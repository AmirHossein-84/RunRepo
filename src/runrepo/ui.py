"""Rich UI formatting and console presentation for RunRepo analysis."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from runrepo.models import Confidence, ProjectInfo


def render_project_analysis(project: ProjectInfo, console: Console, show_evidence: bool = False) -> None:
    """Render a clean, readable Rich presentation of ProjectInfo."""
    console.print()
    console.rule("[bold cyan]RunRepo Analysis[/bold cyan]")
    console.print()

    # 1. Repository Info Panel
    repo_table = Table.grid(padding=(0, 2))
    repo_table.add_column("Key", style="bold")
    repo_table.add_column("Value")

    repo_table.add_row("Path:", f"[white]{project.path}[/white]")
    repo_table.add_row("Project Name:", f"[bold white]{project.name}[/bold white]")
    repo_table.add_row("Project Type:", f"[green]{project.project_type.value}[/green]")
    repo_table.add_row("Monorepo:", "[yellow]yes[/yellow]" if project.is_monorepo else "no")

    if project.languages:
        repo_table.add_row(
            "Languages:",
            ", ".join(f"[bold green]+ {lang}[/bold green]" for lang in project.languages),
        )

    console.print(Panel(repo_table, title="[bold]Repository Overview[/bold]", border_style="cyan"))

    # 2. Runtimes & Package Managers Table
    rt_table = Table(title="Runtimes & Package Managers", expand=True, border_style="dim")
    rt_table.add_column("Type", style="bold cyan", width=16)
    rt_table.add_column("Name", style="bold white", width=16)
    rt_table.add_column("Version", style="green", width=18)
    rt_table.add_column("Primary Evidence", style="dim")

    for rt in project.runtimes:
        ev_str = (
            f"{rt.evidence[0].source} ({rt.evidence[0].detail})"
            if rt.evidence and rt.evidence[0].detail
            else (rt.evidence[0].source if rt.evidence else "-")
        )
        rt_table.add_row("Runtime", rt.name, rt.version or "[dim]any[/dim]", ev_str)

    for pm in project.package_managers:
        ev_str = pm.lockfile or (pm.evidence[0].source if pm.evidence else "-")
        rt_table.add_row("Package Manager", pm.name, pm.version or "[dim]latest/system[/dim]", ev_str)

    if project.runtimes or project.package_managers:
        console.print(rt_table)
        console.print()

    # 3. Frameworks
    if project.frameworks:
        fw_table = Table(title="Detected Frameworks", expand=True, border_style="dim")
        fw_table.add_column("Framework", style="bold magenta", width=20)
        fw_table.add_column("Category", style="cyan", width=18)
        fw_table.add_column("Version", style="green", width=16)
        fw_table.add_column("Source", style="dim")

        for fw in project.frameworks:
            src = fw.evidence[0].path or fw.evidence[0].source if fw.evidence else "-"
            fw_table.add_row(fw.name, fw.category.value, fw.version or "[dim]unknown[/dim]", src)

        console.print(fw_table)
        console.print()

    # 4. Infrastructure (Databases, Services, Docker)
    has_infra = (
        bool(project.databases)
        or bool(project.services)
        or project.docker.has_dockerfile
        or bool(project.docker.compose_files)
    )

    if has_infra:
        infra_table = Table(title="Infrastructure & Services", expand=True, border_style="dim")
        infra_table.add_column("Component", style="bold yellow", width=18)
        infra_table.add_column("Details", style="white", width=28)
        infra_table.add_column("Source", style="dim")

        if project.docker.has_dockerfile:
            infra_table.add_row("Dockerfile", ", ".join(project.docker.dockerfiles), "Dockerfile")
        for cf in project.docker.compose_files:
            srv_names = ", ".join(s.name for s in project.docker.compose_services)
            infra_table.add_row("Docker Compose", f"Services: {srv_names or 'defined'}", cf)

        for db in project.databases:
            det = f"ORM: {db.orm}" if db.orm else "Database"
            if db.connection_var:
                det += f" ({db.connection_var})"
            src = db.evidence[0].path or db.evidence[0].source if db.evidence else "-"
            infra_table.add_row(f"Database ({db.name.value})", det, src)

        for srv in project.services:
            src = srv.evidence[0].path or srv.evidence[0].source if srv.evidence else "-"
            det = f"Port: {srv.port}" if srv.port else (srv.service_type or "Service")
            infra_table.add_row(f"Service ({srv.name})", det, src)

        console.print(infra_table)
        console.print()

    # 5. Environment Variables
    if project.environment_variables:
        env_table = Table(title="Environment Variables", expand=True, border_style="dim")
        env_table.add_column("Variable", style="bold white", width=24)
        env_table.add_column("Status", width=14)
        env_table.add_column("Category", style="cyan", width=18)
        env_table.add_column("Default / Description", style="dim")

        for ev in project.environment_variables:
            status = "[bold red]required[/bold red]" if ev.is_required else "[green]optional[/green]"
            desc = ev.description or (f"default: {ev.default_value}" if ev.default_value else "-")
            env_table.add_row(ev.name, status, ev.category.value, desc)

        console.print(env_table)
        console.print()

    # 6. Scripts & Entrypoints
    if project.scripts or project.entrypoints:
        sc_table = Table(title="Scripts & Entrypoints", expand=True, border_style="dim")
        sc_table.add_column("Name", style="bold green", width=18)
        sc_table.add_column("Command / Target", style="white")

        for ep in project.entrypoints:
            sc_table.add_row(f"[cyan]entrypoint[/cyan]", ep)
        for sc in project.scripts:
            sc_table.add_row(sc.name, sc.command)

        console.print(sc_table)
        console.print()

    # 7. Subprojects / Polyglot breakdown
    if project.subprojects:
        sub_table = Table(title="Subprojects & Workspaces", expand=True, border_style="dim")
        sub_table.add_column("Subproject", style="bold cyan", width=16)
        sub_table.add_column("Path", style="yellow", width=18)
        sub_table.add_column("Languages", style="green", width=18)
        sub_table.add_column("Frameworks / Details", style="white")

        for sp in project.subprojects:
            fw_str = ", ".join(f.name for f in sp.frameworks) or "-"
            sub_table.add_row(sp.name, sp.path, ", ".join(sp.languages), f"Frameworks: {fw_str}")

        console.print(sub_table)
        console.print()

    # 8. Warnings (e.g. malformed files)
    if project.warnings:
        warn_panel = Tree("[bold red]Analysis Warnings[/bold red]")
        for w in project.warnings:
            warn_panel.add(f"[yellow]{w.file_path}[/yellow]: {w.message} [dim]({w.code})[/dim]")
        console.print(Panel(warn_panel, border_style="red"))
        console.print()

    # 9. Evidence Breakdown (--evidence flag)
    if show_evidence:
        console.rule("[bold magenta]Detection Evidence Breakdown[/bold magenta]")
        tree = Tree(f"[bold]{project.name}[/bold]")

        if project.runtimes:
            rt_branch = tree.add("[bold cyan]Runtimes[/bold cyan]")
            for rt in project.runtimes:
                sub = rt_branch.add(f"{rt.name} (version: {rt.version or 'any'})")
                for ev in rt.evidence:
                    sub.add(f"[dim]Source:[/dim] {ev.source} | [dim]Detail:[/dim] {ev.detail or '-'} | [dim]Confidence:[/dim] {ev.confidence.value} | [dim]Path:[/dim] {ev.path or '-'}")

        if project.package_managers:
            pm_branch = tree.add("[bold cyan]Package Managers[/bold cyan]")
            for pm in project.package_managers:
                sub = pm_branch.add(f"{pm.name} (lockfile: {pm.lockfile or 'none'})")
                for ev in pm.evidence:
                    sub.add(f"[dim]Source:[/dim] {ev.source} | [dim]Detail:[/dim] {ev.detail or '-'} | [dim]Confidence:[/dim] {ev.confidence.value} | [dim]Path:[/dim] {ev.path or '-'}")

        if project.frameworks:
            fw_branch = tree.add("[bold magenta]Frameworks[/bold magenta]")
            for fw in project.frameworks:
                sub = fw_branch.add(f"{fw.name} ({fw.category.value})")
                for ev in fw.evidence:
                    sub.add(f"[dim]Source:[/dim] {ev.source} | [dim]Detail:[/dim] {ev.detail or '-'} | [dim]Confidence:[/dim] {ev.confidence.value} | [dim]Path:[/dim] {ev.path or '-'}")

        if project.databases:
            db_branch = tree.add("[bold yellow]Databases[/bold yellow]")
            for db in project.databases:
                sub = db_branch.add(f"{db.name.value} (ORM: {db.orm or 'none'})")
                for ev in db.evidence:
                    sub.add(f"[dim]Source:[/dim] {ev.source} | [dim]Detail:[/dim] {ev.detail or '-'} | [dim]Confidence:[/dim] {ev.confidence.value} | [dim]Path:[/dim] {ev.path or '-'}")

        if project.docker.evidence:
            dk_branch = tree.add("[bold blue]Docker[/bold blue]")
            for ev in project.docker.evidence:
                dk_branch.add(f"[dim]Source:[/dim] {ev.source} | [dim]Detail:[/dim] {ev.detail or '-'} | [dim]Confidence:[/dim] {ev.confidence.value} | [dim]Path:[/dim] {ev.path or '-'}")

        console.print(tree)
        console.print()


def render_environment_state(env_state, console: Console) -> None:
    """Render a clean, readable Rich presentation of EnvironmentState."""
    console.print()
    console.rule("[bold cyan]RunRepo Environment Check (Doctor)[/bold cyan]")
    console.print()

    # 1. Platform Summary Panel
    platform_table = Table.grid(padding=(0, 2))
    platform_table.add_column("Key", style="bold")
    platform_table.add_column("Value")

    platform_table.add_row("Platform:", f"[white]{env_state.platform}[/white]")
    platform_table.add_row("Architecture:", f"[white]{env_state.architecture}[/white]")

    if env_state.is_satisfied:
        satisfaction_text = "[bold green]+ All required environment capabilities are satisfied[/bold green]"
    else:
        issues = []
        if env_state.missing_checks:
            issues.append(f"Missing: {', '.join(env_state.missing_checks)}")
        if env_state.wrong_version_checks:
            issues.append(f"Wrong Version: {', '.join(env_state.wrong_version_checks)}")
        if env_state.broken_checks:
            issues.append(f"Broken: {', '.join(env_state.broken_checks)}")
        satisfaction_text = f"[bold red]- Missing or incompatible requirements: {'; '.join(issues)}[/bold red]"

    platform_table.add_row("Readiness:", satisfaction_text)
    console.print(Panel(platform_table, title="[bold]Host System Overview[/bold]", border_style="cyan"))
    console.print()

    # 2. Environment Checks Table
    table = Table(title="Environment Capabilities & Status", expand=True, border_style="dim")
    table.add_column("Capability", style="bold cyan", width=16)
    table.add_column("Required", width=12)
    table.add_column("Required Ver", style="magenta", width=15)
    table.add_column("Installed Ver", style="white", width=15)
    table.add_column("Status", width=18)
    table.add_column("Diagnostic Details", style="dim")

    for chk in env_state.checks:
        req_str = "[bold yellow]required[/bold yellow]" if chk.required else "[dim]optional[/dim]"
        req_ver_str = chk.required_version or "-"
        inst_ver_str = chk.installed_version or "-"

        status_str = chk.status.value
        if chk.status.value == "OK":
            status_str = "[bold green]+ OK[/bold green]"
        elif chk.status.value == "MISSING":
            status_str = "[bold red]- MISSING[/bold red]" if chk.required else "[dim]MISSING[/dim]"
        elif chk.status.value == "WRONG_VERSION":
            status_str = "[bold yellow]! WRONG_VERSION[/bold yellow]"
        elif chk.status.value == "BROKEN":
            status_str = "[bold red]X BROKEN[/bold red]"
        elif chk.status.value == "UNKNOWN":
            status_str = "[dim]? UNKNOWN[/dim]"

        details_str = chk.details or (chk.executable_path if chk.executable_path else "-")
        table.add_row(chk.name, req_str, req_ver_str, inst_ver_str, status_str, details_str)

    console.print(table)
    console.print()


def render_execution_plan(plan, console: Console) -> None:
    """Render a clean, readable Rich presentation of an ExecutionPlan."""
    console.print()
    console.rule("[bold cyan]RunRepo Execution Plan[/bold cyan]")
    console.print()

    # 1. Overview Panel
    overview_table = Table.grid(padding=(0, 2))
    overview_table.add_column("Key", style="bold")
    overview_table.add_column("Value")

    overview_table.add_row("Repository:", f"[white]{plan.repository_path}[/white]")
    overview_table.add_row("Project Name:", f"[bold white]{plan.project_info.name}[/bold white]")
    overview_table.add_row("Project Type:", f"[green]{plan.project_info.project_type.value}[/green]")

    status_badge = plan.status.value
    if plan.status.value == "READY":
        status_badge = "[bold green]READY[/bold green]"
    elif plan.status.value == "NEEDS_CONFIRMATION":
        status_badge = "[bold yellow]NEEDS_CONFIRMATION[/bold yellow]"
    elif plan.status.value == "NEEDS_INPUT":
        status_badge = "[bold cyan]NEEDS_INPUT[/bold cyan]"
    elif plan.status.value == "BLOCKED":
        status_badge = "[bold red]BLOCKED[/bold red]"

    overview_table.add_row("Plan Status:", status_badge)
    console.print(Panel(overview_table, title="[bold]Plan Overview[/bold]", border_style="cyan"))
    console.print()

    # 2. Blocking / Input Alerts
    if plan.blocking_reasons:
        b_text = "\n".join(f"[bold red]- {r}[/bold red]" for r in plan.blocking_reasons)
        console.print(Panel(b_text, title="[bold red]Blocking Reasons (Action Required)[/bold red]", border_style="red"))
        console.print()

    if plan.input_reasons:
        i_text = "\n".join(f"[bold cyan]? {r}[/bold cyan]" for r in plan.input_reasons)
        console.print(Panel(i_text, title="[bold cyan]Required User Inputs / Disambiguation[/bold cyan]", border_style="cyan"))
        console.print()

    # 3. Ordered Steps Table
    table = Table(title="Planned Execution Steps (Topologically Ordered)", expand=True, border_style="dim")
    table.add_column("#", style="bold white", width=4)
    table.add_column("Step ID", style="bold cyan", width=26)
    table.add_column("Action / Command", style="white", width=30)
    table.add_column("Prerequisites", style="dim", width=22)
    table.add_column("Risk", width=22)
    table.add_column("Justification", style="dim")

    for i, step in enumerate(plan.steps, start=1):
        if step.command:
            cmd_display = " ".join(step.command)
            if step.cwd:
                cmd_display += f" [dim](in {step.cwd})[/dim]"
        elif step.is_satisfied:
            cmd_display = "[bold green]+ Already satisfied[/bold green]"
        elif step.is_blocked:
            cmd_display = "[bold red]- Blocked[/bold red]"
        else:
            cmd_display = f"[cyan]{step.action_type.value}[/cyan]"

        deps_str = ", ".join(step.depends_on) if step.depends_on else "-"

        risk_str = step.risk.value
        if step.risk.value == "SAFE":
            risk_str = "[bold green]SAFE[/bold green]"
        elif step.risk.value == "REQUIRES_CONFIRMATION":
            risk_str = "[bold yellow]REQUIRES_CONFIRMATION[/bold yellow]"
        elif step.risk.value == "BLOCKED":
            risk_str = "[bold red]BLOCKED[/bold red]"
        elif step.risk.value == "DANGEROUS":
            risk_str = "[bold red]DANGEROUS[/bold red]"

        table.add_row(
            str(i),
            step.id,
            cmd_display,
            deps_str,
            risk_str,
            step.reason,
        )

    console.print(table)
    console.print()


