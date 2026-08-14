"""Deterministic environment variable requirement detector integrating the env subsystem."""

from pathlib import Path
from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.env.detector import EnvDetector
from runrepo.env.models import EnvClassification
from runrepo.models import (
    Confidence,
    DetectionEvidence,
    EnvVarCategory,
    EnvironmentVariable,
)


def _to_env_var_category(classification: EnvClassification) -> EnvVarCategory:
    """Map EnvClassification to model EnvVarCategory."""
    if classification == EnvClassification.EXTERNAL_SERVICE:
        return EnvVarCategory.EXTERNAL_SERVICE
    if classification == EnvClassification.LOCAL_DEFAULT:
        return EnvVarCategory.LOCAL_DEFAULT
    if classification == EnvClassification.AUTO_GENERATABLE:
        return EnvVarCategory.SECRET
    return EnvVarCategory.GENERAL


class EnvironmentDetector(BaseDetector):
    """Detects environment variable requirements across .env files, Compose, and code entrypoints."""

    @property
    def name(self) -> str:
        return "environment"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        # Run multi-source deterministic detection
        reqs = EnvDetector.detect_project_requirements(
            root_path=context.root_path,
        )

        for req in reqs:
            evidence = [
                DetectionEvidence(
                    source=req.source,
                    detail=f"{req.name}={req.default_value}" if req.default_value else req.name,
                    confidence=Confidence.HIGH,
                    path=req.source,
                )
            ]

            category = _to_env_var_category(req.classification)
            if "DATABASE" in req.name.upper() or "POSTGRES" in req.name.upper():
                category = EnvVarCategory.DATABASE
            elif req.is_secret:
                category = EnvVarCategory.SECRET

            result.environment_variables.append(
                EnvironmentVariable(
                    name=req.name,
                    description=req.description,
                    default_value=req.default_value,
                    is_required=req.is_required,
                    category=category,
                    evidence=evidence,
                )
            )

        return result
