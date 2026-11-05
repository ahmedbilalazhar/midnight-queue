"""Run the known slow tournament cases with a 300 s algorithm-only deadline.

Timeout attempts run concurrently; a DNF has no elapsed time or median.
Host contention remains a limitation of wall-clock deadlines.  Every classification is also backed by
a completed smaller-n operation-count extrapolation.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from midnight_queue.config import PROJECT_ROOT
from midnight_queue.predictions import add_tournament_round
from midnight_queue.results import RESULT_FIELDS, result_row

CASES = [
    ("Insertion Sort", "C5", 284_807),
    ("Insertion Sort", "C1", 100_000),
    ("Insertion Sort", "C2", 100_000),
    ("Insertion Sort", "C4", 100_000),
    ("Insertion Sort", "C6", 100_000),
    ("Naive Quick Sort", "C3", 100_000),
    ("Naive Quick Sort", "C4", 100_000),
    ("Naive Quick Sort", "C6", 100_000),
    ("Insertion Sort", "C1", 284_807),
    ("Insertion Sort", "C2", 284_807),
    ("Insertion Sort", "C4", 284_807),
    ("Insertion Sort", "C6", 284_807),
    ("Naive Quick Sort", "C3", 284_807),
    ("Naive Quick Sort", "C4", 284_807),
    ("Naive Quick Sort", "C6", 284_807),
]


def _read(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run_case(case, manifest) -> dict:
    from run_tournament import _run_worker
    algorithm,condition,n=case
    cache=PROJECT_ROOT/manifest["sizes"][str(n)]["conditions"][condition]["cache_file"]
    started=time.perf_counter()
    payload=_run_worker(cache,algorithm,300,False)
    return {"algorithm":algorithm,"condition":condition,"n":n,
            "outcome":"dnf" if payload is None else "completed_within_300",
            "detail":"exceeded 300s algorithm-only deadline" if payload is None else json.dumps(payload),
            "wall_s":time.perf_counter()-started}


def main() -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "outputs" / "cache" / "manifest.json").read_text()
    )
    result_path = PROJECT_ROOT / "outputs" / "raw" / "tournament.csv"
    prediction_path = PROJECT_ROOT / "prediction_log.csv"
    rows = _read(result_path)
    # Ensure every round has its prediction recorded before the DNF attempt.
    for _, condition, n in CASES:
        add_tournament_round(prediction_path, condition, n)

    pending = []
    for case in CASES:
        algorithm, condition, n = case
        already = any(
            row.get("experiment") == "full_sort"
            and row.get("algorithm") == algorithm
            and row.get("condition") == condition
            and str(row.get("n")) == str(n)
            and row.get("record_type") == "dnf"
            for row in rows
        )
        if not already:
            pending.append(case)
    print(f"{len(pending)} DNF cases to attempt", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(run_case, case, manifest): case for case in pending}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{result['condition']} n={result['n']:,} {result['algorithm']}: "
                f"{result['outcome']} after {result['wall_s']:.1f}s",
                flush=True,
            )
            if result["outcome"] == "dnf":
                rows.append(
                    result_row(
                        record_type="dnf",
                        problem="C",
                        experiment="full_sort",
                        algorithm=result["algorithm"],
                        condition=result["condition"],
                        n=result["n"],
                        repeat=1,
                        correct="",
                        dnf=True,
                        dnf_reason="exceeded 300s watchdog",
                        extrapolated=False,
                        notes=(
                            "genuine timeout attempt; no elapsed time or median "
                            "is recorded. DNF attempts were run four-at-a-time "
                            "because time is not a reported measurement."
                        ),
                    )
                )
            else:
                # Should not happen for the pre-screened cases; preserve proof.
                rows.append(
                    result_row(
                        record_type="unexpected_completion",
                        problem="C",
                        experiment="full_sort",
                        algorithm=result["algorithm"],
                        condition=result["condition"],
                        n=result["n"],
                        correct="",
                        dnf=False,
                        notes=f"completed within 300s: {result['detail']}",
                    )
                )
            _write(result_path, rows)

    if any(r["outcome"] != "dnf" for r in results):
        print("WARNING: a pre-screened case completed; inspect results.", flush=True)
    print("DNF watchdog phase complete", flush=True)


if __name__ == "__main__":
    main()
