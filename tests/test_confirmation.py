"""Unit tests for ConfirmationHandler implementations."""

from runrepo.executor.confirmation import (
    AutoConfirmationHandler,
    ConsoleConfirmationHandler,
    NonInteractiveConfirmationHandler,
)
from runrepo.planner.models import ActionType, PlanStep, RiskLevel


def _make_step(risk: RiskLevel, is_blocked: bool = False) -> PlanStep:
    return PlanStep(
        id="test-step",
        description="Test step",
        action_type=ActionType.INSTALL_DEPENDENCIES,
        command=["pnpm", "install"],
        risk=risk,
        reason="test reason",
        is_blocked=is_blocked,
    )


def test_auto_confirmation_handler():
    handler = AutoConfirmationHandler(allow_dangerous=False)

    assert handler.confirm(_make_step(RiskLevel.SAFE)) is True
    assert handler.confirm(_make_step(RiskLevel.REQUIRES_CONFIRMATION)) is True
    assert handler.confirm(_make_step(RiskLevel.DANGEROUS)) is False
    assert handler.confirm(_make_step(RiskLevel.BLOCKED, is_blocked=True)) is False

    handler_dangerous = AutoConfirmationHandler(allow_dangerous=True)
    assert handler_dangerous.confirm(_make_step(RiskLevel.DANGEROUS)) is True


def test_non_interactive_confirmation_handler():
    handler = NonInteractiveConfirmationHandler()

    assert handler.confirm(_make_step(RiskLevel.SAFE)) is True
    assert handler.confirm(_make_step(RiskLevel.REQUIRES_CONFIRMATION)) is False
    assert handler.confirm(_make_step(RiskLevel.DANGEROUS)) is False
    assert handler.confirm(_make_step(RiskLevel.BLOCKED, is_blocked=True)) is False


def test_console_confirmation_handler_safe_and_blocked():
    handler = ConsoleConfirmationHandler()
    assert handler.confirm(_make_step(RiskLevel.SAFE)) is True
    assert handler.confirm(_make_step(RiskLevel.BLOCKED, is_blocked=True)) is False
