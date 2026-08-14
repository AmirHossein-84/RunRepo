"""Built-in deterministic domain detectors."""

from runrepo.analyzer.detectors.database import DatabaseDetector
from runrepo.analyzer.detectors.docker import DockerDetector
from runrepo.analyzer.detectors.env import EnvironmentDetector
from runrepo.analyzer.detectors.node import NodeDetector
from runrepo.analyzer.detectors.python import PythonDetector

DEFAULT_DETECTORS = [
    NodeDetector(),
    PythonDetector(),
    DockerDetector(),
    DatabaseDetector(),
    EnvironmentDetector(),
]

__all__ = [
    "NodeDetector",
    "PythonDetector",
    "DockerDetector",
    "DatabaseDetector",
    "EnvironmentDetector",
    "DEFAULT_DETECTORS",
]
