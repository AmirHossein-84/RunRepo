"""Safe command execution abstraction with per-run caching and test mocking support."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
import time


@dataclass(frozen=True)
class CommandResult:
    """Result of executing an inspection command."""

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    executable: str | None = None

    @property
    def success(self) -> bool:
        """Return True if command finished with exit code 0."""
        return self.exit_code == 0


class CommandRunner(ABC):
    """Abstract base class for running safe environment inspection commands with per-run caching."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, ...], CommandResult] = {}

    def run(self, cmd: list[str], timeout_s: float = 5.0) -> CommandResult:
        """Run command with caching by command argument tuple."""
        key = tuple(cmd)
        if key in self._cache:
            return self._cache[key]

        res = self._execute(cmd, timeout_s=timeout_s)
        self._cache[key] = res
        return res

    @abstractmethod
    def _execute(self, cmd: list[str], timeout_s: float) -> CommandResult:
        """Execute the command directly without checking cache."""
        pass

    @abstractmethod
    def which(self, binary_name: str) -> str | None:
        """Locate executable binary on system PATH."""
        pass


class SystemCommandRunner(CommandRunner):
    """Production command runner executing safe inspection commands via subprocess.run without shell=True."""

    def which(self, binary_name: str) -> str | None:
        """Find executable path using shutil.which."""
        return shutil.which(binary_name)

    def _execute(self, cmd: list[str], timeout_s: float) -> CommandResult:
        if not cmd:
            return CommandResult(
                stdout="",
                stderr="Empty command",
                exit_code=1,
                duration_ms=0.0,
            )

        binary = cmd[0]
        exe_path = self.which(binary)

        if exe_path is None:
            return CommandResult(
                stdout="",
                stderr=f"Executable '{binary}' not found on PATH",
                exit_code=127,
                duration_ms=0.0,
                executable=None,
            )

        # Build command with resolved binary path
        resolved_cmd = [exe_path] + cmd[1:]
        start_time = time.perf_counter()

        try:
            # Strictly avoid shell=True
            proc = subprocess.run(
                resolved_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
                errors="replace",
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return CommandResult(
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                exit_code=proc.returncode,
                duration_ms=elapsed_ms,
                executable=exe_path,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return CommandResult(
                stdout="",
                stderr=f"Command '{' '.join(cmd)}' timed out after {timeout_s}s",
                exit_code=124,
                duration_ms=elapsed_ms,
                executable=exe_path,
            )
        except (PermissionError, OSError) as err:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return CommandResult(
                stdout="",
                stderr=f"Failed to execute '{' '.join(cmd)}': {err}",
                exit_code=126,
                duration_ms=elapsed_ms,
                executable=exe_path,
            )


class MockCommandRunner(CommandRunner):
    """Test command runner pre-seeded with mock responses for deterministic, zero-subprocess tests."""

    def __init__(
        self,
        responses: dict[tuple[str, ...], CommandResult] | None = None,
        which_map: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.responses: dict[tuple[str, ...], CommandResult] = responses or {}
        self.which_map: dict[str, str] = which_map or {}
        self.recorded_calls: list[list[str]] = []

    def which(self, binary_name: str) -> str | None:
        return self.which_map.get(binary_name)

    def _execute(self, cmd: list[str], timeout_s: float) -> CommandResult:
        self.recorded_calls.append(list(cmd))
        key = tuple(cmd)

        if key in self.responses:
            return self.responses[key]

        # Check binary name match
        bin_key = (cmd[0],)
        if bin_key in self.responses:
            return self.responses[bin_key]

        return CommandResult(
            stdout="",
            stderr=f"Mock: binary '{cmd[0]}' not found",
            exit_code=127,
            duration_ms=0.0,
            executable=None,
        )
