"""Detector for Conda environments."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import Confidence, DetectionEvidence, PackageManagerInfo, RuntimeInfo


class CondaDetector(BaseDetector):
    """Detects Conda environments from environment.yml or environment.yaml."""

    @property
    def name(self) -> str:
        return "conda"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        has_yml = context.has_file("environment.yml")
        has_yaml = context.has_file("environment.yaml")

        if has_yml or has_yaml:
            source = "environment.yml" if has_yml else "environment.yaml"
            result.languages.append("python")
            result.runtimes.append(
                RuntimeInfo(
                    name="python",
                    evidence=[
                        DetectionEvidence(
                            source=source,
                            confidence=Confidence.HIGH,
                            details=f"Discovered Conda environment file: {source}",
                        )
                    ],
                )
            )
            result.package_managers.append(
                PackageManagerInfo(
                    name="conda",
                    evidence=[
                        DetectionEvidence(
                            source=source,
                            confidence=Confidence.HIGH,
                            details=f"Discovered Conda environment file: {source}",
                        )
                    ],
                )
            )

        return result
