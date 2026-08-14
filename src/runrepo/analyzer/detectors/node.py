"""Deterministic Node.js runtime, package manager, and framework detector."""

from pathlib import Path
from typing import Any

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import (
    Confidence,
    DependencyInfo,
    DetectionEvidence,
    FrameworkCategory,
    FrameworkInfo,
    PackageManagerInfo,
    ProjectScript,
    RuntimeInfo,
    SubprojectInfo,
)

# Known Node web/backend frameworks mapped to category and standard display name
KNOWN_FRAMEWORKS: dict[str, tuple[str, FrameworkCategory]] = {
    "next": ("Next.js", FrameworkCategory.FULLSTACK),
    "nuxt": ("Nuxt", FrameworkCategory.FULLSTACK),
    "@remix-run/react": ("Remix", FrameworkCategory.FULLSTACK),
    "@remix-run/node": ("Remix", FrameworkCategory.FULLSTACK),
    "astro": ("Astro", FrameworkCategory.FULLSTACK),
    "@sveltejs/kit": ("SvelteKit", FrameworkCategory.FULLSTACK),
    "gatsby": ("Gatsby", FrameworkCategory.WEB_FRONTEND),
    "vite": ("Vite", FrameworkCategory.WEB_FRONTEND),
    "react": ("React", FrameworkCategory.UI_LIBRARY),
    "vue": ("Vue", FrameworkCategory.UI_LIBRARY),
    "svelte": ("Svelte", FrameworkCategory.UI_LIBRARY),
    "@angular/core": ("Angular", FrameworkCategory.WEB_FRONTEND),
    "express": ("Express", FrameworkCategory.WEB_BACKEND),
    "@nestjs/core": ("NestJS", FrameworkCategory.WEB_BACKEND),
    "fastify": ("Fastify", FrameworkCategory.WEB_BACKEND),
    "hono": ("Hono", FrameworkCategory.WEB_BACKEND),
    "koa": ("Koa", FrameworkCategory.WEB_BACKEND),
    "electron": ("Electron", FrameworkCategory.OTHER),
}


class NodeDetector(BaseDetector):
    """Detects Node.js runtimes, npm/pnpm/yarn/bun package managers, and JS/TS frameworks."""

    @property
    def name(self) -> str:
        return "node"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        all_package_jsons = context.find_files_by_name("package.json")
        has_node_version_files = (
            context.has_file(".nvmrc")
            or context.has_file(".node-version")
            or context.has_file(".nvmrc")
        )
        has_js_ts_files = any(
            f.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"))
            for f in context.get_all_files()
        )

        if not all_package_jsons and not has_node_version_files and not has_js_ts_files:
            return result

        # Detect Node runtime version
        node_version: str | None = None
        node_raw_version: str | None = None
        node_evidence: list[DetectionEvidence] = []

        if context.has_file(".nvmrc"):
            text = context.read_text(".nvmrc")
            if text:
                v = text.strip()
                node_version = v.lstrip("v")
                node_raw_version = v
                node_evidence.append(
                    DetectionEvidence(
                        source=".nvmrc",
                        detail=v,
                        confidence=Confidence.HIGH,
                        path=".nvmrc",
                    )
                )

        if context.has_file(".node-version"):
            text = context.read_text(".node-version")
            if text:
                v = text.strip()
                if not node_version:
                    node_version = v.lstrip("v")
                    node_raw_version = v
                node_evidence.append(
                    DetectionEvidence(
                        source=".node-version",
                        detail=v,
                        confidence=Confidence.HIGH,
                        path=".node-version",
                    )
                )

        # Monorepo indicators
        is_monorepo = False
        if context.has_file("pnpm-workspace.yaml"):
            is_monorepo = True
            result.evidence.append(
                DetectionEvidence(
                    source="pnpm-workspace.yaml",
                    detail="Workspace configuration found",
                    confidence=Confidence.HIGH,
                    path="pnpm-workspace.yaml",
                )
            )

        for mono_cfg in ("turbo.json", "lerna.json", "nx.json"):
            if context.has_file(mono_cfg):
                is_monorepo = True
                result.evidence.append(
                    DetectionEvidence(
                        source=mono_cfg,
                        detail="Monorepo build tool config",
                        confidence=Confidence.HIGH,
                        path=mono_cfg,
                    )
                )

        # Process root and subproject package.json files
        root_pkg_json: dict[str, Any] | None = None
        if context.has_file("package.json"):
            data = context.read_json("package.json")
            if isinstance(data, dict):
                root_pkg_json = data

        if root_pkg_json is not None:
            # Check workspaces field in root package.json
            if "workspaces" in root_pkg_json:
                is_monorepo = True
                result.evidence.append(
                    DetectionEvidence(
                        source="package.json",
                        detail=f"workspaces: {root_pkg_json['workspaces']}",
                        confidence=Confidence.HIGH,
                        path="package.json",
                    )
                )

            # Node engine in root package.json
            engines = root_pkg_json.get("engines")
            if isinstance(engines, dict) and "node" in engines:
                engine_val = str(engines["node"])
                if not node_version:
                    node_version = engine_val
                    node_raw_version = engine_val
                node_evidence.append(
                    DetectionEvidence(
                        source="package.json",
                        detail=f"engines.node: {engine_val}",
                        confidence=Confidence.HIGH,
                        path="package.json",
                    )
                )

        # Record Node.js runtime if detected
        if all_package_jsons or has_node_version_files or has_js_ts_files:
            if not node_evidence and all_package_jsons:
                node_evidence.append(
                    DetectionEvidence(
                        source="package.json",
                        detail="Node.js project manifest present",
                        confidence=Confidence.HIGH,
                        path=all_package_jsons[0],
                    )
                )
            elif not node_evidence:
                node_evidence.append(
                    DetectionEvidence(
                        source="codebase",
                        detail="JavaScript/TypeScript source files present",
                        confidence=Confidence.MEDIUM,
                    )
                )

            result.runtimes.append(
                RuntimeInfo(
                    name="node",
                    version=node_version,
                    version_raw=node_raw_version,
                    evidence=node_evidence,
                )
            )

        # Detect package managers
        pkg_managers = self._detect_package_managers(context, root_pkg_json)
        result.package_managers.extend(pkg_managers)

        # Detect languages
        languages: set[str] = set()
        has_ts = (
            context.has_file("tsconfig.json")
            or any(
                f.endswith((".ts", ".tsx", ".d.ts")) or f.endswith("tsconfig.json")
                for f in context.get_all_files()
            )
        )
        has_js = (
            all_package_jsons
            or any(
                f.endswith((".js", ".jsx", ".mjs", ".cjs"))
                for f in context.get_all_files()
            )
        )
        if has_js:
            languages.add("JavaScript")
        if has_ts:
            languages.add("TypeScript")
        result.languages.extend(sorted(languages))

        # Parse scripts, dependencies, frameworks from root package.json
        if root_pkg_json:
            scripts, deps, fws = self._parse_package_json_content(
                root_pkg_json, "package.json"
            )
            result.scripts.extend(scripts)
            result.dependencies.extend(deps)
            result.frameworks.extend(fws)

        # Process subprojects (e.g. frontend/package.json, apps/web/package.json)
        for pkg_path in all_package_jsons:
            if pkg_path == "package.json":
                continue

            sub_data = context.read_json(pkg_path)
            if not isinstance(sub_data, dict):
                continue

            sub_dir = str(Path(pkg_path).parent.as_posix())
            sub_name = sub_data.get("name") or sub_dir.split("/")[-1]

            sub_scripts, sub_deps, sub_fws = self._parse_package_json_content(
                sub_data, pkg_path
            )

            sub_pm: list[PackageManagerInfo] = []
            if "packageManager" in sub_data:
                pm_str = str(sub_data["packageManager"])
                pm_name = pm_str.split("@")[0]
                sub_pm.append(
                    PackageManagerInfo(
                        name=pm_name,
                        version=pm_str.split("@")[1] if "@" in pm_str else None,
                        evidence=[
                            DetectionEvidence(
                                source="package.json",
                                detail=f"packageManager: {pm_str}",
                                confidence=Confidence.HIGH,
                                path=pkg_path,
                            )
                        ],
                    )
                )

            sub_languages: list[str] = []
            if any(f.startswith(sub_dir + "/") and f.endswith((".ts", ".tsx")) for f in context.get_all_files()):
                sub_languages.append("TypeScript")
            if any(f.startswith(sub_dir + "/") and f.endswith((".js", ".jsx", ".mjs")) for f in context.get_all_files()) or not sub_languages:
                sub_languages.append("JavaScript")

            subproject = SubprojectInfo(
                name=sub_name,
                path=sub_dir,
                languages=sub_languages,
                runtimes=[
                    RuntimeInfo(
                        name="node",
                        version=node_version,
                        evidence=[
                            DetectionEvidence(
                                source="package.json",
                                detail=f"Subproject manifest in {pkg_path}",
                                confidence=Confidence.HIGH,
                                path=pkg_path,
                            )
                        ],
                    )
                ],
                package_managers=sub_pm,
                frameworks=sub_fws,
                scripts=sub_scripts,
                dependencies=sub_deps,
                evidence=[
                    DetectionEvidence(
                        source="package.json",
                        detail=f"Subproject manifest {sub_name}",
                        confidence=Confidence.HIGH,
                        path=pkg_path,
                    )
                ],
            )
            result.subprojects.append(subproject)

        result.is_monorepo = is_monorepo or len(result.subprojects) > 1
        return result

    def _detect_package_managers(
        self, context: ScanContext, root_pkg: dict[str, Any] | None
    ) -> list[PackageManagerInfo]:
        """Detect npm, pnpm, yarn, bun with associated lockfiles and evidence."""
        pms: list[PackageManagerInfo] = []
        seen: set[str] = set()

        # Check packageManager field in package.json (corepack standard)
        if root_pkg and "packageManager" in root_pkg:
            pm_spec = str(root_pkg["packageManager"])
            parts = pm_spec.split("@")
            name = parts[0].strip().lower()
            version = parts[1].strip() if len(parts) > 1 else None
            seen.add(name)
            pms.append(
                PackageManagerInfo(
                    name=name,
                    version=version,
                    evidence=[
                        DetectionEvidence(
                            source="package.json",
                            detail=f"packageManager: {pm_spec}",
                            confidence=Confidence.HIGH,
                            path="package.json",
                        )
                    ],
                )
            )

        # Check lockfiles
        lockfile_map: list[tuple[str, str]] = [
            ("pnpm-lock.yaml", "pnpm"),
            ("package-lock.json", "npm"),
            ("yarn.lock", "yarn"),
            ("bun.lockb", "bun"),
            ("bun.lock", "bun"),
        ]

        for lockfile, pm_name in lockfile_map:
            if context.has_file(lockfile):
                # If already discovered via packageManager, attach lockfile info
                existing = next((pm for pm in pms if pm.name == pm_name), None)
                if existing:
                    existing.lockfile = lockfile
                    existing.evidence.append(
                        DetectionEvidence(
                            source=lockfile,
                            detail=f"Lockfile {lockfile} present",
                            confidence=Confidence.HIGH,
                            path=lockfile,
                        )
                    )
                else:
                    seen.add(pm_name)
                    pms.append(
                        PackageManagerInfo(
                            name=pm_name,
                            lockfile=lockfile,
                            evidence=[
                                DetectionEvidence(
                                    source=lockfile,
                                    detail=f"Lockfile {lockfile} present",
                                    confidence=Confidence.HIGH,
                                    path=lockfile,
                                )
                            ],
                        )
                    )

        # If package.json exists but no lockfile or packageManager detected
        if not pms and root_pkg is not None:
            pms.append(
                PackageManagerInfo(
                    name="npm",
                    evidence=[
                        DetectionEvidence(
                            source="package.json",
                            detail="Default Node package manager (no lockfile found)",
                            confidence=Confidence.LOW,
                            path="package.json",
                        )
                    ],
                )
            )

        return pms

    def _parse_package_json_content(
        self, pkg_data: dict[str, Any], file_path: str
    ) -> tuple[list[ProjectScript], list[DependencyInfo], list[FrameworkInfo]]:
        """Extract scripts, dependencies, and frameworks from a parsed package.json dictionary."""
        scripts: list[ProjectScript] = []
        dependencies: list[DependencyInfo] = []
        frameworks: list[FrameworkInfo] = []

        # Scripts
        raw_scripts = pkg_data.get("scripts")
        if isinstance(raw_scripts, dict):
            for name, cmd in raw_scripts.items():
                if isinstance(cmd, str):
                    scripts.append(
                        ProjectScript(
                            name=name,
                            command=cmd,
                            evidence=[
                                DetectionEvidence(
                                    source="package.json",
                                    detail=f"scripts.{name}: {cmd}",
                                    confidence=Confidence.HIGH,
                                    path=file_path,
                                )
                            ],
                        )
                    )

        # Dependencies & devDependencies
        all_deps_map: dict[str, tuple[str, bool]] = {}

        raw_deps = pkg_data.get("dependencies")
        if isinstance(raw_deps, dict):
            for dep_name, version in raw_deps.items():
                v_str = str(version) if version is not None else None
                all_deps_map[dep_name] = (v_str or "", False)
                dependencies.append(
                    DependencyInfo(
                        name=dep_name,
                        version_spec=v_str,
                        is_dev=False,
                        source_file=file_path,
                        evidence=[
                            DetectionEvidence(
                                source="package.json",
                                detail=f"dependencies.{dep_name}: {v_str}",
                                confidence=Confidence.HIGH,
                                path=file_path,
                            )
                        ],
                    )
                )

        raw_dev_deps = pkg_data.get("devDependencies")
        if isinstance(raw_dev_deps, dict):
            for dep_name, version in raw_dev_deps.items():
                v_str = str(version) if version is not None else None
                all_deps_map[dep_name] = (v_str or "", True)
                dependencies.append(
                    DependencyInfo(
                        name=dep_name,
                        version_spec=v_str,
                        is_dev=True,
                        source_file=file_path,
                        evidence=[
                            DetectionEvidence(
                                source="package.json",
                                detail=f"devDependencies.{dep_name}: {v_str}",
                                confidence=Confidence.HIGH,
                                path=file_path,
                            )
                        ],
                    )
                )

        # Deterministic Framework Detection
        detected_fw_names: set[str] = set()

        for dep_key, (fw_name, category) in KNOWN_FRAMEWORKS.items():
            if dep_key in all_deps_map:
                version_spec, _ = all_deps_map[dep_key]
                if fw_name in detected_fw_names:
                    continue

                detected_fw_names.add(fw_name)
                frameworks.append(
                    FrameworkInfo(
                        name=fw_name,
                        version=version_spec if version_spec else None,
                        category=category,
                        evidence=[
                            DetectionEvidence(
                                source="package.json",
                                detail=f"dependency '{dep_key}': {version_spec}",
                                confidence=Confidence.HIGH,
                                path=file_path,
                            )
                        ],
                    )
                )

        return scripts, dependencies, frameworks
