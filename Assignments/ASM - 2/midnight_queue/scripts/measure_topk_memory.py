"""Add tracemalloc peaks for the operational Top-K cells.

Timing and memory are separate runs.  We measure the two capacities that the
report discusses operationally (K=52 and K=2,068) at both required sizes and
both C1/C2, for the heap and the bounded buffer.  Full-sort memory is already
covered by ``measure_memory.py`` at n=10,000 and is O(n) analytically.
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

CONDITIONS = ("C1", "C2")
SIZES = (100_000, 284_807)
KS = (52, 2_068)
METHODS = ("Size-K Heap", "Bounded Insertion Buffer")


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
    path = PROJECT_ROOT / "outputs" / "raw" / "topk.csv"
    rows = _read(path)
    done = {
        (r.get("algorithm"), r.get("condition"), str(r.get("n")), str(r.get("k")))
        for r in rows
        if r.get("record_type") == "memory"
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    for condition in CONDITIONS:
        for n in SIZES:
            cache = PROJECT_ROOT / manifest["sizes"][str(n)]["conditions"][
                condition
            ]["cache_file"]
            for k in KS:
                for method in METHODS:
                    key = (method, condition, str(n), str(k))
                    if key in done:
                        continue
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(PROJECT_ROOT / "scripts" / "topk_worker.py"),
                            "--cache",
                            str(cache),
                            "--method",
                            method,
                            "--k",
                            str(k),
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
                        print(
                            f"FAILED {method} {condition} n={n} k={k}: "
                            f"{completed.stderr[-300:]}"
                        )
                        continue
                    payload = json.loads(
                        completed.stdout.strip().splitlines()[-1]
                    )
                    rows.append(
                        result_row(
                            record_type="memory",
                            problem="D",
                            experiment="topk",
                            algorithm=method,
                            condition=condition,
                            n=n,
                            k=k,
                            peak_extra_bytes=payload["peak_extra_bytes"],
                            correct=payload["correct"],
                            notes="tracemalloc, separate from timing",
                        )
                    )
                    _write(path, rows)
                    print(
                        f"{condition} n={n:,} K={k:,} {method}: "
                        f"{payload['peak_extra_bytes']:,} bytes",
                        flush=True,
                    )
    print("Top-K memory rows complete")


if __name__ == "__main__":
    main()
