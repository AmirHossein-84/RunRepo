"""Diagnostics subsystem package exports."""

from runrepo.diagnostics.diagnostics import DiagnosticsEngine
from runrepo.diagnostics.formatters import render_diagnostics_report
from runrepo.diagnostics.models import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticSeverity,
    SuggestedAction,
)
from runrepo.diagnostics.rules import (
    DEFAULT_DIAGNOSTIC_RULES,
    DependencyFailureRule,
    DiagnosticRule,
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

__all__ = [
    "Diagnostic",
    "DiagnosticSeverity",
    "DiagnosticCategory",
    "SuggestedAction",
    "DiagnosticRule",
    "DEFAULT_DIAGNOSTIC_RULES",
    "PermissionDeniedRule",
    "PortConflictRule",
    "DockerUnavailableRule",
    "MissingCommandRule",
    "MissingEnvVarRule",
    "VersionMismatchRule",
    "DependencyFailureRule",
    "NetworkTimeoutRule",
    "ProcessCrashRule",
    "UnknownFailureRule",
    "DiagnosticsEngine",
    "render_diagnostics_report",
]
