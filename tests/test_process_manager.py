"""Unit tests for ProcessManager tracking and log management."""

from pathlib import Path
from runrepo.executor.process import MockProcessExecutor
from runrepo.executor.process_manager import ProcessManager


def test_process_manager_start_and_list(tmp_path):
    pm = ProcessManager(state_dir=tmp_path)
    executor = MockProcessExecutor()

    repo = tmp_path / "repo"
    repo.mkdir()

    proc = pm.start_process(
        name="web-app",
        repo_path=repo,
        command=["python", "main.py"],
        executor=executor,
    )

    assert proc.name == "web-app"
    assert proc.pid > 0
    assert Path(proc.log_file).exists()

    processes = pm.list_processes(repo_path=repo)
    assert len(processes) == 1
    assert processes[0].name == "web-app"


def test_process_manager_get_logs(tmp_path):
    pm = ProcessManager(state_dir=tmp_path)
    executor = MockProcessExecutor()
    repo = tmp_path / "repo"
    repo.mkdir()

    proc = pm.start_process(
        name="web-app",
        repo_path=repo,
        command=["python", "main.py"],
        executor=executor,
    )

    log_path = Path(proc.log_file)
    log_path.write_text("Line 1\nLine 2\nLine 3\nServer running on port 3000\n", encoding="utf-8")

    logs = pm.get_process_logs(repo_path=repo, name="web-app", tail=2)
    assert "Server running on port 3000" in logs
    assert "Line 3" in logs
    assert "Line 1" not in logs
