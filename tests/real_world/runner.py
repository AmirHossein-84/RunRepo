import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from rich.console import Console
from rich.table import Table

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(highlight=False, legacy_windows=False)

BENCHMARK_ROOT = Path(__file__).parent.resolve()
PROJECT_ROOT = BENCHMARK_ROOT.parent.parent.resolve()
REPOSITORIES_FILE = BENCHMARK_ROOT / "repositories.yaml"
RESULTS_ROOT = BENCHMARK_ROOT / "results"


def load_corpus() -> Dict[str, Any]:
    with open(REPOSITORIES_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_command(cmd: List[str], cwd: Optional[Path] = None, timeout: float = 600.0) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RUNREPO_NO_AI"] = "1"
    env["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
    return subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )


def test_repository(repo: Dict[str, Any], batch_num: int) -> Dict[str, Any]:
    repo_id = repo["id"]
    repo_name = repo["name"]
    repo_url = repo["url"]
    console.print(f"\n[bold blue]--------------------------------------------------------------------[/bold blue]")
    console.print(f"[bold cyan]Testing [{repo_id}/50]:[/bold cyan] [bold]{repo_name}[/bold] ({repo_url})")
    console.print(f"[dim]Batch {batch_num} | Category: {repo.get('category')} | Difficulty: {repo.get('difficulty')}[/dim]")

    start_time = time.perf_counter()
    result_data: Dict[str, Any] = {
        "id": repo_id,
        "name": repo_name,
        "url": repo_url,
        "batch": batch_num,
        "category": repo.get("category"),
        "language": repo.get("language"),
        "expected_runtime": repo.get("expected_runtime"),
        "expected_package_manager": repo.get("expected_package_manager"),
        "expected_services": repo.get("expected_services", []),
        "difficulty": repo.get("difficulty"),
        "result": "UNKNOWN",
        "status": "UNKNOWN",
        "failure_stage": None,
        "failure_category": None,
        "root_cause": None,
        "manual_intervention": None,
        "verification": None,
        "cleanup": None,
        "duration_seconds": 0.0,
        "executed_steps": [],
        "notes": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    batch_dir = RESULTS_ROOT / f"batch_{batch_num}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    slug = repo_url.replace("https://github.com/", "").replace("/", "_").lower()
    raw_log_file = batch_dir / f"repo_{repo_id:02d}_{slug}.log"

    try:
        # 1. Execute Setup via CLI
        cmd = ["uv", "run", "runrepo", "setup", repo_url, "--yes", "--no-ai", "--json"]
        proc = run_command(cmd, timeout=600.0)

        duration = time.perf_counter() - start_time
        result_data["duration_seconds"] = round(duration, 2)

        # Write raw stdout and stderr
        raw_log_file.write_text(
            f"=== STDOUT ===\n{proc.stdout}\n\n=== STDERR ===\n{proc.stderr}\n",
            encoding="utf-8",
        )

        parsed_json: Optional[Dict[str, Any]] = None
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if line_str.startswith("{") and line_str.endswith("}"):
                try:
                    candidate = json.loads(line_str)
                    if "status" in candidate and ("steps" in candidate or "plan_id" in candidate):
                        parsed_json = candidate
                        break
                except Exception:
                    pass

        if not parsed_json and "{" in proc.stdout:
            try:
                idx = proc.stdout.find("{")
                last_idx = proc.stdout.rfind("}")
                if idx != -1 and last_idx != -1 and last_idx > idx:
                    parsed_json = json.loads(proc.stdout[idx : last_idx + 1])
            except Exception:
                pass

        if parsed_json:
            result_data["status"] = parsed_json.get("status", "UNKNOWN")
            result_data["executed_steps"] = [
                {
                    "step_id": s.get("step_id"),
                    "status": s.get("status"),
                    "command": s.get("command"),
                    "duration_ms": s.get("duration_ms"),
                    "error": s.get("error"),
                }
                for s in parsed_json.get("steps", [])
            ]

            if result_data["status"] == "SUCCESS":
                result_data["result"] = "FULL_SUCCESS"
                result_data["verification"] = "PASSED"
                console.print(f"[bold green]+ FULL_SUCCESS[/bold green] in {duration:.1f}s")
            elif result_data["status"] == "BLOCKED":
                summary = str(parsed_json.get("summary", "")).lower()
                result_data["root_cause"] = parsed_json.get("summary")
                result_data["failure_stage"] = "PREREQUISITE_CHECK"
                if any(k in summary for k in ("rust", "cargo", "go ", "golang", "ruby", "unsupported", "version mismatch")):
                    result_data["result"] = "CORRECTLY_UNSUPPORTED"
                    result_data["failure_category"] = "UNSUPPORTED_RUNTIME"
                    console.print(f"[bold yellow]? CORRECTLY_UNSUPPORTED[/bold yellow] ({result_data['root_cause']})")
                elif any(k in summary for k in ("secret", "token", "credential", "api_key", "api key", "password")):
                    result_data["result"] = "SUCCESS_WITH_USER_INPUT"
                    result_data["failure_category"] = "CREDENTIALS_REQUIRED"
                    console.print(f"[bold yellow]! SUCCESS_WITH_USER_INPUT[/bold yellow] ({result_data['root_cause']})")
                else:
                    result_data["result"] = "INCORRECT_FAILURE"
                    result_data["failure_category"] = "BLOCKED_PREREQUISITE"
                    console.print(f"[bold red]X BLOCKED[/bold red] ({result_data['root_cause']})")
            else:
                failed_step = next((s for s in parsed_json.get("steps", []) if s.get("status") in ("FAILED", "BLOCKED")), None)
                if failed_step:
                    result_data["failure_stage"] = failed_step.get("step_id")
                    result_data["root_cause"] = failed_step.get("error") or failed_step.get("stderr") or "Step execution failed"
                    
                    # Categorize failure
                    step_id = str(failed_step.get("step_id", "")).lower()
                    if "docker" in step_id:
                        result_data["failure_category"] = "DOCKER"
                    elif "service" in step_id:
                        result_data["failure_category"] = "POSTGRES" if "postgres" in step_id else "REDIS"
                    elif "env" in step_id:
                        result_data["failure_category"] = "ENVIRONMENT_VARIABLES"
                    elif "install" in step_id or "deps" in step_id:
                        result_data["failure_category"] = "PACKAGE_MANAGER"
                    elif "migration" in step_id or "prisma" in step_id or "alembic" in step_id:
                        result_data["failure_category"] = "MIGRATION"
                    elif "verify" in step_id or "start" in step_id:
                        result_data["failure_category"] = "VERIFICATION"
                    else:
                        result_data["failure_category"] = "EXECUTOR"

                    if result_data["failure_category"] == "VERIFICATION":
                        result_data["result"] = "PARTIAL_SUCCESS"
                        console.print(f"[bold yellow]~ PARTIAL_SUCCESS[/bold yellow] at {result_data.get('failure_stage')}: {result_data.get('failure_category')}")
                    else:
                        result_data["result"] = "INCORRECT_FAILURE"
                        console.print(f"[bold red]X INCORRECT_FAILURE[/bold red] at {result_data.get('failure_stage')}: {result_data.get('failure_category')}")
                else:
                    result_data["failure_stage"] = "UNKNOWN"
                    result_data["failure_category"] = "EXECUTOR"
                    result_data["result"] = "INCORRECT_FAILURE"
                    console.print(f"[bold red]X INCORRECT_FAILURE[/bold red] at {result_data.get('failure_stage')}: {result_data.get('failure_category')}")
        else:
            if proc.returncode == 0:
                result_data["result"] = "FULL_SUCCESS"
                result_data["status"] = "SUCCESS"
                result_data["verification"] = "PASSED"
                console.print(f"[bold green]+ FULL_SUCCESS (Exit 0)[/bold green] in {duration:.1f}s")
            else:
                result_data["result"] = "INCORRECT_FAILURE"
                result_data["status"] = "FAILED"
                result_data["failure_stage"] = "CLI_INVOCATION"
                result_data["failure_category"] = "EXECUTOR"
                result_data["root_cause"] = proc.stderr[:300] if proc.stderr else proc.stdout[:300]
                console.print(f"[bold red]X FAILED[/bold red] Exit code {proc.returncode}")

    except subprocess.TimeoutExpired:
        result_data["result"] = "INCORRECT_FAILURE"
        result_data["status"] = "TIMEOUT"
        result_data["failure_stage"] = "TIMEOUT"
        result_data["failure_category"] = "EXECUTOR"
        result_data["root_cause"] = "Execution exceeded 360s timeout"
        console.print("[bold red]X TIMEOUT (360s)[/bold red]")
    except Exception as exc:
        result_data["result"] = "INCORRECT_FAILURE"
        result_data["status"] = "ERROR"
        result_data["failure_stage"] = "EXCEPTION"
        result_data["failure_category"] = "UNKNOWN"
        result_data["root_cause"] = str(exc)
        console.print(f"[bold red]X ERROR:[/bold red] {exc}")

    # Cleanup any running processes for this repo
    try:
        run_command(["uv", "run", "runrepo", "stop"])
        result_data["cleanup"] = "SUCCESS"
    except Exception:
        result_data["cleanup"] = "FAILED"

    # Save structured YAML result
    res_yaml_file = batch_dir / f"repo_{repo_id:02d}_{slug}.yaml"
    with open(res_yaml_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(result_data, f, sort_keys=False)

    return result_data


def run_batch(batch_num: int) -> List[Dict[str, Any]]:
    corpus = load_corpus()
    batches = corpus.get("batches", [])
    batch_data = next((b for b in batches if b["batch"] == batch_num), None)
    if not batch_data:
        console.print(f"[bold red]Batch {batch_num} not found in repositories.yaml[/bold red]")
        sys.exit(1)

    console.print(f"\n[bold yellow]====================================================================[/bold yellow]")
    console.print(f"[bold yellow]  STARTING BATCH {batch_num}: {batch_data['name']} (10 Repositories)  [/bold yellow]")
    console.print(f"[bold yellow]====================================================================[/bold yellow]")

    results: List[Dict[str, Any]] = []
    for repo in batch_data["repositories"]:
        res = test_repository(repo, batch_num)
        results.append(res)

    # Output Batch Summary Table
    table = Table(title=f"Batch {batch_num} Results: {batch_data['name']}")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Repository", style="bold cyan")
    table.add_column("Category", style="dim")
    table.add_column("Result", justify="center")
    table.add_column("Stage / Failure", style="yellow")
    table.add_column("Duration", justify="right")

    for r in results:
        res_style = "bold green" if r["result"] == "FULL_SUCCESS" else "bold red"
        stage_info = f"{r.get('failure_category', '')}: {r.get('failure_stage', '')}" if r.get("failure_stage") else "-"
        table.add_row(
            str(r["id"]),
            r["name"],
            r.get("category", "-"),
            f"[{res_style}]{r['result']}[/{res_style}]",
            stage_info,
            f"{r['duration_seconds']}s",
        )

    console.print(table)

    # Save Batch summary JSON
    summary_file = RESULTS_ROOT / f"batch_{batch_num}" / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="RunRepo 50-Repository Real-World Benchmark Runner")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3, 4, 5], help="Run a specific batch (1-5)")
    parser.add_argument("--id", type=int, help="Run a specific repository ID (1-50)")
    args = parser.parse_args()

    if args.id:
        corpus = load_corpus()
        for b in corpus["batches"]:
            for r in b["repositories"]:
                if r["id"] == args.id:
                    test_repository(r, b["batch"])
                    return
        console.print(f"[bold red]Repository ID {args.id} not found[/bold red]")
        sys.exit(1)

    if args.batch:
        run_batch(args.batch)
    else:
        # Default to Batch 1
        run_batch(1)


if __name__ == "__main__":
    main()
