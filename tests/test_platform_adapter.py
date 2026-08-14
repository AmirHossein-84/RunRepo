"""Unit tests for PlatformAdapter cross-platform process management and capabilities."""

from runrepo.platform.adapter import PlatformAdapter
from runrepo.platform.models import OperatingSystem


def test_platform_adapter_get_os():
    current_os = PlatformAdapter.get_os()
    assert current_os in (OperatingSystem.WINDOWS, OperatingSystem.LINUX, OperatingSystem.MACOS)


def test_platform_adapter_capabilities():
    caps = PlatformAdapter.get_capabilities()
    assert caps.os in (OperatingSystem.WINDOWS, OperatingSystem.LINUX, OperatingSystem.MACOS)
    assert len(caps.architecture) > 0
    assert isinstance(caps.system_package_managers, list)


def test_platform_adapter_package_managers():
    pms = PlatformAdapter.detect_system_package_managers()
    assert isinstance(pms, list)
