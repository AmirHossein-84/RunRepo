"""Detector for monorepo layouts and workspace tools (pnpm, npm, yarn, turbo, nx, uv, poetry)."""

import json
from pathlib import Path
from typing import Any
import yaml
from runrepo.monorepo.models import MonorepoInfo, WorkspacePackage, WorkspaceType


class MonorepoDetector:
    """Discovers workspace configurations and locates sub-packages across repositories."""

    IGNORED_DIRS = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", ".next", ".turbo"}

    def detect(self, repo_path: Path | str) -> MonorepoInfo:
        """Scan repository for monorepo workspace patterns and return MonorepoInfo."""
        root = Path(repo_path).resolve()
        info = MonorepoInfo(root_path=str(root))

        # 1. Check for explicit workspace configuration files
        pnpm_workspace = root / "pnpm-workspace.yaml"
        turbo_json = root / "turbo.json"
        nx_json = root / "nx.json"
        lerna_json = root / "lerna.json"
        root_pkg_json = root / "package.json"
        root_pyproject = root / "pyproject.toml"

        is_monorepo = False
        ws_type = WorkspaceType.SINGLE_PROJECT

        if turbo_json.exists():
            is_monorepo = True
            ws_type = WorkspaceType.TURBOREPO
        elif nx_json.exists():
            is_monorepo = True
            ws_type = WorkspaceType.NX
        elif pnpm_workspace.exists():
            is_monorepo = True
            ws_type = WorkspaceType.PNPM
        elif lerna_json.exists():
            is_monorepo = True
            ws_type = WorkspaceType.LERNA
        elif root_pkg_json.exists():
            try:
                pkg_data = json.loads(root_pkg_json.read_text(encoding="utf-8"))
                if "workspaces" in pkg_data:
                    is_monorepo = True
                    ws_type = WorkspaceType.YARN if (root / "yarn.lock").exists() else WorkspaceType.NPM
            except Exception:
                pass

        if not is_monorepo and root_pyproject.exists():
            try:
                content = root_pyproject.read_text(encoding="utf-8")
                if "[tool.uv.workspace]" in content:
                    is_monorepo = True
                    ws_type = WorkspaceType.UV_WORKSPACE
            except Exception:
                pass

        # 2. Check for layout conventions (apps/, packages/, services/)
        packages: list[WorkspacePackage] = []
        app_dirs = [d for d in ("apps", "packages", "services", "libs", "frontend", "backend") if (root / d).is_dir()]
        if app_dirs and not is_monorepo:
            # Check if there are multiple child packages
            found_subpackages = self._find_subpackages(root)
            if len(found_subpackages) > 1:
                is_monorepo = True
                ws_type = WorkspaceType.DIRECTORY_SUBPROJECTS
                packages = found_subpackages
        elif is_monorepo:
            packages = self._find_subpackages(root)

        runnable_apps = [p for p in packages if p.is_runnable and p.is_application] or [p for p in packages if p.is_runnable]

        info.is_monorepo = is_monorepo
        info.workspace_type = ws_type if is_monorepo else WorkspaceType.SINGLE_PROJECT
        info.packages = packages
        info.runnable_apps = runnable_apps
        return info

    def _find_subpackages(self, root: Path, max_depth: int = 3) -> list[WorkspacePackage]:
        """Recursively discover child package directories containing package.json or pyproject.toml."""
        packages: list[WorkspacePackage] = []

        for candidate_dir in self._walk_dirs(root, depth=1, max_depth=max_depth):
            if candidate_dir == root:
                continue

            rel_path = candidate_dir.relative_to(root)
            pkg_json = candidate_dir / "package.json"
            pyproject = candidate_dir / "pyproject.toml"

            if pkg_json.exists():
                try:
                    data = json.loads(pkg_json.read_text(encoding="utf-8"))
                    name = data.get("name", candidate_dir.name)
                    version = data.get("version")
                    scripts = data.get("scripts", {}) if isinstance(data.get("scripts"), dict) else {}
                    deps_dict = data.get("dependencies", {}) if isinstance(data.get("dependencies"), dict) else {}
                    deps = list(deps_dict.keys())

                    is_runnable = any(k in scripts for k in ("dev", "start", "serve"))
                    is_app = (
                        "apps" in rel_path.parts
                        or "services" in rel_path.parts
                        or "frontend" in rel_path.parts
                        or "backend" in rel_path.parts
                        or ("packages" not in rel_path.parts and "libs" not in rel_path.parts and ("next" in deps_dict or "express" in deps_dict))
                    )

                    packages.append(
                        WorkspacePackage(
                            name=name,
                            path=str(rel_path).replace("\\", "/"),
                            version=version,
                            scripts=scripts,
                            dependencies=deps,
                            is_runnable=is_runnable,
                            is_application=is_app,
                            framework="Next.js" if "next" in deps_dict else None,
                        )
                    )
                except Exception:
                    pass

            elif pyproject.exists():
                name = candidate_dir.name
                is_app = "apps" in rel_path.parts or "services" in rel_path.parts or "backend" in rel_path.parts
                packages.append(
                    WorkspacePackage(
                        name=name,
                        path=str(rel_path).replace("\\", "/"),
                        is_runnable=True,
                        is_application=is_app,
                    )
                )

        return sorted(packages, key=lambda p: p.path)

    def _walk_dirs(self, current: Path, depth: int, max_depth: int):
        """Yield directory paths avoiding ignored build directories."""
        if depth > max_depth:
            return

        try:
            for entry in current.iterdir():
                if entry.is_dir() and entry.name not in self.IGNORED_DIRS and not entry.name.startswith("."):
                    yield entry
                    yield from self._walk_dirs(entry, depth + 1, max_depth)
        except Exception:
            pass
