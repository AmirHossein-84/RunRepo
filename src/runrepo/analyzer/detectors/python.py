"""Deterministic Python runtime, package manager, and framework detector."""

from pathlib import Path
import re
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

KNOWN_PYTHON_FRAMEWORKS: dict[str, tuple[str, FrameworkCategory]] = {
    "fastapi": ("FastAPI", FrameworkCategory.WEB_BACKEND),
    "django": ("Django", FrameworkCategory.FULLSTACK),
    "flask": ("Flask", FrameworkCategory.WEB_BACKEND),
    "starlette": ("Starlette", FrameworkCategory.WEB_BACKEND),
    "litestar": ("Litestar", FrameworkCategory.WEB_BACKEND),
    "tornado": ("Tornado", FrameworkCategory.WEB_BACKEND),
    "sanic": ("Sanic", FrameworkCategory.WEB_BACKEND),
    "streamlit": ("Streamlit", FrameworkCategory.WEB_FRONTEND),
    "gradio": ("Gradio", FrameworkCategory.WEB_FRONTEND),
    "celery": ("Celery", FrameworkCategory.OTHER),
}

CANDIDATE_ENTRYPOINTS = [
    "main.py",
    "app.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "run.py",
    "cli.py",
    "server.py",
]

DEP_REGEX = re.compile(r"^([a-zA-Z0-9_\-\.]+)(?:\[[^\]]*\])?\s*([<>=!~].*)?$")


class PythonDetector(BaseDetector):
    """Detects Python runtimes, pip/uv/poetry/pipenv package managers, frameworks, and entrypoints."""

    @property
    def name(self) -> str:
        return "python"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        all_py_files = [f for f in context.get_all_files() if f.endswith(".py")]
        pyproject_files = context.find_files_by_name("pyproject.toml")
        requirements_files = [
            f
            for f in context.get_all_files()
            if f.endswith("requirements.txt") or f == "requirements.txt" or "/requirements/" in f
        ]
        pipfile_files = context.find_files_by_name("Pipfile")
        has_python_version_file = context.has_file(".python-version") or context.has_file("runtime.txt")
        has_setup_cfg = context.has_file("setup.cfg") or context.has_file("setup.py")

        has_python_project = (
            bool(all_py_files)
            or bool(pyproject_files)
            or bool(requirements_files)
            or bool(pipfile_files)
            or has_python_version_file
            or has_setup_cfg
        )

        if not has_python_project:
            return result

        result.languages.append("Python")

        # 1. Detect Python Version
        python_version: str | None = None
        python_raw_version: str | None = None
        python_evidence: list[DetectionEvidence] = []

        if context.has_file(".python-version"):
            text = context.read_text(".python-version")
            if text:
                v = text.strip()
                python_version = v
                python_raw_version = v
                python_evidence.append(
                    DetectionEvidence(
                        source=".python-version",
                        detail=v,
                        confidence=Confidence.HIGH,
                        path=".python-version",
                    )
                )

        if context.has_file("runtime.txt"):
            text = context.read_text("runtime.txt")
            if text:
                v = text.strip()
                if v.startswith("python-"):
                    v_clean = v.replace("python-", "")
                    if not python_version:
                        python_version = v_clean
                        python_raw_version = v
                    python_evidence.append(
                        DetectionEvidence(
                            source="runtime.txt",
                            detail=v,
                            confidence=Confidence.HIGH,
                            path="runtime.txt",
                        )
                    )

        # Check pyproject.toml for requires-python
        root_pyproject: dict[str, Any] | None = None
        if context.has_file("pyproject.toml"):
            root_pyproject = context.read_toml("pyproject.toml")
            if root_pyproject:
                project_table = root_pyproject.get("project")
                if isinstance(project_table, dict) and "requires-python" in project_table:
                    req_py = str(project_table["requires-python"])
                    if not python_version:
                        python_version = req_py
                        python_raw_version = req_py
                    python_evidence.append(
                        DetectionEvidence(
                            source="pyproject.toml",
                            detail=f"requires-python = {req_py}",
                            confidence=Confidence.HIGH,
                            path="pyproject.toml",
                        )
                    )
                # Poetry python dependency
                tool_poetry = (
                    root_pyproject.get("tool", {}).get("poetry", {})
                    if isinstance(root_pyproject.get("tool"), dict)
                    else {}
                )
                if isinstance(tool_poetry, dict):
                    poetry_deps = tool_poetry.get("dependencies", {})
                    if isinstance(poetry_deps, dict) and "python" in poetry_deps:
                        poetry_py = str(poetry_deps["python"])
                        if not python_version:
                            python_version = poetry_py
                            python_raw_version = poetry_py
                        python_evidence.append(
                            DetectionEvidence(
                                source="pyproject.toml",
                                detail=f"tool.poetry.dependencies.python = {poetry_py}",
                                confidence=Confidence.HIGH,
                                path="pyproject.toml",
                            )
                        )

        # Fallback evidence if general python files exist
        if not python_evidence:
            if pyproject_files:
                python_evidence.append(
                    DetectionEvidence(
                        source="pyproject.toml",
                        detail="Python project configuration found",
                        confidence=Confidence.HIGH,
                        path=pyproject_files[0],
                    )
                )
            elif requirements_files:
                python_evidence.append(
                    DetectionEvidence(
                        source="requirements.txt",
                        detail="Python requirements manifest found",
                        confidence=Confidence.HIGH,
                        path=requirements_files[0],
                    )
                )
            else:
                python_evidence.append(
                    DetectionEvidence(
                        source="codebase",
                        detail="Python source files present",
                        confidence=Confidence.MEDIUM,
                    )
                )

        result.runtimes.append(
            RuntimeInfo(
                name="python",
                version=python_version,
                version_raw=python_raw_version,
                evidence=python_evidence,
            )
        )

        # 2. Detect Package Managers
        pkg_managers = self._detect_package_managers(context, root_pyproject)
        result.package_managers.extend(pkg_managers)

        # 3. Detect Root Dependencies, Frameworks, Scripts
        root_deps: list[DependencyInfo] = []
        root_fws: list[FrameworkInfo] = []
        root_scripts: list[ProjectScript] = []

        if root_pyproject:
            p_scripts, p_deps, p_fws = self._parse_pyproject_content(
                root_pyproject, "pyproject.toml"
            )
            root_scripts.extend(p_scripts)
            root_deps.extend(p_deps)
            root_fws.extend(p_fws)

        if context.has_file("requirements.txt"):
            r_deps, r_fws = self._parse_requirements_file(context, "requirements.txt")
            # Merge without duplicates
            existing_names = {d.name.lower() for d in root_deps}
            for d in r_deps:
                if d.name.lower() not in existing_names:
                    root_deps.append(d)
                    existing_names.add(d.name.lower())
            existing_fw_names = {f.name for f in root_fws}
            for f in r_fws:
                if f.name not in existing_fw_names:
                    root_fws.append(f)
                    existing_fw_names.add(f.name)

        result.scripts.extend(root_scripts)
        result.dependencies.extend(root_deps)
        result.frameworks.extend(root_fws)

        # 4. Detect Entrypoints
        for candidate in CANDIDATE_ENTRYPOINTS:
            if context.has_file(candidate):
                result.entrypoints.append(candidate)
                result.evidence.append(
                    DetectionEvidence(
                        source=candidate,
                        detail=f"Candidate Python entrypoint '{candidate}' present",
                        confidence=Confidence.MEDIUM,
                        path=candidate,
                    )
                )

        if not result.entrypoints:
            root_py_files = [
                f
                for f in context.get_all_files()
                if "/" not in f and f.endswith(".py") and not f.startswith("test_") and f != "setup.py"
            ]
            main_block_files = []
            for py_f in root_py_files:
                content = context.read_text(py_f)
                if content and ("__main__" in content or "if __name__" in content):
                    main_block_files.append(py_f)

            chosen = main_block_files[0] if main_block_files else (root_py_files[0] if len(root_py_files) == 1 else None)
            if chosen:
                result.entrypoints.append(chosen)
                result.evidence.append(
                    DetectionEvidence(
                        source=chosen,
                        detail=f"Detected primary Python script '{chosen}' as entrypoint",
                        confidence=Confidence.HIGH if main_block_files else Confidence.MEDIUM,
                        path=chosen,
                    )
                )

        # 5. Detect Python Subprojects (e.g. backend/pyproject.toml, server/requirements.txt)
        sub_manifests: set[str] = set()
        for f in pyproject_files:
            if f != "pyproject.toml":
                sub_manifests.add(f)
        for f in requirements_files:
            if f != "requirements.txt" and not f.startswith("requirements/"):
                sub_manifests.add(f)

        processed_dirs: set[str] = set()
        for manifest in sorted(sub_manifests):
            sub_dir = str(Path(manifest).parent.as_posix())
            if sub_dir in processed_dirs or sub_dir == ".":
                continue
            # Skip test fixtures, benchmarks, ci directories, and template placeholders
            if "{{" in sub_dir or "}}" in sub_dir or "{%" in sub_dir or "%}" in sub_dir:
                continue
            parts = sub_dir.lower().split("/")
            if any(p in {"test", "tests", "fixtures", "fixture", "test_fixtures", "spec", "specs", "e2e", "benchmark", "benchmarks", "ci", ".ci", "build_tools", "tools", "scripts", ".github", "vendor", ".binder", "docker", ".docker", "docs", "documentation", ".devcontainer"} for p in parts):
                continue

            sub_pyproject_path = f"{sub_dir}/pyproject.toml"
            sub_req_path = f"{sub_dir}/requirements.txt"
            sub_setup_path = f"{sub_dir}/setup.py"
            sub_cfg_path = f"{sub_dir}/setup.cfg"

            has_manifest = (
                context.has_file(sub_pyproject_path)
                or context.has_file(sub_req_path)
                or context.has_file(sub_setup_path)
                or context.has_file(sub_cfg_path)
            )
            if not has_manifest:
                continue

            processed_dirs.add(sub_dir)

            sub_scripts: list[ProjectScript] = []
            sub_deps: list[DependencyInfo] = []
            sub_fws: list[FrameworkInfo] = []
            sub_pms: list[PackageManagerInfo] = []

            if context.has_file(sub_pyproject_path):
                sub_toml = context.read_toml(sub_pyproject_path)
                if sub_toml:
                    s_scripts, s_deps, s_fws = self._parse_pyproject_content(
                        sub_toml, sub_pyproject_path
                    )
                    sub_scripts.extend(s_scripts)
                    sub_deps.extend(s_deps)
                    sub_fws.extend(s_fws)
                sub_pms.append(
                    PackageManagerInfo(
                        name="pip",
                        evidence=[
                            DetectionEvidence(
                                source="pyproject.toml",
                                detail="Python subproject configuration found",
                                confidence=Confidence.HIGH,
                                path=sub_pyproject_path,
                            )
                        ],
                    )
                )

            if context.has_file(sub_req_path):
                s_deps2, s_fws2 = self._parse_requirements_file(context, sub_req_path)
                existing_d = {d.name.lower() for d in sub_deps}
                for d in s_deps2:
                    if d.name.lower() not in existing_d:
                        sub_deps.append(d)
                existing_f = {f.name for f in sub_fws}
                for f in s_fws2:
                    if f.name not in existing_f:
                        sub_fws.append(f)
                if not sub_pms:
                    sub_pms.append(
                        PackageManagerInfo(
                            name="pip",
                            evidence=[
                                DetectionEvidence(
                                    source="requirements.txt",
                                    detail="Python subproject requirements found",
                                    confidence=Confidence.HIGH,
                                    path=sub_req_path,
                                )
                            ],
                        )
                    )

            subproject = SubprojectInfo(
                name=sub_dir.split("/")[-1],
                path=sub_dir,
                languages=["Python"],
                runtimes=[
                    RuntimeInfo(
                        name="python",
                        version=python_version,
                        evidence=[
                            DetectionEvidence(
                                source=manifest,
                                detail=f"Python subproject in {sub_dir}",
                                confidence=Confidence.HIGH,
                                path=manifest,
                            )
                        ],
                    )
                ],
                package_managers=sub_pms,
                frameworks=sub_fws,
                scripts=sub_scripts,
                dependencies=sub_deps,
                evidence=[
                    DetectionEvidence(
                        source=manifest,
                        detail=f"Python subproject manifest in {sub_dir}",
                        confidence=Confidence.HIGH,
                        path=manifest,
                    )
                ],
            )
            result.subprojects.append(subproject)

        return result

    def _detect_package_managers(
        self, context: ScanContext, root_pyproject: dict[str, Any] | None
    ) -> list[PackageManagerInfo]:
        pms: list[PackageManagerInfo] = []

        # Check uv
        if context.has_file("uv.lock") or (
            root_pyproject
            and isinstance(root_pyproject.get("tool"), dict)
            and "uv" in root_pyproject["tool"]
        ):
            lock = "uv.lock" if context.has_file("uv.lock") else None
            pms.append(
                PackageManagerInfo(
                    name="uv",
                    lockfile=lock,
                    evidence=[
                        DetectionEvidence(
                            source="uv.lock" if lock else "pyproject.toml",
                            detail="uv lockfile or tool.uv configuration present",
                            confidence=Confidence.HIGH,
                            path=lock or "pyproject.toml",
                        )
                    ],
                )
            )

        # Check poetry
        if context.has_file("poetry.lock") or (
            root_pyproject
            and isinstance(root_pyproject.get("tool"), dict)
            and "poetry" in root_pyproject["tool"]
        ):
            lock = "poetry.lock" if context.has_file("poetry.lock") else None
            pms.append(
                PackageManagerInfo(
                    name="poetry",
                    lockfile=lock,
                    evidence=[
                        DetectionEvidence(
                            source="poetry.lock" if lock else "pyproject.toml",
                            detail="Poetry lockfile or tool.poetry configuration present",
                            confidence=Confidence.HIGH,
                            path=lock or "pyproject.toml",
                        )
                    ],
                )
            )

        # Check pipenv
        if context.has_file("Pipfile") or context.has_file("Pipfile.lock"):
            lock = "Pipfile.lock" if context.has_file("Pipfile.lock") else None
            pms.append(
                PackageManagerInfo(
                    name="pipenv",
                    lockfile=lock,
                    evidence=[
                        DetectionEvidence(
                            source="Pipfile.lock" if lock else "Pipfile",
                            detail="Pipfile present",
                            confidence=Confidence.HIGH,
                            path=lock or "Pipfile",
                        )
                    ],
                )
            )

        # Fallback to pip if requirements.txt or setup.py/cfg exists and no modern manager was matched
        if not pms and (
            context.has_file("requirements.txt")
            or context.has_file("setup.py")
            or context.has_file("setup.cfg")
            or root_pyproject is not None
        ):
            pms.append(
                PackageManagerInfo(
                    name="pip",
                    evidence=[
                        DetectionEvidence(
                            source="requirements.txt"
                            if context.has_file("requirements.txt")
                            else "pyproject.toml",
                            detail="Standard Python package installer",
                            confidence=Confidence.HIGH
                            if context.has_file("requirements.txt")
                            else Confidence.MEDIUM,
                            path="requirements.txt"
                            if context.has_file("requirements.txt")
                            else "pyproject.toml",
                        )
                    ],
                )
            )

        return pms

    def _parse_requirements_file(
        self, context: ScanContext, rel_path: str
    ) -> tuple[list[DependencyInfo], list[FrameworkInfo]]:
        deps: list[DependencyInfo] = []
        fws: list[FrameworkInfo] = []
        text = context.read_text(rel_path)
        if not text:
            return deps, fws

        detected_fws: set[str] = set()

        for line in text.splitlines():
            clean = line.strip()
            if not clean or clean.startswith(("#", "-", "--")):
                continue

            match = DEP_REGEX.match(clean)
            if match:
                name = match.group(1).strip()
                version_spec = match.group(2).strip() if match.group(2) else None
                deps.append(
                    DependencyInfo(
                        name=name,
                        version_spec=version_spec,
                        is_dev=False,
                        source_file=rel_path,
                        evidence=[
                            DetectionEvidence(
                                source="requirements.txt",
                                detail=clean,
                                confidence=Confidence.HIGH,
                                path=rel_path,
                            )
                        ],
                    )
                )

                canonical_name = name.lower().replace("_", "-")
                if canonical_name in KNOWN_PYTHON_FRAMEWORKS and canonical_name not in detected_fws:
                    fw_name, cat = KNOWN_PYTHON_FRAMEWORKS[canonical_name]
                    detected_fws.add(canonical_name)
                    fws.append(
                        FrameworkInfo(
                            name=fw_name,
                            version=version_spec,
                            category=cat,
                            evidence=[
                                DetectionEvidence(
                                    source="requirements.txt",
                                    detail=f"dependency '{name}': {version_spec or 'any'}",
                                    confidence=Confidence.HIGH,
                                    path=rel_path,
                                )
                            ],
                        )
                    )

        return deps, fws

    def _parse_pyproject_content(
        self, pyproject_data: dict[str, Any], file_path: str
    ) -> tuple[list[ProjectScript], list[DependencyInfo], list[FrameworkInfo]]:
        scripts: list[ProjectScript] = []
        deps: list[DependencyInfo] = []
        fws: list[FrameworkInfo] = []
        detected_fws: set[str] = set()

        # Scripts from project.scripts
        project_table = pyproject_data.get("project")
        if isinstance(project_table, dict):
            proj_scripts = project_table.get("scripts")
            if isinstance(proj_scripts, dict):
                for name, cmd in proj_scripts.items():
                    scripts.append(
                        ProjectScript(
                            name=name,
                            command=str(cmd),
                            evidence=[
                                DetectionEvidence(
                                    source="pyproject.toml",
                                    detail=f"project.scripts.{name} = {cmd}",
                                    confidence=Confidence.HIGH,
                                    path=file_path,
                                )
                            ],
                        )
                    )

            # Dependencies from project.dependencies
            proj_deps = project_table.get("dependencies")
            if isinstance(proj_deps, list):
                for item in proj_deps:
                    if isinstance(item, str):
                        match = DEP_REGEX.match(item.strip())
                        if match:
                            name = match.group(1).strip()
                            v_spec = match.group(2).strip() if match.group(2) else None
                            deps.append(
                                DependencyInfo(
                                    name=name,
                                    version_spec=v_spec,
                                    is_dev=False,
                                    source_file=file_path,
                                    evidence=[
                                        DetectionEvidence(
                                            source="pyproject.toml",
                                            detail=f"dependencies: {item}",
                                            confidence=Confidence.HIGH,
                                            path=file_path,
                                        )
                                    ],
                                )
                            )
                            c_name = name.lower().replace("_", "-")
                            if c_name in KNOWN_PYTHON_FRAMEWORKS and c_name not in detected_fws:
                                fw_name, cat = KNOWN_PYTHON_FRAMEWORKS[c_name]
                                detected_fws.add(c_name)
                                fws.append(
                                    FrameworkInfo(
                                        name=fw_name,
                                        version=v_spec,
                                        category=cat,
                                        evidence=[
                                            DetectionEvidence(
                                                source="pyproject.toml",
                                                detail=f"dependency '{name}': {v_spec or 'any'}",
                                                confidence=Confidence.HIGH,
                                                path=file_path,
                                            )
                                        ],
                                    )
                                )

        # Poetry dependencies
        tool_poetry = (
            pyproject_data.get("tool", {}).get("poetry", {})
            if isinstance(pyproject_data.get("tool"), dict)
            else {}
        )
        if isinstance(tool_poetry, dict):
            poetry_scripts = tool_poetry.get("scripts")
            if isinstance(poetry_scripts, dict):
                for name, cmd in poetry_scripts.items():
                    scripts.append(
                        ProjectScript(
                            name=name,
                            command=str(cmd),
                            evidence=[
                                DetectionEvidence(
                                    source="pyproject.toml",
                                    detail=f"tool.poetry.scripts.{name} = {cmd}",
                                    confidence=Confidence.HIGH,
                                    path=file_path,
                                )
                            ],
                        )
                    )
            poetry_deps = tool_poetry.get("dependencies")
            if isinstance(poetry_deps, dict):
                for dep_name, dep_spec in poetry_deps.items():
                    if dep_name.lower() == "python":
                        continue
                    v_spec = str(dep_spec) if isinstance(dep_spec, (str, int, float)) else None
                    deps.append(
                        DependencyInfo(
                            name=dep_name,
                            version_spec=v_spec,
                            is_dev=False,
                            source_file=file_path,
                            evidence=[
                                DetectionEvidence(
                                    source="pyproject.toml",
                                    detail=f"tool.poetry.dependencies.{dep_name} = {dep_spec}",
                                    confidence=Confidence.HIGH,
                                    path=file_path,
                                )
                            ],
                        )
                    )
                    c_name = dep_name.lower().replace("_", "-")
                    if c_name in KNOWN_PYTHON_FRAMEWORKS and c_name not in detected_fws:
                        fw_name, cat = KNOWN_PYTHON_FRAMEWORKS[c_name]
                        detected_fws.add(c_name)
                        fws.append(
                            FrameworkInfo(
                                name=fw_name,
                                version=v_spec,
                                category=cat,
                                evidence=[
                                    DetectionEvidence(
                                        source="pyproject.toml",
                                        detail=f"dependency '{dep_name}': {v_spec or 'any'}",
                                        confidence=Confidence.HIGH,
                                        path=file_path,
                                    )
                                ],
                            )
                        )

        return scripts, deps, fws
