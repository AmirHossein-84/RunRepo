"""Detector for Bun JavaScript/TypeScript runtime and package manager."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import Confidence, DetectionEvidence, PackageManagerInfo, RuntimeInfo


class BunDetector(BaseDetector):
    """Detects Bun runtime, bun.lockb, bun.lock, or bunfig.toml configurations."""

    @property
    def name(self) -> str:
        return "bun"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        has_lockb = context.has_file("bun.lockb")
        has_lock = context.has_file("bun.lock")
        has_config = context.has_file("bunfig.toml")

        if has_lockb or has_lock or has_config:
            source_file = "bun.lockb" if has_lockb else ("bun.lock" if has_lock else "bunfig.toml")
            result.runtimes.append(
                RuntimeInfo(
                    name="bun",
                    evidence=[
                        DetectionEvidence(
                            source=source_file,
                            confidence=Confidence.HIGH,
                            details=f"Discovered Bun configuration file: {source_file}",
                        )
                    ],
                )
            )
            result.package_managers.append(
                PackageManagerInfo(
                    name="bun",
                    evidence=[
                        DetectionEvidence(
                            source=source_file,
                            confidence=Confidence.HIGH,
                            details=f"Discovered Bun lockfile/config: {source_file}",
                        )
                    ],
                )
            )
            result.languages.extend(["javascript", "typescript"])

        return result
