"""Run Problem E: repeated ranking, maintained heap, and window-merge."""

from __future__ import annotations

import argparse
import csv
import json
import os
import pickle
import statistics
import subprocess
import sys
import time
from pathlib import Path

from midnight_queue.config import CONFIG, PROJECT_ROOT
from midnight_queue.livefeed import build_expected_queues
from midnight_queue.predictions import add_prediction, update_outcome
from midnight_queue.results import RESULT_FIELDS, result_row

STRATEGIES = ("rerank", "heap", "merge")


def _read(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    if path.exists():
        path.with_suffix(".csv.bak").write_bytes(path.read_bytes())
    os.replace(tmp, path)


def _run(cache: Path, expected: Path, strategy: str, width: int, timeout: int, memory=False):
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "livefeed_worker.py"),
        "--cache",
        str(cache),
        "--expected",
        str(expected),
        "--strategy",
        strategy,
        "--width",
        str(width),
        "--k",
        str(CONFIG.k),
        "--timeout",
        str(timeout),
    ]
    if memory:
        command.append("--memory")
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
    if completed.returncode==124:
        return None
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:])
    payload=json.loads(completed.stdout.strip().splitlines()[-1])
    if not memory and payload["elapsed_s"]>timeout:
        return None
    if not payload["correct"]:
        raise RuntimeError("A live publication differs from the trusted reference")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--memory-timeout",type=int,default=1800)
    parser.add_argument("--widths", default="3600,600")
    parser.add_argument("--strategies", default="rerank,heap,merge")
    parser.add_argument("--memory", action="store_true", default=False)
    parser.add_argument("--no-memory", dest="memory", action="store_false")
    args = parser.parse_args()
    result_path = PROJECT_ROOT / "outputs" / "raw" / "livefeed.csv"
    prediction_path = PROJECT_ROOT / "prediction_log.csv"
    rows = _read(result_path)
    cache = PROJECT_ROOT / "outputs" / "cache" / "C1_n284807.pkl"
    with cache.open("rb") as handle:
        records = pickle.load(handle)["records"]
    started = time.perf_counter()

    for width in [int(x) for x in args.widths.split(",")]:
        expected_path = PROJECT_ROOT / "outputs" / "cache" / f"live_expected_{width}.pkl"
        if not expected_path.exists():
            print(f"Building verification queues for width={width}s...", flush=True)
            expected = build_expected_queues(records, width, CONFIG.k)
            with expected_path.open("wb") as handle:
                pickle.dump(expected, handle, protocol=pickle.HIGHEST_PROTOCOL)
        add_prediction(
            prediction_path,
            prediction_id=f"live-width{width}",
            problem="E",
            round_id=f"E_width{width}",
            n=len(records),
            k=CONFIG.k,
            width_s=width,
            predicted_fastest="heap",
            predicted_slowest="rerank",
            rationale=(
                "The maintained size-K heap touches each arriving record once and "
                "never re-ranks history. Repeated ranking re-sorts the entire prefix "
                "each window, giving about w n log n in the worst case. Window-merge "
                "sorts each small window and merges only K, so I expect it between "
                "the two, possibly close to heap for ten-minute windows."
            ),
        )
        print(f"\n=== Live feed width={width}s ===", flush=True)
        totals: dict[str, float | None] = {}
        for strategy in [x for x in args.strategies.split(",")]:
            done = any(
                r
                for r in rows
                if r.get("strategy") == strategy
                and str(r.get("width_s")) == str(width)
                and r.get("record_type") in ("summary","dnf")
            )
            if done:
                existing = [
                    r
                    for r in rows
                    if r.get("experiment") == "livefeed_summary"
                    and r.get("strategy") == strategy
                    and str(r.get("width_s")) == str(width)
                ]
                totals[strategy] = (
                    float(existing[0]["median_s"]) if existing else None
                )
                continue
            strategy_totals=[float(r["elapsed_s"]) for r in rows
                             if r.get("record_type")=="run_total" and r.get("strategy")==strategy
                             and str(r.get("width_s"))==str(width)]
            dnf = False
            for repeat in range(len(strategy_totals)+1, args.repeats + 1):
                try:
                    payload = _run(
                        cache, expected_path, strategy, width, args.timeout, False
                    )
                except RuntimeError as exc:
                    print(f"  {strategy}: ERROR {exc}", flush=True)
                    _write(result_path,rows)
                    raise
                if payload is None:
                    dnf = True
                    rows.append(
                        result_row(
                            record_type="dnf",
                            problem="E",
                            experiment="livefeed",
                            strategy=strategy,
                            n=len(records),
                            k=CONFIG.k,
                            width_s=width,
                            repeat=repeat,
                            dnf=True,
                            dnf_reason=f"exceeded {args.timeout}s watchdog",
                        )
                    )
                    break
                strategy_totals.append(float(payload["elapsed_s"]))
                rows.append(result_row(record_type="run_total",problem="E",experiment="livefeed_total",
                    strategy=strategy,n=len(records),k=CONFIG.k,width_s=width,repeat=repeat,
                    elapsed_s=payload["elapsed_s"],correct=True,dnf=False,
                    notes="sum of algorithm-only window timers; verification excluded"))
                for window_row in payload["rows"]:
                    rows.append(
                        result_row(
                            record_type="run",
                            problem="E",
                            experiment="livefeed",
                            strategy=strategy,
                            n=len(records),
                            k=CONFIG.k,
                            width_s=width,
                            window=window_row["window"],
                            repeat=repeat,
                            elapsed_s=window_row["elapsed_s"],
                            comparisons=window_row["comparisons"],
                            moves=window_row["moves"],
                            correct=window_row["correct"],
                            dnf=False,
                            seen=window_row["seen"],
                            window_records=window_row["window_records"],
                            cumulative_s=window_row["cumulative_s"],
                            queue_size=window_row["queue_size"],
                        )
                    )
                print(
                    f"  {strategy}: rep {repeat} total={payload['elapsed_s']:.3f}s "
                    f"windows={payload['windows']} correct={payload['correct']}",
                    flush=True,
                )
                _write(result_path, rows)
            if dnf or len(strategy_totals) != args.repeats:
                totals[strategy] = None
                _write(result_path, rows)
                continue
            med = statistics.median(strategy_totals)
            totals[strategy] = med
            rows.append(
                result_row(
                    record_type="summary",
                    problem="E",
                    experiment="livefeed_summary",
                    strategy=strategy,
                    n=len(records),
                    k=CONFIG.k,
                    width_s=width,
                    median_s=med,
                    run_count=len(strategy_totals),
                    correct=all(
                        str(r.get("correct")).lower() == "true"
                        for r in rows
                        if r.get("experiment") == "livefeed"
                        and r.get("strategy") == strategy
                        and str(r.get("width_s")) == str(width)
                    ),
                    dnf=False,
                    notes="median of complete live-feed simulations",
                )
            )
            if args.memory:
                memory_payload = _run(
                    cache, expected_path, strategy, width, args.memory_timeout, True
                )
                if memory_payload is None:
                    raise RuntimeError("Memory worker did not complete")
                if memory_payload is not None:
                    rows.append(
                        result_row(
                            record_type="memory",
                            problem="E",
                            experiment="livefeed",
                            strategy=strategy,
                            n=len(records),
                            k=CONFIG.k,
                            width_s=width,
                            peak_extra_bytes=memory_payload["peak_extra_bytes"],
                            correct=memory_payload["correct"],
                            notes="tracemalloc, separate from timing",
                        )
                    )
            _write(result_path, rows)

        completed = {k: v for k, v in totals.items() if v is not None}
        if completed:
            fastest = min(completed, key=completed.get)
            slowest_pool = dict(completed)
            for missing in set(totals) - set(completed):
                slowest_pool[missing] = float("inf")
            slowest = max(slowest_pool, key=slowest_pool.get)
            prediction = next(
                (
                    r
                    for r in _read(prediction_path)
                    if r["prediction_id"] == f"live-width{width}"
                ),
                None,
            )
            if prediction:
                update_outcome(
                    prediction_path,
                    f"live-width{width}",
                    actual_fastest=fastest,
                    actual_slowest=slowest,
                    outcome=(
                        "both correct"
                        if prediction["predicted_fastest"] == fastest
                        and prediction["predicted_slowest"] == slowest
                        else "partly/wrong"
                    ),
                )
        _write(result_path, rows)

    from refresh_prediction_outcomes import reconcile
    reconcile()
    print(f"Live-feed runs finished in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
