"""Repository analyzer orchestrating deterministic domain detectors and aggregating ProjectInfo."""

from pathlib import Path
from typing import Sequence

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.analyzer.detectors import DEFAULT_DETECTORS
from runrepo.models import (
    AnalysisWarning,
    Confidence,
    DatabaseRequirement,
    DatabaseType,
    DependencyInfo,
    DetectionEvidence,
    DockerInfo,
    EnvironmentVariable,
    FrameworkCategory,
    FrameworkInfo,
    PackageManagerInfo,
    ProjectInfo,
    ProjectScript,
    ProjectType,
    RuntimeInfo,
    ServiceRequirement,
    SubprojectInfo,
)


class RepositoryAnalyzer:
    """Orchestrates filesystem scanning, detector execution, and ProjectInfo synthesis.

    Preserves structured evidence throughout the entire pipeline without reducing
    evidence to strings.
    """

    def __init__(self, detectors: Sequence[BaseDetector] | None = None) -> None:
        self.detectors = list(detectors) if detectors is not None else list(DEFAULT_DETECTORS)

    def analyze(self, repo_path: Path | str, enable_ai: bool = True) -> ProjectInfo:
        """Deterministically analyze a local repository and return structured ProjectInfo."""
        path_obj = Path(repo_path).resolve()
        context = ScanContext(path_obj)

        results: list[DetectorResult] = []
        for detector in self.detectors:
            try:
                res = detector.detect(context)
                results.append(res)
            except Exception as err:
                context.add_warning(
                    file_path=".",
                    message=f"Detector '{detector.name}' failed: {err}",
                    code="DETECTOR_EXECUTION_ERROR",
                )

        project_info = self._synthesize_project_info(path_obj, context, results)

        # Ambiguity resolution via optional Gemini AI if ambiguous
        if enable_ai and (project_info.project_type == ProjectType.UNKNOWN or not project_info.scripts):
            try:
                from runrepo.ai import AIRepositoryAnalyzer
                ai_analyzer = AIRepositoryAnalyzer()
                if ai_analyzer.client.is_available():
                    project_info = ai_analyzer.analyze_ambiguity(path_obj, project_info)
            except Exception:
                pass

        return project_info

    def _synthesize_project_info(
        self,
        root_path: Path,
        context: ScanContext,
        results: list[DetectorResult],
    ) -> ProjectInfo:
        # Determine project name
        project_name = root_path.name
        if context.has_file("package.json"):
            pkg = context.read_json("package.json")
            if isinstance(pkg, dict) and "name" in pkg and isinstance(pkg["name"], str):
                project_name = pkg["name"]
        elif context.has_file("pyproject.toml"):
            toml_data = context.read_toml("pyproject.toml")
            if isinstance(toml_data, dict):
                p_name = toml_data.get("project", {}).get("name") or toml_data.get("tool", {}).get("poetry", {}).get("name")
                if p_name and isinstance(p_name, str):
                    project_name = p_name

        # Aggregate languages
        languages_set: set[str] = set()
        for r in results:
            languages_set.update(r.languages)
        languages = sorted(languages_set)

        # Aggregate runtimes (merge by runtime name and combine evidence)
        runtimes_map: dict[str, RuntimeInfo] = {}
        for r in results:
            for rt in r.runtimes:
                if rt.name not in runtimes_map:
                    runtimes_map[rt.name] = rt.model_copy(deep=True)
                else:
                    existing = runtimes_map[rt.name]
                    if not existing.version and rt.version:
                        existing.version = rt.version
                        existing.version_raw = rt.version_raw
                    existing.evidence.extend(rt.evidence)

        # Aggregate package managers (merge by name and combine evidence)
        pm_map: dict[str, PackageManagerInfo] = {}
        for r in results:
            for pm in r.package_managers:
                if pm.name not in pm_map:
                    pm_map[pm.name] = pm.model_copy(deep=True)
                else:
                    existing = pm_map[pm.name]
                    if not existing.lockfile and pm.lockfile:
                        existing.lockfile = pm.lockfile
                    if not existing.version and pm.version:
                        existing.version = pm.version
                    existing.evidence.extend(pm.evidence)

        # Aggregate frameworks (merge by name and combine evidence)
        fw_map: dict[str, FrameworkInfo] = {}
        for r in results:
            for fw in r.frameworks:
                if fw.name not in fw_map:
                    fw_map[fw.name] = fw.model_copy(deep=True)
                else:
                    existing = fw_map[fw.name]
                    if not existing.version and fw.version:
                        existing.version = fw.version
                    existing.evidence.extend(fw.evidence)

        # Aggregate scripts
        scripts_map: dict[tuple[str, str], ProjectScript] = {}
        for r in results:
            for s in r.scripts:
                key = (s.name, s.command)
                if key not in scripts_map:
                    scripts_map[key] = s.model_copy(deep=True)
                else:
                    scripts_map[key].evidence.extend(s.evidence)

        # Aggregate dependencies
        deps_map: dict[tuple[str, str | None], DependencyInfo] = {}
        for r in results:
            for d in r.dependencies:
                key = (d.name.lower(), d.source_file)
                if key not in deps_map:
                    deps_map[key] = d.model_copy(deep=True)
                else:
                    deps_map[key].evidence.extend(d.evidence)

        # Aggregate environment variables
        env_map: dict[str, EnvironmentVariable] = {}
        for r in results:
            for ev in r.environment_variables:
                if ev.name not in env_map:
                    env_map[ev.name] = ev.model_copy(deep=True)
                else:
                    existing = env_map[ev.name]
                    existing.is_required = existing.is_required or ev.is_required
                    if not existing.default_value and ev.default_value:
                        existing.default_value = ev.default_value
                    if not existing.description and ev.description:
                        existing.description = ev.description
                    existing.evidence.extend(ev.evidence)

        # Aggregate databases
        db_map: dict[DatabaseType, DatabaseRequirement] = {}
        for r in results:
            for db in r.databases:
                if db.name not in db_map:
                    db_map[db.name] = db.model_copy(deep=True)
                else:
                    existing = db_map[db.name]
                    if not existing.orm and db.orm:
                        existing.orm = db.orm
                    if not existing.connection_var and db.connection_var:
                        existing.connection_var = db.connection_var
                    existing.evidence.extend(db.evidence)

        # Aggregate services
        svc_map: dict[str, ServiceRequirement] = {}
        for r in results:
            for s in r.services:
                if s.name not in svc_map:
                    svc_map[s.name] = s.model_copy(deep=True)
                else:
                    existing = svc_map[s.name]
                    if not existing.image and s.image:
                        existing.image = s.image
                    existing.evidence.extend(s.evidence)

        # Aggregate Docker
        combined_docker = DockerInfo()
        for r in results:
            if r.docker is not None:
                if r.docker.has_dockerfile:
                    combined_docker.has_dockerfile = True
                combined_docker.dockerfiles.extend(
                    df for df in r.docker.dockerfiles if df not in combined_docker.dockerfiles
                )
                combined_docker.compose_files.extend(
                    cf for cf in r.docker.compose_files if cf not in combined_docker.compose_files
                )
                combined_docker.compose_services.extend(r.docker.compose_services)
                combined_docker.evidence.extend(r.docker.evidence)

        # Aggregate subprojects (preserving path and isolated properties)
        subprojects_map: dict[str, SubprojectInfo] = {}
        for r in results:
            for sp in r.subprojects:
                if sp.path not in subprojects_map:
                    subprojects_map[sp.path] = sp.model_copy(deep=True)
                else:
                    existing = subprojects_map[sp.path]
                    existing.languages = sorted(set(existing.languages + sp.languages))
                    existing.runtimes.extend(sp.runtimes)
                    existing.package_managers.extend(sp.package_managers)
                    existing.frameworks.extend(sp.frameworks)
                    existing.scripts.extend(sp.scripts)
                    existing.dependencies.extend(sp.dependencies)
                    existing.databases.extend(sp.databases)
                    existing.evidence.extend(sp.evidence)

        # Monorepo status
        is_monorepo = any(r.is_monorepo for r in results) or len(subprojects_map) > 1

        # Entrypoints
        entrypoints_set: set[str] = set()
        for r in results:
            entrypoints_set.update(r.entrypoints)
        entrypoints = sorted(entrypoints_set)

        # Infer high-level ProjectType
        project_type = self._infer_project_type(
            frameworks=list(fw_map.values()),
            subprojects=list(subprojects_map.values()),
            runtimes=list(runtimes_map.values()),
            scripts=list(scripts_map.values()),
            entrypoints=entrypoints,
        )

        # Project level evidence
        project_evidence: list[DetectionEvidence] = []
        for r in results:
            project_evidence.extend(r.evidence)

        return ProjectInfo(
            path=root_path.as_posix(),
            name=project_name,
            project_type=project_type,
            is_monorepo=is_monorepo,
            languages=languages,
            runtimes=list(runtimes_map.values()),
            package_managers=list(pm_map.values()),
            frameworks=list(fw_map.values()),
            scripts=list(scripts_map.values()),
            dependencies=list(deps_map.values()),
            environment_variables=list(env_map.values()),
            databases=list(db_map.values()),
            services=list(svc_map.values()),
            docker=combined_docker,
            subprojects=sorted(subprojects_map.values(), key=lambda x: x.path),
            entrypoints=entrypoints,
            warnings=context.warnings,
            evidence=project_evidence,
        )

    def _infer_project_type(
        self,
        frameworks: list[FrameworkInfo],
        subprojects: list[SubprojectInfo],
        runtimes: list[RuntimeInfo],
        scripts: list[ProjectScript],
        entrypoints: list[str],
    ) -> ProjectType:
        # Check polyglot / fullstack with frontend + backend subprojects
        if len(subprojects) >= 2 or len(runtimes) >= 2:
            has_fe = any(
                fw.category in (FrameworkCategory.WEB_FRONTEND, FrameworkCategory.FULLSTACK)
                for fw in frameworks
            ) or any(
                "frontend" in sp.path.lower() or "client" in sp.path.lower() or "ui" in sp.path.lower()
                for sp in subprojects
            )
            has_be = any(
                fw.category in (FrameworkCategory.WEB_BACKEND, FrameworkCategory.FULLSTACK)
                for fw in frameworks
            ) or any(
                "backend" in sp.path.lower() or "server" in sp.path.lower() or "api" in sp.path.lower()
                for sp in subprojects
            )
            if has_fe and has_be:
                return ProjectType.POLYGLOT_FULLSTACK

        # Framework categories
        categories = {fw.category for fw in frameworks}
        if FrameworkCategory.FULLSTACK in categories:
            return ProjectType.WEB_APPLICATION
        if FrameworkCategory.WEB_FRONTEND in categories or FrameworkCategory.UI_LIBRARY in categories:
            return ProjectType.WEB_APPLICATION
        if FrameworkCategory.WEB_BACKEND in categories:
            return ProjectType.API_SERVICE

        # Check script cues for web applications
        script_names = {s.name.lower() for s in scripts}
        if "dev" in script_names or "start" in script_names:
            return ProjectType.WEB_APPLICATION

        # Check for explicit CLI tool declarations (project.scripts, poetry scripts, or entrypoints)
        has_cli_script = any(
            s.evidence and any(
                "project.scripts" in (e.detail or "")
                or "tool.poetry.scripts" in (e.detail or "")
                or "bin" in e.source
                for e in s.evidence
            )
            for s in scripts
        ) or any(s.name in ("cli", "run", "main") for s in scripts)

        if entrypoints or has_cli_script:
            return ProjectType.CLI_TOOL

        if "build" in script_names:
            return ProjectType.WEB_APPLICATION

        # If runtimes exist but no web or CLI entrypoints
        if runtimes:
            return ProjectType.LIBRARY

        return ProjectType.UNKNOWN
