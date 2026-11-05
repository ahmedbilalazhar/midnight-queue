"""Run the full-sort tournament with a per-run subprocess watchdog."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

from midnight_queue.config import CONFIG, PROJECT_ROOT
from midnight_queue.predictions import (
    add_tournament_round,
    update_outcome,
)
from midnight_queue.results import RESULT_FIELDS, result_row
from midnight_queue.sorting import STABILITY

ALGORITHM_ORDER = [
    "Merge Sort",
    "Hardened Quick Sort",
    "Heap Sort",
    "Insertion Sort",
    "Naive Quick Sort",
]
CONDITIONS = ("C1", "C2", "C3", "C4", "C5", "C6")


def _read_existing(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _completed_round(rows, condition: str, n: int) -> bool:
    return any(
        row.get("experiment") == "full_sort"
        and row.get("condition") == condition
        and str(row.get("n")) == str(n)
        and row.get("record_type") == "dnf"
        for row in rows
    )


def _run_worker(cache: Path, algorithm: str, timeout: int, memory: bool, cpu: int | None = None) -> dict | None:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "bench_worker.py"),
        "--cache",
        str(cache),
        "--algorithm",
        algorithm,
        "--timeout",
        str(timeout),
    ]
    if memory:
        command.append("--memory")
    if cpu is not None:
        command.extend(["--cpu",str(cpu)])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout+120,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Worker exceeded its preparation/verification envelope; algorithm DNF is unproven") from exc
    if completed.returncode == 124:
        return None
    if completed.returncode != 0:
        raise RuntimeError(
            f"worker failed ({completed.returncode}): {completed.stderr[-2000:]}"
        )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    if not memory and payload["elapsed_s"] > timeout:
        return None
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--sizes", default="1000,10000,100000,284807")
    parser.add_argument("--conditions", default="C1,C2,C3,C4,C5,C6")
    parser.add_argument("--algorithms", default=",".join(ALGORITHM_ORDER))
    parser.add_argument("--memory", action="store_true", default=True)
    parser.add_argument("--no-memory", dest="memory", action="store_false")
    parser.add_argument("--skip-dnf", action="store_true", help="skip known DNF sizes")
    args = parser.parse_args()

    sizes = [int(x) for x in args.sizes.split(",") if x]
    conditions = [x for x in args.conditions.split(",") if x]
    algorithms = [x for x in args.algorithms.split(",") if x]
    manifest = json.loads(
        (PROJECT_ROOT / "outputs" / "cache" / "manifest.json").read_text()
    )
    result_path = PROJECT_ROOT / "outputs" / "raw" / "tournament.csv"
    prediction_path = PROJECT_ROOT / "prediction_log.csv"
    rows = _read_existing(result_path)
    run_started = time.perf_counter()

    for n in sizes:
        if str(n) not in manifest["sizes"]:
            print(f"Skipping unavailable n={n}")
            continue
        for condition in conditions:
            cache = PROJECT_ROOT / manifest["sizes"][str(n)]["conditions"][
                condition
            ]["cache_file"]
            prediction_id = add_tournament_round(prediction_path, condition, n)
            print(f"\n=== {condition} n={n:,} ===", flush=True)
            round_times: dict[str, float | None] = {}
            dnf_names: list[str] = []
            for algorithm in algorithms:
                done = any(
                    r.get("experiment") == "full_sort"
                    and r.get("condition") == condition
                    and r.get("algorithm") == algorithm
                    and str(r.get("n")) == str(n)
                    and r.get("record_type") in {"median", "dnf"}
                    for r in rows
                )
                if done:
                    existing = [
                        r
                        for r in rows
                        if r.get("experiment") == "full_sort"
                        and r.get("condition") == condition
                        and r.get("algorithm") == algorithm
                        and str(r.get("n")) == str(n)
                        and r.get("record_type") == "median"
                    ]
                    round_times[algorithm] = (
                        float(existing[0]["median_s"]) if existing else None
                    )
                    if not existing:
                        dnf_names.append(algorithm)
                    continue

                samples: list[dict] = []
                timed_out = False
                for repeat in range(1, args.repeats + 1):
                    try:
                        payload = _run_worker(
                            cache, algorithm, args.timeout, memory=False
                        )
                    except RuntimeError as exc:
                        print(f"  {algorithm}: ERROR {exc}", flush=True)
                        rows.append(
                            result_row(
                                record_type="failure",
                                problem="C",
                                experiment="full_sort",
                                prediction_id=prediction_id,
                                algorithm=algorithm,
                                condition=condition,
                                n=n,
                                repeat=repeat,
                                correct=False,
                                dnf=False,
                                dnf_reason=f"worker error: {exc}",
                                stable=STABILITY[algorithm],
                            )
                        )
                        _write(result_path,rows)
                        raise
                    if payload is None:
                        timed_out = True
                        print(
                            f"  {algorithm}: DNF after >{args.timeout}s on repeat {repeat}",
                            flush=True,
                        )
                        rows.append(
                            result_row(
                                record_type="dnf",
                                problem="C",
                                experiment="full_sort",
                                prediction_id=prediction_id,
                                algorithm=algorithm,
                                condition=condition,
                                n=n,
                                repeat=repeat,
                                correct="",
                                dnf=True,
                                dnf_reason=f"exceeded {args.timeout}s watchdog",
                                stable=STABILITY[algorithm],
                            )
                        )
                        break
                    samples.append(payload)
                    rows.append(
                        result_row(
                            record_type="run",
                            problem="C",
                            experiment="full_sort",
                            prediction_id=prediction_id,
                            algorithm=algorithm,
                            condition=condition,
                            n=n,
                            repeat=repeat,
                            elapsed_s=payload["elapsed_s"],
                            comparisons=payload["comparisons"],
                            moves=payload["moves"],
                            correct=payload["correct"],
                            dnf=False,
                            stable=STABILITY[algorithm],
                        )
                    )
                    print(
                        f"  {algorithm}: rep {repeat} {payload['elapsed_s']:.4f}s "
                        f"cmp={payload['comparisons']:,} moves={payload['moves']:,} "
                        f"correct={payload['correct']}",
                        flush=True,
                    )
                    _write(result_path, rows)

                if timed_out:
                    round_times[algorithm] = None
                    dnf_names.append(algorithm)
                    _write(result_path, rows)
                    continue
                if len(samples) != args.repeats:
                    round_times[algorithm] = None
                    dnf_names.append(algorithm)
                    continue

                elapsed = [s["elapsed_s"] for s in samples]
                comparisons = {s["comparisons"] for s in samples}
                moves = {s["moves"] for s in samples}
                if len(comparisons) != 1 or len(moves) != 1:
                    raise RuntimeError("instrumentation was not deterministic")
                median = statistics.median(elapsed)
                round_times[algorithm] = median
                rows.append(
                    result_row(
                        record_type="median",
                        problem="C",
                        experiment="full_sort",
                        prediction_id=prediction_id,
                        algorithm=algorithm,
                        condition=condition,
                        n=n,
                        median_s=median,
                        run_count=len(elapsed),
                        comparisons=samples[0]["comparisons"],
                        moves=samples[0]["moves"],
                        correct=all(s["correct"] for s in samples),
                        dnf=False,
                        stable=STABILITY[algorithm],
                        notes="median of five completed runs"
                        if len(elapsed) == 5
                        else "median of completed runs",
                    )
                )

                if args.memory:
                    try:
                        memory_payload = _run_worker(
                            cache, algorithm, args.timeout, memory=True
                        )
                    except RuntimeError as exc:
                        memory_payload = None
                        print(f"  {algorithm}: memory FAILED {exc}", flush=True)
                    if memory_payload is not None:
                        rows.append(
                            result_row(
                                record_type="memory",
                                problem="C",
                                experiment="full_sort",
                                prediction_id=prediction_id,
                                algorithm=algorithm,
                                condition=condition,
                                n=n,
                                peak_extra_bytes=memory_payload["peak_extra_bytes"],
                                correct=memory_payload["correct"],
                                stable=STABILITY[algorithm],
                                notes="tracemalloc, separate from timing",
                            )
                        )
                _write(result_path, rows)

            completed = {k: v for k, v in round_times.items() if v is not None}
            if completed:
                actual_fastest = min(completed, key=completed.get)
                slowest_pool = dict(completed)
                for name in dnf_names:
                    slowest_pool[name] = float("inf")
                actual_slowest = max(slowest_pool, key=slowest_pool.get)
                predicted = next(
                    (
                        r
                        for r in _read_existing(prediction_path)
                        if r["prediction_id"] == prediction_id
                    ),
                    None,
                )
                if predicted:
                    correct_fast = predicted["predicted_fastest"] == actual_fastest
                    correct_slow = predicted["predicted_slowest"] == actual_slowest
                    outcome = (
                        "both correct"
                        if correct_fast and correct_slow
                        else "fastest correct"
                        if correct_fast
                        else "slowest correct"
                        if correct_slow
                        else "both wrong"
                    )
                    update_outcome(
                        prediction_path,
                        prediction_id,
                        actual_fastest=actual_fastest,
                        actual_slowest=actual_slowest,
                        outcome=outcome,
                        notes="DNF: " + ", ".join(dnf_names) if dnf_names else "",
                    )
            _write(result_path, rows)

    print(
        f"\nTournament finished in {time.perf_counter() - run_started:.1f}s; "
        f"results -> {result_path}"
    )


if __name__ == "__main__":
    main()
