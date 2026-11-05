"""Validate every contender against the reference on real sampled conditions."""

from __future__ import annotations

import argparse
import time

from midnight_queue.config import CONFIG, DEFAULT_DATA_PATH
from midnight_queue.conditions import build_conditions
from midnight_queue.data import load_dataset, sample_records
from midnight_queue.records import (
    Counters,
    OrderMode,
    TriageOrder,
    bands_non_increasing,
    is_sorted,
)
from midnight_queue.reference import reference_band_stable, reference_triage
from midnight_queue.sorting import SORT_ALGORITHMS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    args = parser.parse_args()
    ds = load_dataset(DEFAULT_DATA_PATH, verify_checksum=False)
    records = sample_records(ds.records, args.n, CONFIG.seed)
    conditions = build_conditions(records, CONFIG.seed)
    print(f"n={args.n}, conditions built from {len(records)} records")
    failures = 0
    for cid, condition in conditions.items():
        if condition.order_mode == "triage":
            reference = reference_triage(condition.records)
        else:
            reference = reference_band_stable(condition.records)
        for name, algorithm in SORT_ALGORITHMS.items():
            counters = Counters()
            start = time.perf_counter()
            output = algorithm(
                list(condition.records),
                TriageOrder(condition.order_mode, counters),
                counters,
            )
            elapsed = time.perf_counter() - start
            if condition.order_mode == "triage":
                ok = output == reference and is_sorted(output, TriageOrder())
            else:
                ok = (
                    bands_non_increasing(output)
                    and sorted(t.txn_id for t in output)
                    == sorted(t.txn_id for t in condition.records)
                )
            failures += not ok
            print(
                f"{cid:>2} {name:<21} {'OK' if ok else 'FAIL':<4} "
                f"{elapsed:8.4f}s cmp={counters.comparisons:>9} "
                f"moves={counters.moves:>9}"
            )
    if failures:
        raise SystemExit(f"{failures} validation failures")


if __name__ == "__main__":
    main()
