"""Isolated worker for one Top-K or full-sort queue run."""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

from midnight_queue.records import Counters, TriageOrder, triage_key
from midnight_queue.sorting import hardened_quicksort
from midnight_queue.topk import topk_buffer, topk_heap
from midnight_queue.deadline import algorithm_deadline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--timeout",type=float,default=300)
    args = parser.parse_args()
    with Path(args.cache).open("rb") as handle:
        payload = pickle.load(handle)
    records = payload["records"]
    if payload["mode"] != "triage":
        raise ValueError("Top-K experiments only use C1/C2")
    counters = Counters()
    order = TriageOrder("triage", counters)

    if args.method == "Full Sort":
        work = list(records)

        def run():
            hardened_quicksort(work, order, counters)
            output = work[: max(0,args.k)]
            counters.moves += len(output)
            return output

    elif args.method == "Size-K Heap":
        work = list(records)

        def run():
            return topk_heap(work, args.k, order, counters)

    elif args.method == "Bounded Insertion Buffer":
        work = list(records)

        def run():
            return topk_buffer(work, args.k, order, counters)

    else:
        raise ValueError(args.method)

    if args.memory:
        import tracemalloc

        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            output = run()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        elapsed = None
    else:
        with algorithm_deadline(args.timeout):
            start = time.perf_counter()
            output = run()
            elapsed = time.perf_counter() - start
        peak = None

    expected = sorted(records, key=triage_key)[: max(0, args.k)]
    correct = output == expected
    json.dump(
        {
            "method": args.method,
            "k": args.k,
            "n": len(records),
            "elapsed_s": elapsed,
            "peak_extra_bytes": peak,
            "comparisons": counters.comparisons,
            "moves": counters.moves,
            "correct": correct,
            "output_size": len(output),
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
