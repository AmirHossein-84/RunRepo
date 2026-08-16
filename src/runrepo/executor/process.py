"""Process execution layer providing safe subprocess management for foreground and background tasks."""

import os
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class ProcessExecutionResult:
    """Outcome of a process execution."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: float = 0.0
    pid: int | None = None


class ProcessExecutor(ABC):
    """Abstract interface for process execution."""

    @abstractmethod
    def execute(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout_s: float | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessExecutionResult:
        """Execute a foreground command synchronously to completion."""
        ...

    @abstractmethod
    def start_background(
        self,
        command: list[str],
        cwd: Path | None = None,
        log_file: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> int:
        """Start a detached long-running background process, returning its PID."""
        ...


class SystemProcessExecutor(ProcessExecutor):
    """Production process executor using subprocess without shell=True."""

    @staticmethod
    def _sanitize_proxy_env(env_dict: dict[str, str]) -> None:
        """Ensure proxy URLs conform to RFC URI format and bypass dead localhost proxies."""
        import socket
        from urllib.parse import urlparse

        proxy_keys = ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
        for key in proxy_keys:
            val = env_dict.get(key)
            if val and val.strip():
                clean = val.strip()
                if not clean.startswith(("http://", "https://", "socks5://", "socks5h://")):
                    clean = f"http://{clean}"

                # If proxy points to local address, verify that the proxy server is actually listening
                try:
                    parsed = urlparse(clean)
                    host = parsed.hostname
                    port = parsed.port
                    if host in ("127.0.0.1", "localhost", "::1") and port:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.settimeout(0.15)
                            if s.connect_ex((host, port)) != 0:
                                # Dead localhost proxy: drop from environment so network calls succeed
                                env_dict.pop(key, None)
                                continue
                except Exception:
                    pass

                env_dict[key] = clean

    @staticmethod
    def _load_dotenv(cwd: Path | None, env_dict: dict[str, str]) -> None:
        """Load .env from cwd if present into env_dict without overriding existing non-empty keys."""
        if not cwd:
            return
        env_file = cwd / ".env"
        if env_file.exists() and env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and (k not in env_dict or not env_dict[k]):
                            env_dict[k] = v
            except Exception:
                pass

    def execute(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout_s: float | None = 300.0,
        env: dict[str, str] | None = None,
    ) -> ProcessExecutionResult:
        if not command:
            return ProcessExecutionResult(
                stdout="",
                stderr="Empty command list provided",
                exit_code=1,
                duration_ms=0.0,
            )

        merged_env = os.environ.copy()
        merged_env["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
        self._load_dotenv(cwd, merged_env)
        if env:
            merged_env.update(env)
        self._sanitize_proxy_env(merged_env)

        working_dir = str(cwd.resolve()) if cwd else None
        start_time = time.perf_counter()

        # On Windows, resolve command executable if needed
        resolved_cmd = list(command)
        executable = resolved_cmd[0]
        which_path = shutil.which(executable)
        if which_path:
            resolved_cmd[0] = which_path

        if sys.platform == "win32" and resolved_cmd:
            exe_lower = resolved_cmd[0].lower()
            if exe_lower.endswith((".cmd", ".bat")):
                resolved_cmd = ["cmd.exe", "/c"] + resolved_cmd

        try:
            process = subprocess.Popen(
                resolved_cmd,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                shell=False,
                env=merged_env,
            )
            stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_s)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

            return ProcessExecutionResult(
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode,
                duration_ms=duration_ms,
                pid=process.pid,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_bytes, stderr_bytes = process.communicate()
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ProcessExecutionResult(
                stdout=stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else "",
                stderr=(stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "") + f"\nProcess timed out after {timeout_s}s",
                exit_code=124,
                duration_ms=duration_ms,
                pid=process.pid,
            )
        except FileNotFoundError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ProcessExecutionResult(
                stdout="",
                stderr=f"Executable not found on PATH: {executable} ({exc})",
                exit_code=127,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ProcessExecutionResult(
                stdout="",
                stderr=f"Process execution failed: {exc}",
                exit_code=1,
                duration_ms=duration_ms,
            )

    def start_background(
        self,
        command: list[str],
        cwd: Path | None = None,
        log_file: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> int:
        if not command:
            raise ValueError("Cannot launch empty command in background")

        merged_env = os.environ.copy()
        merged_env["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
        self._load_dotenv(cwd, merged_env)
        if env:
            merged_env.update(env)
        self._sanitize_proxy_env(merged_env)

        working_dir = str(cwd.resolve()) if cwd else None
        resolved_cmd = list(command)
        which_path = shutil.which(resolved_cmd[0])
        if which_path:
            resolved_cmd[0] = which_path

        if sys.platform == "win32" and resolved_cmd:
            exe_lower = resolved_cmd[0].lower()
            if exe_lower.endswith((".cmd", ".bat")):
                resolved_cmd = ["cmd.exe", "/c"] + resolved_cmd

        out_dest = subprocess.DEVNULL
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            out_dest = open(log_file, "a", encoding="utf-8")

        creationflags = 0
        start_new_session = False
        if sys.platform == "win32":
            # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            start_new_session = True

        try:
            process = subprocess.Popen(
                resolved_cmd,
                cwd=working_dir,
                stdout=out_dest,
                stderr=subprocess.STDOUT if log_file else subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                shell=False,
                env=merged_env,
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
            return process.pid
        finally:
            if log_file and out_dest != subprocess.DEVNULL and hasattr(out_dest, "close"):
                out_dest.close()


class MockProcessExecutor(ProcessExecutor):
    """Deterministic mock process executor for tests with zero subprocess execution."""

    def __init__(
        self,
        responses: dict | None = None,
        custom_responses: dict | None = None,
        default_response: ProcessExecutionResult | None = None,
        default_result: ProcessExecutionResult | None = None,
        side_effect: Any | None = None,
    ) -> None:
        raw_responses = responses or custom_responses or {}
        self.responses: dict[tuple[str, ...], ProcessExecutionResult] = {}
        for k, v in raw_responses.items():
            key = tuple(k.split()) if isinstance(k, str) else tuple(k)
            self.responses[key] = v

        self.default_response = default_response or default_result or ProcessExecutionResult(
            stdout="mock output",
            stderr="",
            exit_code=0,
            duration_ms=10.0,
            pid=12345,
        )
        self.side_effect = side_effect
        self.executed_commands: list[tuple[list[str], Path | None]] = []
        self.background_commands: list[tuple[list[str], Path | None, Path | None]] = []
        self._next_pid = 20000

    def register_response(
        self,
        command: list[str] | tuple[str, ...] | str,
        result: ProcessExecutionResult,
    ) -> None:
        """Register a specific mock result for an exact command prefix or tuple."""
        key = tuple(command.split()) if isinstance(command, str) else tuple(command)
        self.responses[key] = result

    def execute(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout_s: float | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessExecutionResult:
        self.executed_commands.append((list(command), cwd))

        if self.side_effect is not None:
            if callable(self.side_effect):
                res = self.side_effect(command, cwd=cwd, env=env, timeout=timeout_s)
                if res is not None:
                    return res

        key = tuple(command)
        if key in self.responses:
            return self.responses[key]

        # Check partial prefix match
        for registered_key, resp in self.responses.items():
            if len(command) >= len(registered_key) and tuple(command[: len(registered_key)]) == registered_key:
                return resp

        return self.default_response

    def start_background(
        self,
        command: list[str],
        cwd: Path | None = None,
        log_file: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> int:
        self.background_commands.append((list(command), cwd, log_file))
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text("Mock background process started\n", encoding="utf-8")
        self._next_pid += 1
        return self._next_pid
