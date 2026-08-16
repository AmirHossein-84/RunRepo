"""Domain models for Pull Request reproduction, environment export, and developer share specifications."""

from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field


class TestSuiteResult(BaseModel):
    """Execution results for a detected repository test suite."""

    command: list[str] = Field(description="Command executed to run the test suite, e.g. ['pytest'] or ['npm', 'test']")
    exit_code: int = Field(description="Process return code")
    passed: bool = Field(description="Whether the test suite passed with exit code 0")
    duration_ms: float = Field(default=0.0, description="Test execution duration in milliseconds")
    stdout: str = Field(default="", description="Captured test stdout")
    stderr: str = Field(default="", description="Captured test stderr")


class PRReproductionReport(BaseModel):
    """Comprehensive structured reproduction report for a GitHub Pull Request."""

    pr_url: str = Field(description="Original GitHub Pull Request URL")
    owner: str = Field(description="Repository owner/organization")
    repo: str = Field(description="Repository name")
    pr_number: int = Field(description="Pull request issue number")
    local_path: str = Field(description="Isolated directory where PR was reproduced")
    setup_successful: bool = Field(description="Whether environment setup & dependency install succeeded")
    test_results: list[TestSuiteResult] = Field(default_factory=list, description="Results of all executed test suites")
    all_tests_passed: bool = Field(default=True, description="Whether all executed test suites passed")
    startup_successful: bool = Field(default=False, description="Whether the application started successfully")
    live_urls: list[str] = Field(default_factory=list, description="Verified accessible localhost endpoints")
    duration_ms: float = Field(default=0.0, description="Total reproduction execution time in milliseconds")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )
    summary: str = Field(default="", description="Human-readable markdown summary of reproduction outcome")


class ShareSpec(BaseModel):
    """Developer onboarding specification containing Markdown guides and copy-pasteable scripts."""

    project_name: str = Field(description="Name of the analyzed project")
    target_path: str = Field(description="Base path of the repository")
    markdown_guide: str = Field(description="Comprehensive Markdown setup and run guide")
    bash_script: str = Field(description="Defensive cross-platform Bash setup script (setup.sh)")
    powershell_script: str = Field(description="Strict Windows PowerShell setup script (setup.ps1)")
    required_env_vars: list[str] = Field(default_factory=list, description="Required environment variables")
    required_ports: list[int] = Field(default_factory=list, description="Required listening ports")
