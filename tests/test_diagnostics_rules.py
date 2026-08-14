"""Unit tests for deterministic failure diagnostic rules and priority ordering."""

from runrepo.diagnostics.models import DiagnosticCategory
from runrepo.diagnostics.rules import (
    DEFAULT_DIAGNOSTIC_RULES,
    DependencyFailureRule,
    DockerUnavailableRule,
    MissingCommandRule,
    MissingEnvVarRule,
    NetworkTimeoutRule,
    PermissionDeniedRule,
    PortConflictRule,
    ProcessCrashRule,
    UnknownFailureRule,
    VersionMismatchRule,
)
from runrepo.executor.models import StepExecutionResult
from runrepo.planner.models import ActionType, PlanStep, RiskLevel


def test_permission_denied_rule():
    rule = PermissionDeniedRule()
    step_res = StepExecutionResult(step_id="install-deps", exit_code=1, stderr="npm ERR! code EACCES: permission denied")
    diag = rule.match(None, step_res, None, "npm ERR! code EACCES: permission denied", None, step_res.stderr)
    assert diag is not None
    assert diag.category == DiagnosticCategory.PERMISSION
    assert "Permission" in diag.title


def test_port_conflict_rule():
    rule = PortConflictRule()
    step_res = StepExecutionResult(step_id="start-app", exit_code=1, stderr="Error: listen EADDRINUSE: address already in use :::3000")
    diag = rule.match(None, step_res, None, step_res.stderr, None, step_res.stderr)
    assert diag is not None
    assert diag.category == DiagnosticCategory.NETWORK
    assert "Port Conflict" in diag.title
    assert "3000" in diag.title


def test_docker_unavailable_rule():
    rule = DockerUnavailableRule()
    step_res = StepExecutionResult(step_id="start-service", exit_code=1, stderr="docker: error response from daemon: cannot connect to the docker daemon")
    diag = rule.match(None, step_res, None, step_res.stderr, None, step_res.stderr)
    assert diag is not None
    assert diag.category == DiagnosticCategory.SERVICE
    assert "Docker" in diag.title


def test_missing_command_rule():
    rule = MissingCommandRule()
    step = PlanStep(
        id="verify-runtime:node",
        description="Verify Node",
        action_type=ActionType.VERIFY_RUNTIME,
        command=["pnpm", "--version"],
        risk=RiskLevel.SAFE,
        reason="Verify",
    )
    step_res = StepExecutionResult(step_id="verify-runtime:node", exit_code=1, stderr="'pnpm' is not recognized as an internal or external command")
    diag = rule.match(step, step_res, None, step_res.stderr, None, step_res.stderr)
    assert diag is not None
    assert diag.category == DiagnosticCategory.DEPENDENCY
    assert "Missing" in diag.title


def test_missing_env_var_rule():
    rule = MissingEnvVarRule()
    step_res = StepExecutionResult(step_id="start-app", exit_code=1, stderr="KeyError: 'DATABASE_URL'")
    diag = rule.match(None, step_res, None, step_res.stderr, None, step_res.stderr)
    assert diag is not None
    assert diag.category == DiagnosticCategory.CONFIGURATION
    assert "Environment Configuration" in diag.title


def test_dependency_failure_rule():
    rule = DependencyFailureRule()
    step_res = StepExecutionResult(step_id="install-deps", exit_code=1, stderr="npm ERR! code ERESOLVE could not solve dependencies")
    diag = rule.match(None, step_res, None, step_res.stderr, None, step_res.stderr)
    assert diag is not None
    assert diag.category == DiagnosticCategory.DEPENDENCY


def test_rule_priority_conflict_resolution():
    # An error containing both "permission denied" and "npm err!" should trigger PermissionDenied (priority 100) first
    combined = "npm ERR! code EACCES: permission denied, mkdir '/usr/local/lib/node_modules'"
    step_res = StepExecutionResult(step_id="install-deps", exit_code=1, stderr=combined)

    sorted_rules = sorted(DEFAULT_DIAGNOSTIC_RULES, key=lambda r: r.priority, reverse=True)
    matched = None
    for r in sorted_rules:
        matched = r.match(None, step_res, None, combined, None, combined)
        if matched:
            break

    assert matched is not None
    assert matched.category == DiagnosticCategory.PERMISSION
