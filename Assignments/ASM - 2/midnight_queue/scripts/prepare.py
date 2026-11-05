"""Build deterministic experiment inputs and the dataset profile."""

from __future__ import annotations

import json
import pickle
import time
from dataclasses import asdict
from pathlib import Path

from midnight_queue.config import CONFIG, DEFAULT_DATA_PATH, PROJECT_ROOT
from midnight_queue.conditions import CONDITION_IDS, build_conditions
from midnight_queue.data import dataset_profile, load_dataset, sample_records
from midnight_queue.environment import write_environment
from midnight_queue.records import Counters, TriageOrder, is_sorted
from midnight_queue.sorting import count_inversions


def main() -> None:
    outputs = PROJECT_ROOT / "outputs"
    cache = outputs / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    write_environment(PROJECT_ROOT, outputs / "environment.json")
    print("Loading and validating the full dataset...")
    dataset = load_dataset(DEFAULT_DATA_PATH)
    profile = dataset_profile(dataset)
    (outputs / "profile.json").write_text(
        json.dumps(profile, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"Loaded {dataset.n:,} rows / {dataset.fraud_count} frauds; "
        f"sha256={dataset.sha256[:16]}..."
    )

    manifest: dict[str, object] = {
        "config": asdict(CONFIG),
        "dataset": {
            "path": str(DEFAULT_DATA_PATH.resolve()),
            "sha256": dataset.sha256,
            "n": dataset.n,
            "frauds": dataset.fraud_count,
        },
        "sizes": {},
    }
    sizes: dict[str, object] = {}
    for n in CONFIG.sizes:
        if n > dataset.n:
            print(f"Skipping n={n}: unavailable")
            continue
        sampled = sample_records(dataset.records, n, CONFIG.seed)
        conditions = build_conditions(sampled, CONFIG.seed)
        assert all(c.n == n for c in conditions.values())
        expected_ids = sorted(t.txn_id for t in sampled)
        for cid in CONDITION_IDS:
            condition = conditions[cid]
            assert sorted(t.txn_id for t in condition.records) == expected_ids
            if cid == "C3":
                assert is_sorted(condition.records, TriageOrder("triage"))
            if cid == "C4":
                assert condition.records == list(reversed(conditions["C3"].records))
            if cid == "C1":
                assert all(
                    a.time <= b.time
                    for a, b in zip(condition.records, condition.records[1:])
                )
            path = cache / f"{cid}_n{n}.pkl"
            with path.open("wb") as handle:
                pickle.dump(
                    {"mode": condition.order_mode, "records": condition.records},
                    handle,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            print(f"  cached {cid} n={n:,} ({path.stat().st_size / 1e6:.1f} MB)")

        # Exact inversion count on C5, using the custom merge counter.
        inversion_counters = Counters()
        inversions = count_inversions(
            conditions["C5"].records,
            TriageOrder(counters=inversion_counters),
        )
        c5_changed = sum(
            1
            for a, b in zip(conditions["C3"].records, conditions["C5"].records)
            if a != b
        )
        band_counts = {}
        for value in range(10):
            band_counts[str(value)] = sum(
                1 for record in conditions["C6"].records if record.band == value
            )
        sizes[str(n)] = {
            "n": n,
            "sample_frauds": sum(t.label for t in sampled),
            "c5_inversions": inversions,
            "c5_changed_positions": c5_changed,
            "c5_expected_changed": int(0.01 * n),
            "band_counts_c6": band_counts,
            "conditions": {
                cid: {
                    "mode": conditions[cid].order_mode,
                    "cache_file": str(
                        (cache / f"{cid}_n{n}.pkl").relative_to(PROJECT_ROOT)
                    ),
                    "n": n,
                }
                for cid in CONDITION_IDS
            },
        }
        print(
            f"n={n:,}: frauds={sizes[str(n)]['sample_frauds']}, "
            f"C5 inversions={inversions:,}, changed={c5_changed}"
        )

    manifest["sizes"] = sizes
    (cache / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    elapsed = time.perf_counter() - started
    print(f"Preparation complete in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
