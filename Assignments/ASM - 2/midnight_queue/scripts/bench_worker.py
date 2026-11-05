"""Isolated worker for one timed full-sort run.

Input loading/copying and correctness verification happen outside the timed
region.  The parent process enforces the 300-second rule.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

from midnight_queue.records import (
    Counters,
    TriageOrder,
    bands_non_increasing,
    is_sorted,
    triage_key,
)
from midnight_queue.sorting import SORT_ALGORITHMS
from midnight_queue.deadline import algorithm_deadline


def verify(records, output, mode: str):
    if mode == "triage":
        expected = sorted(records, key=triage_key)
        return bool(output == expected and is_sorted(output, TriageOrder()))
    return bool(
        bands_non_increasing(output)
        and sorted(t.txn_id for t in output)
        == sorted(t.txn_id for t in records)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True)
    parser.add_argument("--algorithm", required=True)
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--timeout",type=float,default=300)
    args = parser.parse_args()
    if args.cpu is not None:
        try:
            import psutil
            psutil.Process().cpu_affinity([args.cpu])
        except (ImportError, OSError, ValueError):
            pass

    with Path(args.cache).open("rb") as handle:
        payload = pickle.load(handle)
    records = payload["records"]
    mode = payload["mode"]
    algorithm = SORT_ALGORITHMS[args.algorithm]
    counters = Counters()
    order = TriageOrder(mode, counters)
    work = list(records)  # fresh copy outside the timer

    if args.memory:
        import tracemalloc

        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            output = algorithm(work, order, counters)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        elapsed = None
    else:
        import time

        with algorithm_deadline(args.timeout):
            start = time.perf_counter()
            output = algorithm(work, order, counters)
            elapsed = time.perf_counter() - start
        peak = None

    correct = verify(records, output, mode)
    result = {
        "algorithm": args.algorithm,
        "mode": mode,
        "n": len(records),
        "elapsed_s": elapsed,
        "peak_extra_bytes": peak,
        "comparisons": counters.comparisons,
        "moves": counters.moves,
        "correct": correct,
        "output_ids_digest": __import__("hashlib").blake2b(
            ",".join(str(t.txn_id) for t in output).encode(), digest_size=16
        ).hexdigest(),
    }
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
