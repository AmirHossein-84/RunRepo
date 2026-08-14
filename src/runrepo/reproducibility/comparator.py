"""Comparator for detecting environment, runtime, service, and plan drift from runrepo.lock."""

from runrepo.environment.models import EnvironmentState
from runrepo.models import ProjectInfo
from runrepo.planner.models import ExecutionPlan
from runrepo.reproducibility.models import LockDiff, RunRepoLock


class ReproducibilityComparator:
    """Detects structural discrepancies between current system/plan facts and an existing lockfile."""

    @classmethod
    def compare(
        cls,
        project_info: ProjectInfo,
        environment_state: EnvironmentState | None,
        execution_plan: ExecutionPlan | None,
        lock: RunRepoLock,
    ) -> LockDiff:
        """Compare current repository facts and plan against locked decisions."""
        diff = LockDiff()

        # 1. Package Manager comparison
        current_pm_names = [pm.name.lower() for pm in project_info.package_managers]
        if lock.resolved_package_manager:
            locked_pm = lock.resolved_package_manager.lower()
            if current_pm_names and locked_pm not in current_pm_names:
                diff.has_changes = True
                diff.package_manager_diff = (lock.resolved_package_manager, current_pm_names[0])
                diff.warnings.append(
                    f"Package manager drifted from locked '{lock.resolved_package_manager}' to '{current_pm_names[0]}'."
                )

        # 2. Runtime Version comparison
        if environment_state:
            for check in environment_state.checks:
                clean_name = check.name.lower().split()[0]
                if clean_name in lock.resolved_runtimes and check.installed_version:
                    locked_ver = lock.resolved_runtimes[clean_name]
                    if check.installed_version != locked_ver:
                        diff.has_changes = True
                        diff.runtime_diffs[clean_name] = (locked_ver, check.installed_version)
                        diff.warnings.append(
                            f"Host runtime '{clean_name}' version drifted: locked '{locked_ver}', current '{check.installed_version}'."
                        )

        # 3. Startup Command comparison
        if project_info.scripts and lock.resolved_startup.command:
            current_startup = [s.command for s in project_info.scripts if s.name in ("dev", "start", "serve")]
            locked_cmd_str = " ".join(lock.resolved_startup.command)
            if current_startup and current_startup[0] != locked_cmd_str:
                diff.has_changes = True
                diff.startup_diff = (lock.resolved_startup.command, current_startup[0].split())
                diff.warnings.append(
                    f"Startup command drifted: locked '{locked_cmd_str}', current '{current_startup[0]}'."
                )

        # 4. Service comparison
        locked_service_names = {s.name.lower() for s in lock.resolved_services}
        current_service_names = {s.name.lower() for s in project_info.services}
        if project_info.databases:
            for db in project_info.databases:
                current_service_names.add(db.name.value.lower())

        if locked_service_names != current_service_names:
            diff.has_changes = True
            diff.service_diffs["services"] = (sorted(locked_service_names), sorted(current_service_names))
            diff.warnings.append(
                f"Services requirement changed: locked {sorted(locked_service_names)}, current {sorted(current_service_names)}."
            )

        # 5. Environment Variables comparison
        locked_env_names = {e.name for e in lock.resolved_environment}
        current_env_names = {e.name for e in project_info.environment_variables}
        new_vars = current_env_names - locked_env_names
        missing_vars = locked_env_names - current_env_names
        if new_vars or missing_vars:
            diff.has_changes = True
            diff.env_diffs = sorted(new_vars | missing_vars)
            if new_vars:
                diff.warnings.append(f"New environment variables detected since lockfile: {sorted(new_vars)}.")
            if missing_vars:
                diff.warnings.append(f"Environment variables no longer detected: {sorted(missing_vars)}.")

        return diff
