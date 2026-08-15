"""Deterministic Python virtual environment detection and inspection."""

from enum import StrEnum
from pathlib import Path
from pydantic import BaseModel, Field

from runrepo.environment.version import clean_version_string, evaluate_version_requirement


class VirtualEnvStatus(StrEnum):
    """Classification of local Python virtual environment state."""

    NOT_FOUND = "NOT_FOUND"          # No virtual environment directory found
    VALID = "VALID"                  # Virtual environment is intact and satisfies version constraints
    BROKEN = "BROKEN"                # Virtual environment directory exists but is incomplete or corrupted
    WRONG_VERSION = "WRONG_VERSION"  # Virtual environment exists but Python version violates required constraint


class VirtualEnvInspection(BaseModel):
    """Structured inspection result of a Python virtual environment."""

    status: VirtualEnvStatus = Field(description="Operational status of virtual environment")
    path: Path = Field(description="Path to inspected virtual environment directory")
    python_version: str | None = Field(
        default=None,
        description="Detected Python version string inside the virtual environment",
    )
    python_executable: Path | None = Field(
        default=None,
        description="Path to python executable inside virtual environment",
    )
    details: str = Field(
        default="",
        description="Human-readable explanation of inspection outcome",
    )


def _parse_pyvenv_cfg(cfg_path: Path) -> dict[str, str]:
    """Safely parse standard pyvenv.cfg key-value configuration."""
    config: dict[str, str] = {}
    if not cfg_path.exists() or not cfg_path.is_file():
        return config

    try:
        content = cfg_path.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                config[key.strip().lower()] = val.strip()
    except Exception:
        pass
    return config


def _find_venv_python_executable(venv_dir: Path) -> Path | None:
    """Find the python interpreter binary inside a virtual environment across Windows and POSIX."""
    candidates = [
        # Windows layout
        venv_dir / "Scripts" / "python.exe",
        venv_dir / "Scripts" / "python.cmd",
        venv_dir / "Scripts" / "python.bat",
        venv_dir / "Scripts" / "python",
        # POSIX layout
        venv_dir / "bin" / "python",
        venv_dir / "bin" / "python3",
        venv_dir / "bin" / "python.exe",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def inspect_virtual_env(
    target_dir: Path | str,
    required_version: str | None = None,
    venv_name: str = ".venv",
) -> VirtualEnvInspection:
    """Deterministically inspect a Python virtual environment directory.

    Evaluates:
      1. Presence of .venv directory
      2. Presence and validity of python interpreter binary (Scripts/ or bin/)
      3. pyvenv.cfg metadata (version, home)
      4. Version compatibility against required_version constraint

    Args:
        target_dir: Directory containing or expected to contain .venv
        required_version: Optional version constraint (e.g. '>=3.11', '3.12')
        venv_name: Name of the virtualenv folder (defaults to '.venv')

    Returns:
        VirtualEnvInspection containing classification and diagnostic explanation.
    """
    base = Path(target_dir).resolve()
    venv_path = base / venv_name

    # Check alternative 'venv' if '.venv' does not exist
    if not venv_path.exists() and (base / "venv").exists():
        venv_path = base / "venv"

    # 1. NOT_FOUND
    if not venv_path.exists():
        return VirtualEnvInspection(
            status=VirtualEnvStatus.NOT_FOUND,
            path=venv_path,
            details=f"No virtual environment found at {venv_path}",
        )

    # If it's a file instead of directory -> BROKEN
    if not venv_path.is_dir():
        return VirtualEnvInspection(
            status=VirtualEnvStatus.BROKEN,
            path=venv_path,
            details=f"Target path {venv_path} is a file, not a directory",
        )

    # 2. Locate Interpreter
    exe_path = _find_venv_python_executable(venv_path)
    if exe_path is None:
        return VirtualEnvInspection(
            status=VirtualEnvStatus.BROKEN,
            path=venv_path,
            details=f"Virtual environment directory exists at {venv_path} but contains no valid python executable in Scripts/ or bin/",
        )

    # 3. Read pyvenv.cfg metadata
    cfg_data = _parse_pyvenv_cfg(venv_path / "pyvenv.cfg")
    raw_version = cfg_data.get("version") or cfg_data.get("version_info")
    extracted_version = clean_version_string(raw_version) if raw_version else None

    # 4. Version Check
    if required_version and extracted_version:
        is_sat = evaluate_version_requirement(extracted_version, required_version)
        if is_sat is False:
            return VirtualEnvInspection(
                status=VirtualEnvStatus.WRONG_VERSION,
                path=venv_path,
                python_version=extracted_version,
                python_executable=exe_path,
                details=(
                    f"Virtual environment Python version ({extracted_version}) "
                    f"does not satisfy required constraint '{required_version}'"
                ),
            )

    # 5. VALID
    ver_str = f"Python {extracted_version}" if extracted_version else "intact"
    return VirtualEnvInspection(
        status=VirtualEnvStatus.VALID,
        path=venv_path,
        python_version=extracted_version,
        python_executable=exe_path,
        details=f"Usable virtual environment ({ver_str}) at {venv_path}",
    )
