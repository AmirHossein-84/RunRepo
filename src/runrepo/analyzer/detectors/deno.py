"""Detector for Deno runtime and configuration."""

from runrepo.analyzer.context import ScanContext
from runrepo.analyzer.detector import BaseDetector, DetectorResult
from runrepo.models import Confidence, DetectionEvidence, ProjectScript, RuntimeInfo


class DenoDetector(BaseDetector):
    """Detects Deno runtime, deno.json, deno.jsonc, or deno.lock."""

    @property
    def name(self) -> str:
        return "deno"

    def detect(self, context: ScanContext) -> DetectorResult:
        result = DetectorResult()

        has_deno_json = context.has_file("deno.json")
        has_deno_jsonc = context.has_file("deno.jsonc")
        has_deno_lock = context.has_file("deno.lock")

        if has_deno_json or has_deno_jsonc or has_deno_lock:
            source_file = "deno.json" if has_deno_json else ("deno.jsonc" if has_deno_jsonc else "deno.lock")
            result.runtimes.append(
                RuntimeInfo(
                    name="deno",
                    evidence=[
                        DetectionEvidence(
                            source=source_file,
                            confidence=Confidence.HIGH,
                            details=f"Discovered Deno configuration: {source_file}",
                        )
                    ],
                )
            )
            result.languages.extend(["typescript", "javascript"])

            # Check tasks in deno.json
            deno_cfg = context.read_json(source_file)
            if deno_cfg and isinstance(deno_cfg, dict):
                tasks = deno_cfg.get("tasks", {})
                if isinstance(tasks, dict):
                    for task_name, task_cmd in tasks.items():
                        result.scripts.append(
                            ProjectScript(
                                name=task_name,
                                command=f"deno task {task_name}",
                                evidence=[
                                    DetectionEvidence(
                                        source=source_file,
                                        confidence=Confidence.HIGH,
                                        details=f"Deno task '{task_name}' in {source_file}",
                                    )
                                ],
                            )
                        )

        return result
