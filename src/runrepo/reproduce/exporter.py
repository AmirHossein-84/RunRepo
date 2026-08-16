"""Declarative configuration exporter generating runrepo.yaml and runrepo.lock from verified projects."""

from pathlib import Path
import yaml
from runrepo.analyzer import RepositoryAnalyzer
from runrepo.environment.checker import EnvironmentChecker
from runrepo.models import ProjectInfo
from runrepo.reproducibility import ReproducibilityManager


class EnvironmentExporter:
    """Exports structured runrepo.yaml manifest and runrepo.lock configuration."""

    def __init__(self, analyzer: RepositoryAnalyzer | None = None) -> None:
        self.analyzer = analyzer or RepositoryAnalyzer()

    def export_yaml(self, repo_path: Path) -> str:
        """Generate a clean, declarative runrepo.yaml string from analyzed project facts."""
        project_info = self.analyzer.analyze(repo_path)
        runtime_dict = {}
        for rt in project_info.runtimes:
            runtime_dict[rt.name] = rt.version or "latest"

        pm_name = project_info.package_managers[0].name if project_info.package_managers else "npm"
        services_list = [svc.name for svc in project_info.services] + [db.name for db in project_info.databases]
        scripts_dict = {s.name: s.command for s in project_info.scripts}

        manifest = {
            "version": "1.0",
            "name": project_info.name,
            "runtime": runtime_dict or {"node": "22"},
            "package_manager": pm_name,
            "services": list(dict.fromkeys(services_list)),
            "environment": {
                "generate": [
                    ev.name for ev in project_info.environment_variables
                    if ev.category.value in ("secret", "local_default")
                ]
            },
            "commands": {
                "install": f"{pm_name} install" if pm_name != "uv" else "uv sync",
                "start": scripts_dict.get("dev") or scripts_dict.get("start") or f"{pm_name} start",
            },
        }
        return yaml.dump(manifest, sort_keys=False)

    def export_lock(self, repo_path: Path) -> str:
        """Generate a reproducible runrepo.lock JSON string."""
        project_info = self.analyzer.analyze(repo_path)
        checker = EnvironmentChecker()
        env_state = checker.check_environment(project_info)
        from runrepo.planner import ExecutionPlanner
        planner = ExecutionPlanner()
        plan = planner.plan(project_info, env_state)
        mgr = ReproducibilityManager(repo_path)
        lock = mgr.generate_lockfile(project_info, env_state, plan)
        return lock.model_dump_json(indent=2)
