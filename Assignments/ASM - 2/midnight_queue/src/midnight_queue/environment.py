"""Environment capture for reproducibility."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psutil


def _cpu_name() -> str:
    if platform.system() == "Windows":
        try:
            output = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor).Name",
                ],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=15,
            )
            name = output.strip().splitlines()[0].strip()
            if name:
                return name
        except (OSError, subprocess.SubprocessError, IndexError):
            pass
    return platform.processor() or "unknown"


def environment_info(project_root: Path) -> dict[str, object]:
    memory = psutil.virtual_memory()
    return {
        "os": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "cpu": _cpu_name(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cpus": psutil.cpu_count(logical=True),
        "max_cpu_mhz": psutil.cpu_freq().max if psutil.cpu_freq() else None,
        "memory_total_bytes": int(memory.total),
        "python": sys.version,
        "python_executable": sys.executable,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "project_root": str(project_root),
    }


def write_environment(project_root: Path, destination: Path) -> dict[str, object]:
    info = environment_info(project_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info
