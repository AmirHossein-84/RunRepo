"""Cross-platform operating system adapter handling Windows, Linux, and macOS differences."""

import os
import platform
import shutil
import signal
import subprocess
from runrepo.platform.models import OperatingSystem, PlatformCapabilities, SystemPackageManager


class PlatformAdapter:
    """Provides consistent process management and system inspection across OS platforms."""

    @classmethod
    def get_os(cls) -> OperatingSystem:
        """Identify the host operating system."""
        sys_name = platform.system().lower()
        if sys_name == "windows":
            return OperatingSystem.WINDOWS
        elif sys_name == "linux":
            return OperatingSystem.LINUX
        elif sys_name == "darwin":
            return OperatingSystem.MACOS
        return OperatingSystem.UNKNOWN

    @classmethod
    def kill_process_tree(cls, pid: int, timeout: float = 3.0) -> bool:
        """Safely terminate a process and all of its spawned child processes."""
        current_os = cls.get_os()

        if current_os == OperatingSystem.WINDOWS:
            try:
                cmd = ["taskkill", "/F", "/T", "/PID", str(pid)]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                return res.returncode == 0
            except Exception:
                return False
        else:
            # POSIX process group termination
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
                return True
            except ProcessLookupError:
                return True
            except Exception:
                try:
                    os.kill(pid, signal.SIGKILL)
                    return True
                except Exception:
                    return False

    @classmethod
    def detect_system_package_managers(cls) -> list[str]:
        """Discover installed OS package managers."""
        current_os = cls.get_os()
        found: list[str] = []

        candidates: list[str] = []
        if current_os == OperatingSystem.WINDOWS:
            candidates = ["winget", "choco", "scoop"]
        elif current_os == OperatingSystem.MACOS:
            candidates = ["brew", "port"]
        elif current_os == OperatingSystem.LINUX:
            candidates = ["apt", "apt-get", "dnf", "yum", "pacman", "apk", "zypper", "brew"]

        for tool in candidates:
            if shutil.which(tool) is not None:
                found.append(tool)

        return found

    @classmethod
    def get_capabilities(cls) -> PlatformCapabilities:
        """Inspect and return current host platform capabilities."""
        current_os = cls.get_os()
        arch = platform.machine().lower()
        pms = cls.detect_system_package_managers()
        has_docker = shutil.which("docker") is not None

        return PlatformCapabilities(
            os=current_os,
            architecture=arch,
            system_package_managers=pms,
            has_docker=has_docker,
            supports_process_groups=(current_os in (OperatingSystem.LINUX, OperatingSystem.MACOS)),
        )
