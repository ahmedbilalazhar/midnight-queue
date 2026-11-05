"""Measure extra memory for every full-sort contender at n=10,000.

The timing tournament deliberately excludes traced runs.  This script adds one
``memory`` row per (algorithm, condition) cell at the representative n=10,000
size; memory at other sizes is reported analytically in the report.  Keeping
all conditions at the same n makes the table comparable.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from midnight_queue.results import RESULT_FIELDS, result_row
from midnight_queue.sorting import STABILITY

ALGORITHMS = [
    "Merge Sort",
    "Hardened Quick Sort",
    "Heap Sort",
    "Insertion Sort",
    "Naive Quick Sort",
]
CONDITIONS = ("C1", "C2", "C3", "C4", "C5", "C6")
N = 10_000


def _read(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows) -> None:
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def main() -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "outputs" / "cache" / "manifest.json").read_text()
    )
    path = PROJECT_ROOT / "outputs" / "raw" / "tournament.csv"
    rows = _read(path)
    done = {
        (r.get("algorithm"), r.get("condition"))
        for r in rows
        if r.get("record_type") == "memory" and str(r.get("n")) == str(N)
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    for condition in CONDITIONS:
        cache = PROJECT_ROOT / manifest["sizes"][str(N)]["conditions"][condition][
            "cache_file"
        ]
        for algorithm in ALGORITHMS:
            if (algorithm, condition) in done:
                continue
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "bench_worker.py"),
                    "--cache",
                    str(cache),
                    "--algorithm",
                    algorithm,
                    "--memory",
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=300,
            )
            if completed.returncode != 0:
                print(f"FAILED {algorithm} {condition}: {completed.stderr[-300:]}")
                continue
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
            rows.append(
                result_row(
                    record_type="memory",
                    problem="C",
                    experiment="full_sort",
                    algorithm=algorithm,
                    condition=condition,
                    n=N,
                    peak_extra_bytes=payload["peak_extra_bytes"],
                    comparisons=payload["comparisons"],
                    moves=payload["moves"],
                    correct=payload["correct"],
                    stable=STABILITY[algorithm],
                    notes="tracemalloc; n=10,000 representative slice",
                )
            )
            _write(path, rows)
            print(
                f"{condition} {algorithm}: {payload['peak_extra_bytes']:,} bytes",
                flush=True,
            )
    print("Memory rows complete")


if __name__ == "__main__":
    main()
