"""Detector for Go programming language and modules."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import Confidence, DetectionEvidence, ProjectScript, RuntimeInfo


class GoDetector(BaseDetector):
    """Detects Go runtime and go.mod modules."""

    @property
    def name(self) -> str:
        return "go"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        if context.has_file("go.mod") or context.has_file("main.go"):
            source = "go.mod" if context.has_file("go.mod") else "main.go"
            result.languages.append("go")
            result.runtimes.append(
                RuntimeInfo(
                    name="go",
                    evidence=[
                        DetectionEvidence(
                            source=source,
                            confidence=Confidence.HIGH,
                            details=f"Discovered Go source file: {source}",
                        )
                    ],
                )
            )

            if context.has_file("main.go"):
                result.scripts.append(
                    ProjectScript(
                        name="dev",
                        command="go run .",
                        evidence=[
                            DetectionEvidence(
                                source="main.go",
                                confidence=Confidence.HIGH,
                                details="Discovered main.go Go entrypoint",
                            )
                        ],
                    )
                )

        return result
