"""Detector for Rust language and Cargo package manager."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import Confidence, DetectionEvidence, PackageManagerInfo, ProjectScript, RuntimeInfo


class RustDetector(BaseDetector):
    """Detects Rust programming language, Cargo.toml, and Cargo package manager."""

    @property
    def name(self) -> str:
        return "rust"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        cargo_files = context.find_files_by_name("Cargo.toml")
        if cargo_files:
            rel_file = cargo_files[0]
            result.languages.append("rust")
            result.runtimes.append(
                RuntimeInfo(
                    name="rust",
                    evidence=[
                        DetectionEvidence(
                            source="Cargo.toml",
                            confidence=Confidence.HIGH,
                            details=f"Discovered Cargo.toml manifest at {rel_file}",
                            path=rel_file,
                        )
                    ],
                )
            )
            result.package_managers.append(
                PackageManagerInfo(
                    name="cargo",
                    evidence=[
                        DetectionEvidence(
                            source="Cargo.toml",
                            confidence=Confidence.HIGH,
                            details=f"Discovered Cargo package manager at {rel_file}",
                            path=rel_file,
                        )
                    ],
                )
            )
            result.scripts.append(
                ProjectScript(
                    name="dev",
                    command="cargo run",
                    evidence=[
                        DetectionEvidence(
                            source="Cargo.toml",
                            confidence=Confidence.HIGH,
                            details="Default cargo run development command",
                            path=rel_file,
                        )
                    ],
                )
            )

        return result
