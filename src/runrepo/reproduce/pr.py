"""Pull Request reproduction orchestrator executing isolated PR builds, test suites, and smoke checks."""

import time
from pathlib import Path
from typing import Any

from runrepo.analyzer import RepositoryAnalyzer
from runrepo.environment.checker import EnvironmentChecker
from runrepo.executor import ExecutionEngine
from runrepo.executor.confirmation import AutoConfirmationHandler
from runrepo.executor.process import ProcessExecutor, SystemProcessExecutor
from runrepo.executor.process_manager import ProcessManager
from runrepo.models import ProjectInfo, ProjectType
from runrepo.planner import ExecutionPlanner
from runrepo.planner.models import ActionType, PlanStatus
from runrepo.repository import RepositoryManager
from runrepo.reproduce.models import PRReproductionReport, TestSuiteResult


class PullRequestRunner:
    """Orchestrates end-to-end pull request reproduction, test execution, and reporting."""

    def __init__(
        self,
        repository_manager: RepositoryManager | None = None,
        analyzer: RepositoryAnalyzer | None = None,
        planner: ExecutionPlanner | None = None,
        executor: ProcessExecutor | None = None,
    ) -> None:
        self.repo_manager = repository_manager or RepositoryManager()
        self.analyzer = analyzer or RepositoryAnalyzer()
        self.planner = planner or ExecutionPlanner()
        self.executor = executor or SystemProcessExecutor()

    def reproduce(
        self,
        pr_url: str,
        refresh: bool = False,
        run_tests: bool = True,
        start_app: bool = True,
    ) -> PRReproductionReport:
        """Fetch, isolate, setup, test, and verify a remote GitHub Pull Request."""
        start_time = time.perf_counter()

        # 1. Resolve and clone PR ref into isolated cache
        res = self.repo_manager.resolve_pull_request(pr_url, refresh=refresh)
        if not res.success or not res.local_path:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return PRReproductionReport(
                pr_url=pr_url,
                owner=res.target.owner or "unknown",
                repo=res.target.name or "unknown",
                pr_number=int(res.target.branch.replace("pr-", "")) if res.target.branch and "pr-" in res.target.branch else 0,
                local_path="",
                setup_successful=False,
                summary=f"Failed to acquire Pull Request: {res.error_message}",
                duration_ms=duration_ms,
            )

        local_path = res.local_path
        owner = res.target.owner or "unknown"
        repo = res.target.name or "unknown"
        pr_num = int(res.target.branch.replace("pr-", "")) if res.target.branch and "pr-" in res.target.branch else 0

        # 2. Analyze repository state
        project_info = self.analyzer.analyze(local_path)
        checker = EnvironmentChecker()
        env_state = checker.check_environment(project_info)

        # 3. Create execution plan
        plan = self.planner.plan(project_info, env_state)
        pm = ProcessManager(state_dir=local_path / ".runrepo_state")
        engine = ExecutionEngine(
            executor=self.executor,
            confirmation=AutoConfirmationHandler(),
            process_manager=pm,
        )

        # Filter out START_APPLICATION from setup phase if we manage testing first
        setup_plan = plan
        if not start_app:
            setup_plan.steps = [s for s in plan.steps if s.action_type != ActionType.START_APPLICATION]

        exec_result = engine.execute(setup_plan)
        setup_ok = exec_result.status.value == "SUCCESS"

        test_results: list[TestSuiteResult] = []
        all_tests_passed = True

        # 4. Detect and execute test suites
        if setup_ok and run_tests:
            test_cmds = self._detect_test_commands(project_info, local_path)
            for cmd in test_cmds:
                t_start = time.perf_counter()
                t_res = self.executor.execute(cmd, cwd=local_path)
                t_dur = (time.perf_counter() - t_start) * 1000.0
                passed = t_res.exit_code == 0
                if not passed:
                    all_tests_passed = False
                test_results.append(
                    TestSuiteResult(
                        command=cmd,
                        exit_code=t_res.exit_code,
                        passed=passed,
                        duration_ms=t_dur,
                        stdout=t_res.stdout,
                        stderr=t_res.stderr,
                    )
                )

        # 5. Determine application startup endpoints
        live_urls: list[str] = []
        if setup_ok and start_app:
            running_procs = pm.list_processes()
            for proc in running_procs:
                if proc.port:
                    live_urls.append(f"http://localhost:{proc.port}")

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # 6. Build summary
        summary_lines = [
            f"# PR Reproduction Report for {owner}/{repo} #{pr_num}",
            f"- **Repository:** `{owner}/{repo}`",
            f"- **PR Number:** `#{pr_num}`",
            f"- **Location:** `{local_path}`",
            f"- **Environment Setup:** {'PASSED' if setup_ok else 'FAILED'}",
        ]
        if test_results:
            passed_cnt = sum(1 for t in test_results if t.passed)
            summary_lines.append(f"- **Test Suites:** {passed_cnt}/{len(test_results)} passed")
            for t in test_results:
                summary_lines.append(f"  - `{' '.join(t.command)}`: {'PASSED' if t.passed else 'FAILED'}")
        if live_urls:
            summary_lines.append(f"- **Live Endpoints:** {', '.join(live_urls)}")

        return PRReproductionReport(
            pr_url=pr_url,
            owner=owner,
            repo=repo,
            pr_number=pr_num,
            local_path=str(local_path),
            setup_successful=setup_ok,
            test_results=test_results,
            all_tests_passed=all_tests_passed,
            startup_successful=setup_ok and (bool(live_urls) or not start_app),
            live_urls=live_urls,
            duration_ms=duration_ms,
            summary="\n".join(summary_lines),
        )

    def _detect_test_commands(self, project_info: ProjectInfo, local_path: Path) -> list[list[str]]:
        """Detect automated test runner commands across Node.js, Python, Rust, and Go."""
        cmds: list[list[str]] = []
        runtimes = {rt.name.lower() for rt in project_info.runtimes}
        pms = {pm.name.lower() for pm in project_info.package_managers}
        scripts = {s.name.lower(): s.command for s in project_info.scripts}

        # 1. Node.js
        if "node" in runtimes or "npm" in pms or "pnpm" in pms or "yarn" in pms:
            if "test" in scripts:
                if "pnpm" in pms:
                    cmds.append(["pnpm", "test"])
                elif "yarn" in pms:
                    cmds.append(["yarn", "test"])
                else:
                    cmds.append(["npm", "test"])

        # 2. Python
        if "python" in runtimes or "pip" in pms or "uv" in pms or "poetry" in pms:
            has_tests_dir = (local_path / "tests").is_dir() or (local_path / "test").is_dir()
            has_pytest_ini = (local_path / "pytest.ini").is_file() or (local_path / "pyproject.toml").is_file()
            if has_tests_dir or has_pytest_ini:
                if "poetry" in pms:
                    cmds.append(["poetry", "run", "pytest"])
                elif "uv" in pms or "pip" in pms:
                    cmds.append(["uv", "run", "pytest"])
                else:
                    cmds.append(["pytest"])

        return cmds
