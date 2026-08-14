"""Detection evidence models for explainable repository analysis."""

from enum import StrEnum
from pydantic import BaseModel, Field


class Confidence(StrEnum):
    """Confidence level of a detection fact."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class DetectionEvidence(BaseModel):
    """Structured evidence detailing why a particular fact was detected.

    Preserves exact provenance (source file, exact configuration detail,
    confidence level, and relative file path) across the analyzer pipeline.
    """

    source: str = Field(
        description="Source identifier or file name, e.g. '.nvmrc', 'package.json', 'compose.yaml'"
    )
    detail: str | None = Field(
        default=None,
        description="Exact matched value or excerpt, e.g. 'engines.node: >=18', '22.14.0'",
    )
    confidence: Confidence = Field(
        default=Confidence.HIGH,
        description="Confidence score for this detection fact",
    )
    path: str | None = Field(
        default=None,
        description="Normalized relative path from repository root, using forward slashes",
    )
