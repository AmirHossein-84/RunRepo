"""Confirmation subsystem enforcing safety gates, user approval, and non-interactive policies."""

from abc import ABC, abstractmethod
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from runrepo.planner.models import PlanStep, RiskLevel


class ConfirmationHandler(ABC):
    """Abstract interface for step execution confirmation."""

    @abstractmethod
    def confirm(self, step: PlanStep, dry_run: bool = False) -> bool:
        """Evaluate whether a plan step is approved for execution."""
        ...


class ConsoleConfirmationHandler(ConfirmationHandler):
    """Interactive terminal confirmation handler using Rich prompts."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def confirm(self, step: PlanStep, dry_run: bool = False) -> bool:
        if step.is_blocked or step.risk == RiskLevel.BLOCKED:
            self.console.print(f"[bold red]Cannot execute blocked step '{step.id}': {step.reason}[/bold red]")
            return False

        if step.risk == RiskLevel.SAFE or step.is_satisfied:
            return True

        # Display confirmation panel
        cmd_str = " ".join(step.command) if step.command else step.action_type.value
        cwd_str = f" in {step.cwd}" if step.cwd else ""
        panel_content = (
            f"[bold cyan]Step:[/bold cyan] {step.id}\n"
            f"[bold cyan]Action:[/bold cyan] {cmd_str}{cwd_str}\n"
            f"[bold cyan]Risk Level:[/bold cyan] [yellow]{step.risk.value}[/yellow]\n"
            f"[bold cyan]Reason:[/bold cyan] {step.reason}"
        )

        if step.risk == RiskLevel.DANGEROUS:
            self.console.print(
                Panel(
                    panel_content,
                    title="[bold red]DANGEROUS ACTION CONFIRMATION[/bold red]",
                    border_style="red",
                )
            )
            response = Prompt.ask(
                "[bold red]To proceed with this dangerous action, type 'I UNDERSTAND'[/bold red]"
            )
            return response.strip() == "I UNDERSTAND"

        if step.risk == RiskLevel.REQUIRES_CONFIRMATION:
            self.console.print(
                Panel(
                    panel_content,
                    title="[bold yellow]Action Requires Confirmation[/bold yellow]",
                    border_style="yellow",
                )
            )
            return Confirm.ask("[bold]Proceed with this step?[/bold]", default=True)

        return True


class AutoConfirmationHandler(ConfirmationHandler):
    """Non-interactive handler used when --yes is supplied."""

    def __init__(self, allow_dangerous: bool = False) -> None:
        self.allow_dangerous = allow_dangerous

    def confirm(self, step: PlanStep, dry_run: bool = False) -> bool:
        if step.is_blocked or step.risk == RiskLevel.BLOCKED:
            return False
        if step.risk == RiskLevel.SAFE or step.is_satisfied:
            return True
        if step.risk == RiskLevel.REQUIRES_CONFIRMATION:
            return True
        if step.risk == RiskLevel.DANGEROUS:
            return self.allow_dangerous
        return True


class NonInteractiveConfirmationHandler(ConfirmationHandler):
    """Strict non-interactive handler for CI/automated environments."""

    def confirm(self, step: PlanStep, dry_run: bool = False) -> bool:
        if step.is_blocked or step.risk == RiskLevel.BLOCKED:
            return False
        if step.risk == RiskLevel.SAFE or step.is_satisfied:
            return True
        # Cannot confirm interactive steps in non-interactive mode
        return False
