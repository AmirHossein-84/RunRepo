"""Rich terminal formatting for diagnostic failure reports and actionable suggestions."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from runrepo.diagnostics.models import Diagnostic, DiagnosticCategory, DiagnosticSeverity


def _get_category_badge(category: DiagnosticCategory) -> str:
    """Format category badge with distinctive styling."""
    color_map = {
        DiagnosticCategory.ENVIRONMENT: "cyan",
        DiagnosticCategory.DEPENDENCY: "magenta",
        DiagnosticCategory.PROCESS: "yellow",
        DiagnosticCategory.NETWORK: "blue",
        DiagnosticCategory.SERVICE: "bright_magenta",
        DiagnosticCategory.CONFIGURATION: "bright_yellow",
        DiagnosticCategory.PERMISSION: "bright_red",
        DiagnosticCategory.UNKNOWN: "dim white",
    }
    color = color_map.get(category, "white")
    return f"[{color}]● {category.value}[/{color}]"


def _get_severity_style(severity: DiagnosticSeverity) -> str:
    """Map severity to border/title style."""
    if severity == DiagnosticSeverity.CRITICAL:
        return "bold red"
    if severity == DiagnosticSeverity.ERROR:
        return "red"
    if severity == DiagnosticSeverity.WARNING:
        return "yellow"
    return "cyan"


def render_diagnostics_report(diagnostics: list[Diagnostic], console: Console) -> None:
    """Render structured diagnostic cards with root cause and actionable next steps."""
    if not diagnostics:
        return

    console.print()
    console.rule("[bold red]RunRepo Diagnostic Failure Report[/bold red]")
    console.print()

    for idx, diag in enumerate(diagnostics, start=1):
        content_parts: list[str] = []

        # 1. Category & Affected Step Header
        category_badge = _get_category_badge(diag.category)
        step_info = f"[dim]Affected Step: {diag.affected_step_id}[/dim]" if diag.affected_step_id else ""
        header = f"{category_badge}  {step_info}".strip()
        content_parts.append(header)
        content_parts.append("")

        # 2. Explanation
        content_parts.append(f"[bold white]Root Cause:[/bold white]\n{diag.explanation}")

        # 3. Log Excerpt (Pre-redacted)
        if diag.stderr_excerpt or diag.stdout_excerpt:
            excerpt = diag.stderr_excerpt or diag.stdout_excerpt
            content_parts.append("")
            content_parts.append("[bold white]Relevant Output Excerpt (Secrets Redacted):[/bold white]")
            content_parts.append(f"[dim]{excerpt}[/dim]")

        # 4. Actionable Suggestions
        if diag.suggested_actions:
            content_parts.append("")
            content_parts.append("[bold green]Suggested Next Actions:[/bold green]")
            for action in diag.suggested_actions:
                content_parts.append(f"  • [bold]{action.title}[/bold]: {action.description}")
                if action.command:
                    content_parts.append(f"    [dim cyan]> {action.command}[/dim cyan]")

        card_text = "\n".join(content_parts)
        border_style = _get_severity_style(diag.severity)

        panel = Panel(
            card_text,
            title=f"[bold]{idx}. {diag.title}[/bold]",
            border_style=border_style,
            expand=True,
            padding=(1, 2),
        )
        console.print(panel)
        console.print()
