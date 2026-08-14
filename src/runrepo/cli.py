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


@app.command(name="analyze")
def analyze_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the local repository directory to analyze",
        ),
    ] = Path("."),
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
) -> None:
    """Analyze a local repository and produce a structured, explainable ProjectInfo."""
    target_path = Path(path).resolve()
    if not target_path.exists():
        console.print(f"[bold red]Error:[/bold red] Directory '{target_path}' does not exist.")
        raise typer.Exit(code=1)

    if not target_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] Path '{target_path}' is not a directory.")
        raise typer.Exit(code=1)

    analyzer = RepositoryAnalyzer()
    project_info = analyzer.analyze(target_path)

    if json_output:
        # Constraint 6: Serialize the actual structured domain model
        typer.echo(project_info.model_dump_json(indent=2))
    else:
        render_project_analysis(project_info, console=console, show_evidence=show_evidence)


@app.command(name="doctor")
def doctor_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Optional path to local repository directory to evaluate requirements for",
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
        target_path = Path(path).resolve()
        if not target_path.exists():
            console.print(f"[bold red]Error:[/bold red] Directory '{target_path}' does not exist.")
            raise typer.Exit(code=1)
        if not target_path.is_dir():
            console.print(f"[bold red]Error:[/bold red] Path '{target_path}' is not a directory.")
            raise typer.Exit(code=1)

        analyzer = RepositoryAnalyzer()
        project_info = analyzer.analyze(target_path)

    checker = EnvironmentChecker()
    env_state = checker.check_environment(project_info)

    if json_output:
        typer.echo(env_state.model_dump_json(indent=2))
    else:
        render_environment_state(env_state, console=console)


@app.command(name="plan")
def plan_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the local repository directory to plan execution for",
        ),
    ] = Path("."),
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
) -> None:
    """Generate an ordered, explainable execution plan for a repository."""
    from runrepo.environment import EnvironmentChecker
    from runrepo.planner import ExecutionPlanner
    from runrepo.ui import render_execution_plan

    target_path = Path(path).resolve()
    if not target_path.exists():
        console.print(f"[bold red]Error:[/bold red] Directory '{target_path}' does not exist.")
        raise typer.Exit(code=1)
    if not target_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] Path '{target_path}' is not a directory.")
        raise typer.Exit(code=1)

    # 1. Repository Facts
    analyzer = RepositoryAnalyzer()
    project_info = analyzer.analyze(target_path)

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


if __name__ == "__main__":
    app()


