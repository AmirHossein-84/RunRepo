"""Process manager tracking long-running background applications, lifecycle states, and logs."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
import platformdirs

from runrepo.executor.process import ProcessExecutor, SystemProcessExecutor


class ManagedProcess(BaseModel):
    """Metadata record of a tracked background process."""

    name: str = Field(description="Process or service identifier")
    repo_path: str = Field(description="Associated repository path")
    command: list[str] = Field(description="Command line tokens executed")
    cwd: str | None = Field(default=None, description="Working directory relative to repo")
    pid: int = Field(description="Operating system process ID")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when process was spawned",
    )
    log_file: str = Field(description="Absolute path to process output log file")
    is_running: bool = Field(default=True, description="Whether process is currently active")


def is_pid_alive(pid: int) -> bool:
    """Check if a process ID is currently running on the system."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            STILL_ACTIVE = 259
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = wintypes.DWORD()
            success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            if success:
                return exit_code.value == STILL_ACTIVE
            return False
        except Exception:
            try:
                out = subprocess.check_output(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=2.0,
                )
                return str(pid) in out and "No tasks" not in out
            except Exception:
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Running under another user
            return True
        except OSError:
            return False


def terminate_pid(pid: int) -> bool:
    """Safely terminate a running process by PID."""
    if not is_pid_alive(pid):
        return True

    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5.0,
            )
            return not is_pid_alive(pid)
        except Exception:
            pass

    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.3)
        if is_pid_alive(pid):
            os.kill(pid, signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM)
        return not is_pid_alive(pid)
    except Exception:
        return not is_pid_alive(pid)


class ProcessManager:
    """Manages active background processes, persistence registry, and log retrieval."""

    def __init__(self, state_dir: Path | None = None) -> None:
        if state_dir is not None:
            self.state_dir = Path(state_dir).resolve()
        else:
            base_dir = Path(platformdirs.user_data_dir("runrepo", appauthor=False))
            self.state_dir = base_dir / "processes"

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.state_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.state_dir / "registry.json"

    def _load_registry(self) -> list[ManagedProcess]:
        if not self.registry_file.exists():
            return []
        try:
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            processes: list[ManagedProcess] = []
            for item in data:
                proc = ManagedProcess(**item)
                proc.is_running = is_pid_alive(proc.pid)
                processes.append(proc)
            return processes
        except Exception:
            return []

    def _save_registry(self, processes: list[ManagedProcess]) -> None:
        data = [p.model_dump(mode="json") for p in processes]
        self.registry_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def start_process(
        self,
        name: str,
        repo_path: Path,
        command: list[str],
        cwd: Path | None = None,
        executor: ProcessExecutor | None = None,
    ) -> ManagedProcess:
        """Start a long-running process and register it."""
        exec_layer = executor if executor is not None else SystemProcessExecutor()
        normalized_repo = str(repo_path.resolve())

        # Stop existing process for same repo/name if active
        self.stop_process(repo_path=repo_path, name=name)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = name.replace(":", "_").replace("/", "_").replace("\\", "_")
        log_file = self.logs_dir / f"{safe_name}_{timestamp_str}.log"

        pid = exec_layer.start_background(
            command=command,
            cwd=cwd,
            log_file=log_file,
        )

        managed = ManagedProcess(
            name=name,
            repo_path=normalized_repo,
            command=command,
            cwd=str(cwd.relative_to(repo_path)) if cwd and cwd != repo_path else None,
            pid=pid,
            log_file=str(log_file.resolve()),
            is_running=True,
        )

        processes = self._load_registry()
        processes.append(managed)
        self._save_registry(processes)
        return managed

    def stop_process(
        self,
        repo_path: Path | None = None,
        name: str | None = None,
    ) -> list[ManagedProcess]:
        """Stop running processes matching repo_path and/or name."""
        processes = self._load_registry()
        stopped: list[ManagedProcess] = []
        normalized_repo = str(repo_path.resolve()) if repo_path else None

        for proc in processes:
            match_repo = normalized_repo is None or proc.repo_path == normalized_repo
            match_name = name is None or proc.name == name

            if match_repo and match_name and proc.is_running:
                terminate_pid(proc.pid)
                proc.is_running = False
                stopped.append(proc)

        self._save_registry(processes)
        return stopped

    def list_processes(self, repo_path: Path | None = None) -> list[ManagedProcess]:
        """List tracked processes and refresh active states."""
        processes = self._load_registry()
        normalized_repo = str(repo_path.resolve()) if repo_path else None
        for proc in processes:
            proc.is_running = is_pid_alive(proc.pid)
        self._save_registry(processes)
        filtered = [
            p for p in processes
            if normalized_repo is None or p.repo_path == normalized_repo
        ]
        return filtered

    def get_process_logs(
        self,
        repo_path: Path | None = None,
        name: str | None = None,
        tail: int = 50,
    ) -> str:
        """Fetch the latest output logs for a matching process."""
        processes = self.list_processes(repo_path=repo_path)
        matching = [p for p in processes if name is None or p.name == name]
        if not matching:
            return "No matching processes found."

        # Pick latest
        target_proc = matching[-1]
        log_path = Path(target_proc.log_file)
        if not log_path.exists():
            return f"Log file not found: {log_path}"

        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = lines[-tail:] if len(lines) > tail else lines
            return "\n".join(selected)
        except Exception as exc:
            return f"Failed to read logs: {exc}"
