"""Domain models for cross-platform OS and system package manager abstraction."""

from enum import StrEnum
from pydantic import BaseModel, Field


class OperatingSystem(StrEnum):
    """Operating system classification."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


class SystemPackageManager(StrEnum):
    """Host operating system package managers."""

    WINGET = "winget"
    CHOCO = "choco"
    SCOOP = "scoop"
    APT = "apt"
    DNF = "dnf"
    PACMAN = "pacman"
    BREW = "brew"


class PlatformCapabilities(BaseModel):
    """Capabilities and features available on the current host system."""

    os: OperatingSystem = Field(description="Host operating system")
    architecture: str = Field(description="CPU architecture (x86_64, arm64, etc.)")
    system_package_managers: list[str] = Field(
        default_factory=list,
        description="Available OS package managers (e.g. winget, brew, apt)",
    )
    has_docker: bool = Field(default=False, description="Whether Docker daemon is running")
    supports_process_groups: bool = Field(
        default=False,
        description="Whether OS supports POSIX process groups or Windows job objects",
    )
