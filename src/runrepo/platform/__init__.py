"""Platform abstraction exports."""

from runrepo.platform.adapter import PlatformAdapter
from runrepo.platform.models import (
    OperatingSystem,
    PlatformCapabilities,
    SystemPackageManager,
)

__all__ = [
    "OperatingSystem",
    "SystemPackageManager",
    "PlatformCapabilities",
    "PlatformAdapter",
]
