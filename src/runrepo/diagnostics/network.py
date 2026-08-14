"""Advanced network and port diagnostics with process owner inspection (Windows-first)."""

import platform
import re
import socket
import subprocess
from pydantic import BaseModel, Field


class PortOwnerInfo(BaseModel):
    """Information about the operating system process currently occupying a port."""

    port: int = Field(description="Port number inspected")
    pid: int | None = Field(default=None, description="Process ID occupying the port")
    process_name: str | None = Field(default=None, description="Executable or process name")
    protocol: str = Field(default="TCP", description="Network protocol")
    state: str = Field(default="LISTENING", description="Connection state")


class PortDiagnostics:
    """Inspects port availability and discovers owning processes without killing them."""

    @classmethod
    def get_port_owner(cls, port: int) -> PortOwnerInfo | None:
        """Inspect the operating system to find the process ID and name occupying a port."""
        current_os = platform.system().lower()

        if current_os == "windows":
            return cls._get_port_owner_windows(port)
        else:
            return cls._get_port_owner_posix(port)

    @classmethod
    def _get_port_owner_windows(cls, port: int) -> PortOwnerInfo | None:
        """Parse Windows netstat -ano to find owning PID and tasklist for process name."""
        try:
            cmd = ["netstat", "-ano", "-p", "tcp"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
            if res.returncode != 0:
                return None

            pid = None
            port_pattern = re.compile(rf":{port}\s+.*?LISTENING\s+(\d+)", re.IGNORECASE)
            for line in res.stdout.splitlines():
                match = port_pattern.search(line)
                if match:
                    pid = int(match.group(1))
                    break

            if pid is None:
                return None

            process_name = cls._get_process_name_windows(pid)
            return PortOwnerInfo(
                port=port,
                pid=pid,
                process_name=process_name,
                protocol="TCP",
                state="LISTENING",
            )
        except Exception:
            return None

    @classmethod
    def _get_process_name_windows(cls, pid: int) -> str | None:
        """Query tasklist to resolve executable name for a given PID."""
        try:
            cmd = ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0 and res.stdout:
                parts = res.stdout.strip().split(",")
                if parts:
                    return parts[0].strip('"')
        except Exception:
            pass
        return None

    @classmethod
    def _get_port_owner_posix(cls, port: int) -> PortOwnerInfo | None:
        """Inspect Linux/macOS port owner via ss or lsof."""
        try:
            cmd = ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0 and res.stdout.strip():
                pid = int(res.stdout.strip().splitlines()[0])
                return PortOwnerInfo(
                    port=port,
                    pid=pid,
                    process_name=f"pid_{pid}",
                    protocol="TCP",
                    state="LISTENING",
                )
        except Exception:
            pass
        return None

    @classmethod
    def check_port_availability(cls, port: int, host: str = "127.0.0.1") -> tuple[bool, PortOwnerInfo | None]:
        """Check if port is available; if in use, identify the owner process."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.bind((host, port))
                return True, None
            except OSError:
                owner = cls.get_port_owner(port)
                return False, owner


class NetworkDiagnostics:
    """Network connection probes and DNS diagnostics."""

    @classmethod
    def probe_localhost(cls, port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> tuple[bool, str | None]:
        """Check if a local service is listening and accepting connections on a given port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            try:
                s.connect((host, port))
                return True, None
            except ConnectionRefusedError:
                return False, f"Connection refused on {host}:{port}. Is the service running?"
            except TimeoutError:
                return False, f"Connection timed out on {host}:{port} after {timeout}s."
            except Exception as err:
                return False, f"Network probe failed for {host}:{port}: {err}"

    @classmethod
    def check_dns(cls, hostname: str) -> tuple[bool, str | None]:
        """Check DNS hostname resolution."""
        try:
            ip = socket.gethostbyname(hostname)
            return True, ip
        except socket.gaierror as err:
            return False, f"DNS resolution failed for '{hostname}': {err}"
