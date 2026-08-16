import sys
from pathlib import Path
from typing import Annotated, Optional

from rich.console import Console
import typer

from runrepo.analyzer import RepositoryAnalyzer
from runrepo.ui import render_project_analysis

# Ensure UTF-8 output on Windows consoles with legacy codepages (e.g. cp1252)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = typer.Typer(
    name="runrepo",
    help="RunRepo: Deterministic repository analyzer and local environment orchestrator.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console(highlight=False)


@app.callback()
def main() -> None:
    """RunRepo: Deterministic repository analyzer and local environment orchestrator."""
    pass


def resolve_target_path(
    target_input: str | Path | None,
    refresh: bool = False,
) -> Path:
    """Resolve a local path or remote GitHub reference to a local filesystem directory."""
    if target_input is None:
        return Path(".").resolve()

    from runrepo.repository import RepositoryManager, RepositorySource

    manager = RepositoryManager()
    result = manager.resolve(str(target_input), refresh=refresh)
    if not result.success:
        console.print(f"[bold red]Error:[/bold red] {result.error_message or 'Failed to acquire repository.'}")
        raise typer.Exit(code=1)

    if result.target.source != RepositorySource.LOCAL:
        if result.target.status.value == "CACHED":
            console.print(f"[dim cyan]Using cached repository:[/] [bold]{result.local_path}[/]")
        elif result.target.status.value == "CLONED":
            console.print(f"[dim green]Cloned repository to:[/] [bold]{result.local_path}[/]")

    return result.local_path.resolve()  # type: ignore


@app.command(name="clone")
def clone_command(
    target: Annotated[
        str,
        typer.Argument(
            help="GitHub URL (https://github.com/owner/repo) or shorthand (owner/repo) to clone and cache",
        ),
    ],
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            "-r",
            help="Force re-clone even if repository is already cached locally",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured RepositoryResult JSON (Pydantic serialized)",
        ),
    ] = False,
) -> None:
    """Safely clone and cache a remote GitHub repository."""
    from runrepo.repository import RepositoryManager

    manager = RepositoryManager()
    result = manager.resolve(target, refresh=refresh)

    if json_output:
        typer.echo(result.model_dump_json(indent=2))
    else:
        if result.success:
            console.print(f"[bold green]Successfully acquired repository:[/] {result.local_path}")
        else:
            console.print(f"[bold red]Error:[/bold red] {result.error_message}")
            raise typer.Exit(code=1)


cache_app = typer.Typer(
    name="cache",
    help="Manage cached remote GitHub repositories.",
    no_args_is_help=False,
)
app.add_typer(cache_app, name="cache")


@cache_app.command(name="list")
def cache_list_command(
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured CacheMetadata JSON (Pydantic serialized)",
        ),
    ] = False,
) -> None:
    """List cached repositories, disk usage, and health status."""
    from runrepo.repository import RepositoryManager

    mgr = RepositoryManager()
    meta = mgr.list_cached()

    if json_output:
        typer.echo(meta.model_dump_json(indent=2))
    else:
        if not meta.repositories:
            console.print(f"[dim]No cached repositories found in {meta.cache_dir}[/dim]")
            return

        from rich.table import Table

        table = Table(title="RunRepo Repository Cache")
        table.add_column("Repository", style="bold cyan")
        table.add_column("Size", justify="right")
        table.add_column("Status", justify="center")
        table.add_column("Last Used", style="dim")

        for repo in meta.repositories:
            size_mb = repo.size_bytes / (1024 * 1024)
            status_str = "[green]VALID[/green]" if repo.is_valid else "[red]CORRUPT[/red]"
            table.add_row(
                repo.name,
                f"{size_mb:.1f} MB",
                status_str,
                repo.last_used_at or "Unknown",
            )

        console.print(table)
        total_mb = meta.total_size_bytes / (1024 * 1024)
        console.print(f"\n[bold]Total:[/bold] {meta.total_repositories} repositories ({total_mb:.1f} MB)")


@cache_app.callback(invoke_without_command=True)
def cache_default_command(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured CacheMetadata JSON (Pydantic serialized)",
        ),
    ] = False,
) -> None:
    """List cached repositories, disk usage, and health status."""
    if ctx.invoked_subcommand is not None:
        return
    cache_list_command(json_output=json_output)


@cache_app.command(name="clean")
def cache_clean_command(
    target: Annotated[
        Optional[str],
        typer.Argument(
            help="Specific repository name or slug to remove from cache (e.g. owner/repo)",
        ),
    ] = None,
    days: Annotated[
        Optional[int],
        typer.Option(
            "--days",
            help="Only remove cached repositories older than specified days",
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Automatically approve cache cleanup without interactive prompt",
        ),
    ] = False,
) -> None:
    """Safely purge cached repositories from disk."""
    from runrepo.repository import RepositoryManager

    mgr = RepositoryManager()
    meta = mgr.list_cached()

    if not meta.repositories:
        console.print("[dim]Cache is already empty.[/dim]")
        return

    if not yes:
        confirm = typer.confirm(
            f"Are you sure you want to clean cached repositories in {mgr.cache_dir}?"
        )
        if not confirm:
            console.print("[yellow]Cache cleanup canceled.[/yellow]")
            return

    removed = mgr.clean_cache(target=target, older_than_days=days)
    if removed:
        console.print(f"[bold green]Successfully cleaned {len(removed)} cached repositories:[/bold green]")
        for name in removed:
            console.print(f"  [green]•[/green] {name}")
    else:
        console.print("[dim]No matching cached repositories were found to clean.[/dim]")


@app.command(name="tree")
def tree_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path or GitHub URL/shorthand of repository to inspect tree for",
        ),
    ] = ".",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured MonorepoInfo JSON (Pydantic serialized)",
        ),
    ] = False,
) -> None:
    """Display repository directory and monorepo workspace structure."""
    from runrepo.monorepo import MonorepoDetector

    target_path = resolve_target_path(path)
    detector = MonorepoDetector()
    monorepo_info = detector.detect(target_path)

    if json_output:
        typer.echo(monorepo_info.model_dump_json(indent=2))
    else:
        from rich.tree import Tree

        root_tree = Tree(f"[bold cyan]{target_path.name}[/bold cyan] ({monorepo_info.workspace_type.value})")

        if monorepo_info.packages:
            for pkg in monorepo_info.packages:
                badge = "[green][app][/green]" if pkg.is_application else "[dim][pkg][/dim]"
                node = root_tree.add(f"{badge} [bold]{pkg.name}[/bold] ([dim]{pkg.path}[/dim])")
                if pkg.scripts:
                    scripts_node = node.add("[dim]scripts[/dim]")
                    for s_name, cmd in pkg.scripts.items():
                        scripts_node.add(f"[cyan]{s_name}[/cyan]: {cmd}")
        else:
            root_tree.add("[dim]Single-package repository layout[/dim]")

        console.print(root_tree)


@app.command(name="config")
def config_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path or GitHub URL/shorthand of repository to inspect config for",
        ),
    ] = ".",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured RunRepoConfig JSON (Pydantic serialized)",
        ),
    ] = False,
) -> None:
    """Display user configuration from runrepo.yaml and effective settings."""
    from runrepo.reproducibility import ReproducibilityManager

    target_path = resolve_target_path(path)
    repro_mgr = ReproducibilityManager(target_path)
    config = repro_mgr.load_config()

    if json_output:
        if config:
            typer.echo(config.model_dump_json(indent=2))
        else:
            typer.echo("{}")
    else:
        if config:
            console.print(f"[bold green]Loaded Configuration:[/] {target_path / 'runrepo.yaml'}")
            console.print(f"  • Runtimes: {config.runtimes or 'None'}")
            console.print(f"  • Package Manager: {config.package_manager or 'Detected'}")
            console.print(f"  • Docker: {config.docker}")
            console.print(f"  • Services: {list(config.services.keys()) or 'None'}")
            if config.startup.command:
                console.print(f"  • Startup Override: {config.startup.command}")
        else:
            console.print(f"[dim]No runrepo.yaml found in {target_path}. Using detected defaults.[/dim]")


@app.command(name="lock")
def lock_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path or GitHub URL/shorthand of repository to lock",
        ),
    ] = ".",
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            "-r",
            help="Force refresh and rewrite runrepo.lock even if one already exists",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Simulate lockfile generation without writing to disk",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured RunRepoLock JSON (Pydantic serialized)",
        ),
    ] = False,
) -> None:
    """Generate or refresh a deterministic, secret-free runrepo.lock file."""
    from runrepo.environment import EnvironmentChecker
    from runrepo.planner import ExecutionPlanner
    from runrepo.reproducibility import LockfileManager, ReproducibilityManager

    target_path = resolve_target_path(path)
    repro_mgr = ReproducibilityManager(target_path)
    config = repro_mgr.load_config()

    analyzer = RepositoryAnalyzer()
    project_info = analyzer.analyze(target_path)

    checker = EnvironmentChecker()
    env_state = checker.check_environment(project_info)

    planner = ExecutionPlanner()
    plan = planner.plan(project_info, env_state, config=config)

    lock = repro_mgr.generate_lockfile(project_info, env_state, plan)
    if json_output:
        typer.echo(LockfileManager.format_json(lock))
    elif dry_run:
        console.print("[yellow]Dry-run: generated lockfile in memory[/yellow]")
    else:
        console.print(f"[bold green]Successfully generated lockfile:[/] {target_path / 'runrepo.lock'}")


@app.command(name="analyze")
def analyze_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path or GitHub URL/shorthand of repository to analyze",
        ),
    ] = ".",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured domain model JSON (Pydantic serialized)",
        ),
    ] = False,
    show_evidence: Annotated[
        bool,
        typer.Option(
            "--evidence",
            "-e",
            help="Show granular detection evidence, confidence scores, and source paths",
        ),
    ] = False,
    no_ai: Annotated[
        bool,
        typer.Option(
            "--no-ai",
            help="Disable AI-assisted ambiguity resolution and diagnostics",
        ),
    ] = False,
) -> None:
    """Analyze a repository and produce a structured, explainable ProjectInfo."""
    if no_ai:
        os.environ["RUNREPO_NO_AI"] = "1"

    target_path = resolve_target_path(path)

    analyzer = RepositoryAnalyzer()
    project_info = analyzer.analyze(target_path, enable_ai=not no_ai)

    if json_output:
        # Constraint 6: Serialize the actual structured domain model
        typer.echo(project_info.model_dump_json(indent=2))
    else:
        render_project_analysis(project_info, console=console, show_evidence=show_evidence)


@app.command(name="doctor")
def doctor_command(
    path: Annotated[
        Optional[str],
        typer.Argument(
            help="Optional path or GitHub URL/shorthand to evaluate requirements for",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured EnvironmentState JSON (Pydantic serialized)",
        ),
    ] = False,
) -> None:
    """Inspect local machine environment and evaluate repository requirements."""
    from runrepo.environment import EnvironmentChecker
    from runrepo.ui import render_environment_state

    project_info = None
    if path is not None:
        target_path = resolve_target_path(path)
        analyzer = RepositoryAnalyzer()
        project_info = analyzer.analyze(target_path)

    checker = EnvironmentChecker()
    env_state = checker.check_environment(project_info)

    if json_output:
        typer.echo(env_state.model_dump_json(indent=2))
    else:
        render_environment_state(env_state, console=console)
        if not env_state.is_satisfied:
            from runrepo.diagnostics import DiagnosticsEngine, render_diagnostics_report

            diag_engine = DiagnosticsEngine()
            diagnostics = diag_engine.diagnose_environment(env_state, project_info)
            if diagnostics:
                render_diagnostics_report(diagnostics, console)


@app.command(name="plan")
def plan_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path or GitHub URL/shorthand of repository to plan execution for",
        ),
    ] = ".",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured ExecutionPlan JSON (Pydantic serialized)",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Explicit alias: compute and display the plan without executing it",
        ),
    ] = False,
    no_ai: Annotated[
        bool,
        typer.Option(
            "--no-ai",
            help="Disable AI-assisted ambiguity resolution and diagnostics",
        ),
    ] = False,
) -> None:
    """Generate an ordered, explainable execution plan for a repository."""
    if no_ai:
        os.environ["RUNREPO_NO_AI"] = "1"

    from runrepo.environment import EnvironmentChecker
    from runrepo.planner import ExecutionPlanner
    from runrepo.ui import render_execution_plan

    target_path = resolve_target_path(path)

    from runrepo.reproducibility import ReproducibilityManager
    repro_mgr = ReproducibilityManager(target_path)
    config = repro_mgr.load_config()

    # 1. Repository Facts
    analyzer = RepositoryAnalyzer()
    project_info = analyzer.analyze(target_path, enable_ai=not no_ai)

    # 2. Host Facts
    checker = EnvironmentChecker()
    env_state = checker.check_environment(project_info)

    # 3. Decision Plan
    planner = ExecutionPlanner()
    execution_plan = planner.plan(project_info, env_state, config=config)

    # 4. Check Drift Against runrepo.lock
    diff = repro_mgr.check_drift(project_info, env_state, execution_plan)
    if diff and diff.has_changes:
        execution_plan.warnings.extend(diff.warnings)

    if json_output:
        typer.echo(execution_plan.model_dump_json(indent=2))
    else:
        render_execution_plan(execution_plan, console=console)
        if diff and diff.has_changes:
            console.print("[bold yellow]Environment Drift from runrepo.lock:[/bold yellow]")
            for w in diff.warnings:
                console.print(f"  [yellow]•[/yellow] {w}")


@app.command(name="setup")
def setup_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path or GitHub URL/shorthand of repository to setup and run",
        ),
    ] = ".",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Simulate execution without modifying files or running processes",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Automatically approve actions requiring confirmation",
        ),
    ] = False,
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--non-interactive",
            help="Run without interactive prompts (fails on unapproved confirmation)",
        ),
    ] = False,
    no_ai: Annotated[
        bool,
        typer.Option(
            "--no-ai",
            help="Disable AI-assisted ambiguity resolution and diagnostics",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured ExecutionResult JSON (Pydantic serialized)",
        ),
    ] = False,
) -> None:
    """Analyze, check environment, plan, and safely execute setup for a repository."""
    if no_ai:
        os.environ["RUNREPO_NO_AI"] = "1"

    from runrepo.environment import EnvironmentChecker
    from runrepo.executor import (
        AutoConfirmationHandler,
        ConsoleConfirmationHandler,
        ExecutionEngine,
        NonInteractiveConfirmationHandler,
    )
    from runrepo.planner import ExecutionPlanner
    from runrepo.reproducibility import ReproducibilityManager
    from runrepo.ui import render_execution_plan, render_execution_result

    target_path = resolve_target_path(path)
    repro_mgr = ReproducibilityManager(target_path)
    config = repro_mgr.load_config()

    # 1. Repository Facts
    analyzer = RepositoryAnalyzer()
    project_info = analyzer.analyze(target_path, enable_ai=not no_ai)

    # 2. Host Facts
    checker = EnvironmentChecker()
    env_state = checker.check_environment(project_info)

    # 3. Decision Plan
    planner = ExecutionPlanner()
    plan = planner.plan(project_info, env_state, config=config)

    # 4. Check Drift Against runrepo.lock
    diff = repro_mgr.check_drift(project_info, env_state, plan)
    if diff and diff.has_changes:
        plan.warnings.extend(diff.warnings)

    if not json_output:
        render_execution_plan(plan, console=console)
        if diff and diff.has_changes:
            console.print("[bold yellow]Environment Drift from runrepo.lock:[/bold yellow]")
            for w in diff.warnings:
                console.print(f"  [yellow]•[/yellow] {w}")

    # 4. Confirmation Strategy
    if dry_run or yes:
        confirmation = AutoConfirmationHandler()
    elif non_interactive:
        confirmation = NonInteractiveConfirmationHandler()
    else:
        confirmation = ConsoleConfirmationHandler(console=console)

    # 5. Execution Engine
    engine = ExecutionEngine(confirmation=confirmation, console=console)
    result = engine.execute(plan, dry_run=dry_run)

    if json_output:
        typer.echo(result.model_dump_json(indent=2))
    else:
        render_execution_result(result, console=console)
        if result.status.value in ("FAILED", "BLOCKED"):
            from runrepo.diagnostics import DiagnosticsEngine, render_diagnostics_report

            diag_engine = DiagnosticsEngine()
            diagnostics = diag_engine.diagnose_execution(result, plan=plan)
            if not diagnostics and env_state:
                diagnostics = diag_engine.diagnose_environment(env_state, project_info)
            if diagnostics:
                render_diagnostics_report(diagnostics, console)

    if result.status.value in ("FAILED", "BLOCKED", "CANCELLED"):
        raise typer.Exit(code=1)


@app.command(name="status")
def status_command() -> None:
    """List all tracked background application processes."""
    from runrepo.executor import ProcessManager
    from runrepo.ui import render_process_list

    pm = ProcessManager()
    processes = pm.list_processes()
    render_process_list(processes, console=console)


@app.command(name="stop")
def stop_command(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Optional path to repository whose processes should be stopped",
        ),
    ] = None,
    name: Annotated[
        Optional[str],
        typer.Option(
            "--name",
            "-n",
            help="Optional specific process name to stop",
        ),
    ] = None,
) -> None:
    """Stop running background processes."""
    from runrepo.executor import ProcessManager

    pm = ProcessManager()
    target_path = Path(path).resolve() if path else None
    stopped = pm.stop_process(repo_path=target_path, name=name)

    if stopped:
        for p in stopped:
            console.print(f"[bold green]+ Stopped process:[/bold green] {p.name} (PID: {p.pid})")
    else:
        console.print("[dim]No matching running processes found to stop.[/dim]")


@app.command(name="logs")
def logs_command(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Optional path to repository",
        ),
    ] = None,
    name: Annotated[
        Optional[str],
        typer.Option(
            "--name",
            "-n",
            help="Optional process name",
        ),
    ] = None,
    tail: Annotated[
        int,
        typer.Option(
            "--tail",
            "-t",
            help="Number of lines from end of log file to display",
        ),
    ] = 50,
) -> None:
    """Fetch recent output logs of a running or completed process."""
    from runrepo.executor import ProcessManager

    pm = ProcessManager()
    target_path = Path(path).resolve() if path else None
    logs = pm.get_process_logs(repo_path=target_path, name=name, tail=tail)
    console.print(logs)


@app.command("infra")
def infra_command(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Optional path to repository",
        ),
    ] = None,
) -> None:
    """List RunRepo-managed infrastructure resources (containers, volumes)."""
    from runrepo.services import InfrastructureRegistry
    from runrepo.ui import render_infrastructure_list

    registry = InfrastructureRegistry()
    target_path = Path(path).resolve() if path else None
    resources = registry.list_resources(repo_path=target_path)
    render_infrastructure_list(resources, console)


@app.command("clean")
def clean_command(
    path: Annotated[
        Optional[Path],
        typer.Argument(
            help="Optional path to repository to scope cleanup",
        ),
    ] = None,
    all_resources: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Clean all RunRepo-managed infrastructure across all projects",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Confirm removal without prompting",
        ),
    ] = False,
) -> None:
    """Clean up and remove RunRepo-created Docker containers and volumes."""
    from rich.prompt import Confirm
    from runrepo.executor.process import SystemProcessExecutor
    from runrepo.services import ComposeManager, DockerManager, InfrastructureRegistry
    from runrepo.services.models import ResourceType, ServiceType
    from runrepo.ui import render_infrastructure_list

    registry = InfrastructureRegistry()
    target_path = None if all_resources else (Path(path).resolve() if path else Path.cwd().resolve())

    resources = registry.list_resources(repo_path=target_path)
    if not resources:
        console.print("\n[dim]No RunRepo-managed infrastructure resources found for cleanup.[/dim]\n")
        return

    render_infrastructure_list(resources, console)

    if not yes:
        confirmed = Confirm.ask(
            f"[bold yellow]Remove {len(resources)} RunRepo-managed infrastructure resource(s)?[/bold yellow]",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Cleanup cancelled.[/dim]\n")
            return

    executor = SystemProcessExecutor()
    cleaned_count = 0

    for res in resources:
        if res.service_type == ServiceType.DOCKER_COMPOSE and res.project_path:
            compose_file = ComposeManager.find_compose_file(Path(res.project_path))
            if compose_file:
                ComposeManager.down(Path(res.project_path), executor=executor)

        if res.resource_type == ResourceType.CONTAINER:
            DockerManager.remove_container(res.name or res.id, executor, force=True)
            registry.unregister_resource(res.id)
            cleaned_count += 1
        elif res.resource_type == ResourceType.VOLUME:
            DockerManager.remove_volume(res.name or res.id, executor)
            registry.unregister_resource(res.id)
            cleaned_count += 1

    console.print(f"\n[bold green]Successfully cleaned {cleaned_count} resource(s).[/bold green]\n")


@app.command(name="start")
def start_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path or GitHub URL/shorthand of repository to start",
        ),
    ] = ".",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Simulate startup without modifying files or running processes",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Automatically approve actions requiring confirmation",
        ),
    ] = False,
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--non-interactive",
            help="Run without interactive prompts",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured ExecutionResult JSON",
        ),
    ] = False,
) -> None:
    """Start application and services for a repository."""
    setup_command(
        path=path,
        dry_run=dry_run,
        yes=yes,
        non_interactive=non_interactive,
        json_output=json_output,
    )


@app.command(name="pr")
def pr_command(
    url: Annotated[
        str,
        typer.Argument(
            help="GitHub PR URL (https://github.com/owner/repo/pull/123) or shorthand (owner/repo#123)",
        ),
    ],
    no_tests: Annotated[
        bool,
        typer.Option(
            "--no-tests",
            help="Skip running automated test suites",
        ),
    ] = False,
    no_start: Annotated[
        bool,
        typer.Option(
            "--no-start",
            help="Skip application startup and live endpoint probes",
        ),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            "-r",
            help="Force re-fetch/clone even if cached",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured PRReproductionReport JSON",
        ),
    ] = False,
) -> None:
    """Reproduce, test, and verify a remote GitHub Pull Request locally."""
    from runrepo.reproduce import PullRequestRunner

    runner = PullRequestRunner()
    report = runner.reproduce(
        pr_url=url,
        refresh=refresh,
        run_tests=not no_tests,
        start_app=not no_start,
    )

    if json_output:
        typer.echo(report.model_dump_json(indent=2))
    else:
        console.print(f"\n{report.summary}\n")
        if not report.setup_successful:
            raise typer.Exit(code=1)


@app.command(name="repair")
def repair_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path to repository to repair",
        ),
    ] = ".",
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Automatically execute all remediation actions",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output structured RepairResult JSON",
        ),
    ] = False,
) -> None:
    """Diagnose and autonomously repair broken virtualenvs, port conflicts, stopped Docker daemon, and .env files."""
    target_path = resolve_target_path(path)
    from runrepo.diagnostics.repair import EnvironmentRepairManager

    repair_mgr = EnvironmentRepairManager()
    result = repair_mgr.repair(target_path)

    if json_output:
        typer.echo(result.model_dump_json(indent=2))
    else:
        console.print(f"\n{result.summary}\n")


@app.command(name="export")
def export_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path to repository to export",
        ),
    ] = ".",
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: 'yaml' (runrepo.yaml) or 'lock' (runrepo.lock)",
        ),
    ] = "yaml",
    out: Annotated[
        Optional[Path],
        typer.Option(
            "--out",
            "-o",
            help="Optional output destination filepath",
        ),
    ] = None,
) -> None:
    """Export detected repository facts and environment configuration to runrepo.yaml or runrepo.lock."""
    target_path = resolve_target_path(path)
    from runrepo.reproduce import EnvironmentExporter

    exporter = EnvironmentExporter()
    if format.lower() in ("lock", "json"):
        content = exporter.export_lock(target_path)
    else:
        content = exporter.export_yaml(target_path)

    if out:
        out.write_text(content, encoding="utf-8")
        console.print(f"[bold green]Exported configuration to:[/] {out}")
    else:
        typer.echo(content)


@app.command(name="reproduce")
def reproduce_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path to repository to reproduce",
        ),
    ] = ".",
    lock_file: Annotated[
        Optional[Path],
        typer.Option(
            "--lock-file",
            "-l",
            help="Explicit path to runrepo.lock",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Simulate execution without modifying system",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Automatically approve reproduction steps",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured ExecutionResult JSON",
        ),
    ] = False,
) -> None:
    """Deterministically recreate a project environment from runrepo.lock or runrepo.yaml."""
    target_path = resolve_target_path(path)
    from runrepo.reproduce import EnvironmentReproducer

    reproducer = EnvironmentReproducer()
    success, exec_res, warnings = reproducer.reproduce(target_path, lock_path=lock_file, dry_run=dry_run)

    if warnings:
        console.print("[bold yellow]Reproducibility Warnings / Drift:[/bold yellow]")
        for w in warnings:
            console.print(f"  [yellow]•[/yellow] {w}")

    if json_output and exec_res:
        typer.echo(exec_res.model_dump_json(indent=2))
    elif not json_output and exec_res:
        from runrepo.ui import render_execution_result

        render_execution_result(exec_res, console=console)

    if not success:
        raise typer.Exit(code=1)


@app.command(name="share")
def share_command(
    path: Annotated[
        str,
        typer.Argument(
            help="Path to repository to generate onboarding share guide",
        ),
    ] = ".",
    out_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--out-dir",
            "-o",
            help="Directory to write setup.sh, setup.ps1, and GUIDE.md",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output raw structured ShareSpec JSON",
        ),
    ] = False,
) -> None:
    """Generate human-readable developer onboarding guides and copy-pasteable setup scripts."""
    target_path = resolve_target_path(path)
    from runrepo.reproduce import ShareGenerator

    gen = ShareGenerator()
    spec = gen.generate(target_path)

    if json_output:
        typer.echo(spec.model_dump_json(indent=2))
    else:
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "GUIDE.md").write_text(spec.markdown_guide, encoding="utf-8")
            (out_dir / "setup.sh").write_text(spec.bash_script, encoding="utf-8")
            (out_dir / "setup.ps1").write_text(spec.powershell_script, encoding="utf-8")
            console.print(f"[bold green]Generated onboarding guide and setup scripts in:[/] {out_dir}")
        else:
            console.print(spec.markdown_guide)


if __name__ == "__main__":
    app()



