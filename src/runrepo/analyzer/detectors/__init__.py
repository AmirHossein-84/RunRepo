"""Built-in deterministic domain detectors."""

from runrepo.analyzer.detectors.bun import BunDetector
from runrepo.analyzer.detectors.conda import CondaDetector
from runrepo.analyzer.detectors.database import DatabaseDetector
from runrepo.analyzer.detectors.deno import DenoDetector
from runrepo.analyzer.detectors.docker import DockerDetector
from runrepo.analyzer.detectors.env import EnvironmentDetector
from runrepo.analyzer.detectors.go import GoDetector
from runrepo.analyzer.detectors.node import NodeDetector
from runrepo.analyzer.detectors.python import PythonDetector
from runrepo.analyzer.detectors.rust import RustDetector

DEFAULT_DETECTORS = [
    NodeDetector(),
    PythonDetector(),
    DockerDetector(),
    DatabaseDetector(),
    EnvironmentDetector(),
    BunDetector(),
    DenoDetector(),
    GoDetector(),
    RustDetector(),
    CondaDetector(),
]

__all__ = [
    "NodeDetector",
    "PythonDetector",
    "DockerDetector",
    "DatabaseDetector",
    "EnvironmentDetector",
    "BunDetector",
    "DenoDetector",
    "GoDetector",
    "RustDetector",
    "CondaDetector",
    "DEFAULT_DETECTORS",
]
