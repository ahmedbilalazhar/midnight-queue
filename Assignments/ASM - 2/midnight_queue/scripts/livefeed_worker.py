"""Isolated worker for one complete live-feed strategy run."""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

from midnight_queue.livefeed import make_windows, run_live_feed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--timeout",type=float,default=300)
    args = parser.parse_args()
    with Path(args.cache).open("rb") as handle:
        records = pickle.load(handle)["records"]
    with Path(args.expected).open("rb") as handle:
        expected = pickle.load(handle)
    # The window split is shared input, not algorithm workspace.  Build it
    # before tracing so peak extra memory reflects the strategy itself.
    windows = make_windows(records, args.width)

    if args.memory:
        import tracemalloc

        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            result = run_live_feed(
                records,
                args.width,
                args.k,
                args.strategy,
                expected=expected,
                windows=windows,
                keep_queues=False,
            )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        elapsed = None
    else:
        result = run_live_feed(
            records,
            args.width,
            args.k,
            args.strategy,
            expected=expected,
            windows=windows,
            timeout_seconds=args.timeout,
        )
        peak = None
        elapsed = result.total_seconds

    json.dump(
        {
            "strategy": args.strategy,
            "width_s": args.width,
            "k": args.k,
            "elapsed_s": elapsed,
            "wall_s": result.wall_seconds,
            "peak_extra_bytes": peak,
            "rows": result.rows,
            "correct": all(row["correct"] for row in result.rows),
            "windows": len(result.rows),
            "total_comparisons": result.counters.comparisons,
            "total_moves": result.counters.moves,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
