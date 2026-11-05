"""Run the full-sort tournament with one pinned worker per cell.

Each cell is one (algorithm, condition, size) combination.  A worker performs
five timed repetitions on fresh copies of the same input and verifies the
result outside the timer.  The parent writes the CSV atomically after every
completed cell, so an interrupted session cannot truncate earlier results.

Known catastrophic cells are handled by ``run_dnf.py`` and are skipped here.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from midnight_queue.predictions import add_tournament_round, update_outcome
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
SIZES = (1_000, 10_000, 100_000, 284_807)
REPEATS = 5
CPU_SLOTS = (0, 2, 4, 6)

KNOWN_DNF = {
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
}


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    backup = path.with_suffix(".csv.bak")
    if path.exists():
        backup.write_bytes(path.read_bytes())
    os.replace(tmp, path)


def run_cell(task: dict) -> dict:
    """Enforce the deadline separately for every repetition, never a median."""
    from run_tournament import _run_worker
    elapsed = []
    comparisons = moves = None
    timed_out = False
    for _ in range(task["repeats"]):
        payload = _run_worker(Path(task["cache"]), task["algorithm"],
                              task.get("timeout",300), memory=False, cpu=task.get("cpu"))
        if payload is None:
            timed_out = True
            break
        if not payload["correct"]:
            raise RuntimeError(f"Correctness failure: {task['algorithm']}")
        if comparisons is not None and (payload["comparisons"] != comparisons or payload["moves"] != moves):
            raise RuntimeError("Logical counts changed between identical repetitions")
        comparisons, moves = payload["comparisons"], payload["moves"]
        elapsed.append(payload["elapsed_s"])
    return {
        "algorithm":task["algorithm"], "condition":task["condition"], "n":task["n"],
        "elapsed":elapsed, "comparisons":comparisons, "moves":moves,
        "correct":True, "dnf":timed_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", default="outputs/raw/tournament.csv")
    parser.add_argument("--timeout",type=int,default=300)
    args = parser.parse_args()
    if not 1<=args.workers<=4:
        parser.error("workers must be between 1 and 4")

    manifest = json.loads(
        (PROJECT_ROOT / "outputs" / "cache" / "manifest.json").read_text()
    )
    result_path = PROJECT_ROOT / args.output
    prediction_path = PROJECT_ROOT / "prediction_log.csv"
    rows = _read(result_path)

    done = {
        (
            row.get("algorithm"),
            row.get("condition"),
            int(row.get("n") or 0),
        )
        for row in rows
        if row.get("record_type") in {"median", "dnf"}
    }
    tasks = []
    for n in SIZES:
        for condition in CONDITIONS:
            add_tournament_round(prediction_path, condition, n)
            cache = PROJECT_ROOT / manifest["sizes"][str(n)]["conditions"][condition][
                "cache_file"
            ]
            for algorithm in ALGORITHMS:
                key = (algorithm, condition, n)
                if key in done:
                    continue
                tasks.append(
                    {
                        "algorithm": algorithm,
                        "condition": condition,
                        "n": n,
                        "cache": str(cache),
                        "repeats": REPEATS,
                        "timeout": args.timeout,
                    }
                )

    def estimate(task: dict) -> float:
        """Rough measured-cost proxy, used only for longest-first scheduling."""
        n = task["n"]
        algorithm = task["algorithm"]
        condition = task["condition"]
        if algorithm == "Insertion Sort":
            if condition == "C3":
                return n / 2_000_000
            if condition == "C5":
                return n * n / 6.0e8
            return n * n / 3.0e8
        if algorithm == "Naive Quick Sort":
            if condition == "C5":
                return n * n / 6.0e8
            if condition in {"C3", "C4", "C6"}:
                return n * n / 8.0e8
            return n * 1.5e-5
        if algorithm == "Hardened Quick Sort":
            return n * (1.0e-5 if condition == "C4" else 4.0e-6)
        return n * 8.0e-7

    tasks.sort(key=estimate, reverse=True)
    print(
        f"{len(tasks)} cells to measure with {args.workers} pinned workers "
        f"(longest first)",
        flush=True,
    )
    if not tasks:
        print("Nothing to do.")
        return

    completed = 0
    started = time.perf_counter()
    import psutil
    allowed=psutil.Process().cpu_affinity() if hasattr(psutil.Process(),"cpu_affinity") else list(range(os.cpu_count() or 1))
    cpus=[c for c in CPU_SLOTS if c in allowed] or allowed
    slots=Queue()
    for cpu in cpus[:args.workers]: slots.put(cpu)
    def measure(task):
        cpu=slots.get()
        try:
            return run_cell(dict(task,cpu=cpu))
        finally:
            slots.put(cpu)
    with ThreadPoolExecutor(max_workers=min(args.workers,len(cpus))) as pool:
        futures = {}
        for index, task in enumerate(tasks):
            futures[pool.submit(measure, task)] = task
        for future in as_completed(futures):
            task = futures[future]
            payload = future.result()
            prediction_id = f"tournament-{task['condition']}-n{task['n']}"
            elapsed = payload["elapsed"]
            for repeat, seconds in enumerate(elapsed, start=1):
                rows.append(
                    result_row(
                        record_type="run",
                        problem="C",
                        experiment="full_sort",
                        prediction_id=prediction_id,
                        algorithm=task["algorithm"],
                        condition=task["condition"],
                        n=task["n"],
                        repeat=repeat,
                        elapsed_s=seconds,
                        comparisons=payload["comparisons"],
                        moves=payload["moves"],
                        correct=payload["correct"],
                        dnf=False,
                        stable=STABILITY[task["algorithm"]],
                        notes="pinned worker; fresh copy outside timer",
                    )
                )
            if payload.get("dnf"):
                rows.append(result_row(
                    record_type="dnf",problem="C",experiment="full_sort",
                    prediction_id=prediction_id,algorithm=task["algorithm"],
                    condition=task["condition"],n=task["n"],repeat=len(elapsed)+1,
                    dnf=True,dnf_reason=f"exceeded {args.timeout}s per-run watchdog",
                    stable=STABILITY[task["algorithm"]],
                ))
                _write(result_path,rows)
                completed += 1
                print(f"[{completed}/{len(tasks)}] {task['algorithm']} "
                      f"{task['condition']} n={task['n']:,}: DNF",flush=True)
                continue
            median = statistics.median(elapsed)
            rows.append(
                result_row(
                    record_type="median",
                    problem="C",
                    experiment="full_sort",
                    prediction_id=prediction_id,
                    algorithm=task["algorithm"],
                    condition=task["condition"],
                    n=task["n"],
                    median_s=median,
                    run_count=len(elapsed),
                    comparisons=payload["comparisons"],
                    moves=payload["moves"],
                    correct=payload["correct"],
                    dnf=False,
                    stable=STABILITY[task["algorithm"]],
                    notes=(
                        "median of five completed runs; one cell per pinned "
                        "logical CPU, fresh input copy outside timer"
                    ),
                )
            )
            _write(result_path, rows)
            completed += 1
            print(
                f"[{completed}/{len(tasks)}] {task['algorithm']} "
                f"{task['condition']} n={task['n']:,}: median {median:.4f}s "
                f"({time.perf_counter() - started:.0f}s elapsed)",
                flush=True,
            )

    # Recompute every tournament outcome from the finished table.
    rows = _read(result_path)
    for n in SIZES:
        for condition in CONDITIONS:
            prediction_id = f"tournament-{condition}-n{n}"
            medians = {
                row["algorithm"]: float(row["median_s"])
                for row in rows
                if row.get("experiment") == "full_sort"
                and row.get("record_type") == "median"
                and row.get("condition") == condition
                and str(row.get("n")) == str(n)
            }
            dnfs = {
                row["algorithm"]
                for row in rows
                if row.get("experiment") == "full_sort"
                and row.get("record_type") == "dnf"
                and row.get("condition") == condition
                and str(row.get("n")) == str(n)
            }
            if len(medians) + len(dnfs) < len(ALGORITHMS):
                continue
            fastest = min(medians, key=medians.get)
            slowest_pool = dict(medians)
            for name in dnfs:
                slowest_pool[name] = float("inf")
            slowest = max(slowest_pool, key=slowest_pool.get)
            predicted = next(
                (
                    row
                    for row in _read(prediction_path)
                    if row["prediction_id"] == prediction_id
                ),
                None,
            )
            if predicted:
                cf = predicted["predicted_fastest"] == fastest
                cs = predicted["predicted_slowest"] == slowest
                outcome = (
                    "both correct"
                    if cf and cs
                    else "fastest correct"
                    if cf
                    else "slowest correct"
                    if cs
                    else "both wrong"
                )
                update_outcome(
                    prediction_path,
                    prediction_id,
                    actual_fastest=fastest,
                    actual_slowest=slowest,
                    outcome=outcome,
                    notes="DNF: " + ", ".join(sorted(dnfs)) if dnfs else "",
                )

    print(f"Tournament complete in {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    main()
