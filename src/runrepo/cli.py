import sys
from pathlib import Path
from typing import Annotated

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
    """RunRepo main CLI entrypoint."""
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
        str | None,
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

    # 1. Repository Facts
    analyzer = RepositoryAnalyzer()
    project_info = analyzer.analyze(target_path, enable_ai=not no_ai)

    # 2. Host Facts
    checker = EnvironmentChecker()
    env_state = checker.check_environment(project_info)

    # 3. Decision Plan
    planner = ExecutionPlanner()
    execution_plan = planner.plan(project_info, env_state)

    if json_output:
        typer.echo(execution_plan.model_dump_json(indent=2))
    else:
        render_execution_plan(execution_plan, console=console)


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
    from runrepo.ui import render_execution_plan, render_execution_result

    target_path = resolve_target_path(path)

    # 1. Repository Facts
    analyzer = RepositoryAnalyzer()
    project_info = analyzer.analyze(target_path, enable_ai=not no_ai)

    # 2. Host Facts
    checker = EnvironmentChecker()
    env_state = checker.check_environment(project_info)

    # 3. Decision Plan
    planner = ExecutionPlanner()
    plan = planner.plan(project_info, env_state)

    if not json_output:
        render_execution_plan(plan, console=console)

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
        Path | None,
        typer.Argument(
            help="Optional path to repository whose processes should be stopped",
        ),
    ] = None,
    name: Annotated[
        str | None,
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
        Path | None,
        typer.Argument(
            help="Optional path to repository",
        ),
    ] = None,
    name: Annotated[
        str | None,
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
        Path | None,
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
        Path | None,
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


if __name__ == "__main__":
    app()



