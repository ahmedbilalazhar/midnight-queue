"""Problem A evidence, fraud-capture curve, and C6 band-group analysis."""

from __future__ import annotations

import csv
import json
import pickle
from pathlib import Path

import numpy as np

from midnight_queue.config import CONFIG, DEFAULT_DATA_PATH, PROJECT_ROOT
from midnight_queue.data import dataset_profile, load_dataset
from midnight_queue.records import Counters, TriageOrder, triage_key
from midnight_queue.sorting import count_inversions

ANALYSIS_DIR = PROJECT_ROOT / "outputs" / "analysis"


def _lomuto_band_comparisons(bands: list[int]) -> int:
    """Exact comparison count for last-pivot Lomuto using only band keys.

    This integer model mirrors the declared partition rule (<= goes left) and
    contains no record movement, so it is a derivation check rather than a
    second implementation of the contender.
    """

    a = list(bands)
    comparisons = 0
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            comparisons += hi - lo
            pivot = a[hi]
            i = lo
            for j in range(lo, hi):
                if a[j] >= pivot:
                    a[i], a[j] = a[j], a[i]
                    i += 1
            a[i], a[hi] = a[hi], a[i]
            if i - lo < hi - i:
                if i + 1 < hi:
                    stack.append((i + 1, hi))
                hi = i - 1
            else:
                if lo < i - 1:
                    stack.append((lo, i - 1))
                lo = i + 1
    return comparisons


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset(DEFAULT_DATA_PATH)
    profile = dataset_profile(dataset)
    manifest = json.loads(
        (PROJECT_ROOT / "outputs" / "cache" / "manifest.json").read_text()
    )
    c1 = pickle.loads(
        (PROJECT_ROOT / "outputs" / "cache" / "C1_n284807.pkl").read_bytes()
    )["records"]

    # Raw-file ordering evidence.
    time_sorted = all(a.time <= b.time for a, b in zip(c1, c1[1:]))
    triage_adjacent = sum(
        1 for a, b in zip(c1, c1[1:]) if TriageOrder().cmp(a, b) <= 0
    ) / (len(c1) - 1)
    band_adjacent = sum(1 for a, b in zip(c1, c1[1:]) if a.band >= b.band) / (
        len(c1) - 1
    )
    print("Counting inversions in raw C1...", flush=True)
    inversions = count_inversions(c1, TriageOrder())

    # Fraud capture curve from the complete triage reference (evaluation only).
    print("Ranking full file for fraud-capture evaluation...", flush=True)
    ranked = sorted(c1, key=triage_key)
    labels = np.fromiter((t.label for t in ranked), dtype=np.int64)
    cumulative = np.cumsum(labels)
    total_frauds = int(cumulative[-1])
    half = (total_frauds + 1) // 2
    k_half = int(np.argmax(cumulative >= half) + 1)
    curve_path = ANALYSIS_DIR / "fraud_curve.csv"
    with curve_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["k", "frauds_captured", "total_frauds", "fraction"])
        for k in range(1, len(cumulative) + 1):
            captured = int(cumulative[k - 1])
            writer.writerow([k, captured, total_frauds, captured / total_frauds])

    capture_points = {}
    for k in (10, 50, CONFIG.k, 500, 5000, 10_000, 50_000, 100_000, 284_807):
        if k <= len(cumulative):
            captured = int(cumulative[k - 1])
            capture_points[str(k)] = {
                "frauds": captured,
                "fraction": captured / total_frauds,
            }
    capture_points[str(k_half)] = {
        "frauds": int(cumulative[k_half - 1]),
        "fraction": int(cumulative[k_half - 1]) / total_frauds,
    }

    # M6: exact band-only Lomuto comparison prediction from the real groups.
    c6_counts = {}
    for n in CONFIG.sizes:
        key = str(n)
        if key not in manifest["sizes"]:
            continue
        c6 = pickle.loads(
            (
                PROJECT_ROOT
                / manifest["sizes"][key]["conditions"]["C6"]["cache_file"]
            ).read_bytes()
        )["records"]
        bands = [t.band for t in c6]
        group_sizes = [bands.count(b) for b in sorted(set(bands))]
        quadratic = sum(m * (m - 1) // 2 for m in group_sizes)
        # The element-level simulation is only cheap while the quadratic
        # group term fits in a few million operations.  For 100k/full the
        # closed-form group term is the honest prediction; simulating it
        # would take hours and add no information.
        exact = (
            _lomuto_band_comparisons(bands)
            if len(bands) <= 10_000
            else None
        )
        c6_counts[key] = {
            "band_sizes": {
                str(b): bands.count(b) for b in sorted(set(bands))
            },
            "predicted_comparisons_group_formula": quadratic,
            "predicted_comparisons_exact_sequence": exact,
            "n": len(bands),
        }
        print(
            f"M6 n={n:,}: group-quadratic prediction="
            f"{quadratic:,}; exact model={exact if exact is None else format(exact, ',')}",
            flush=True,
        )

    output = {
        "profile": profile,
        "raw_order_evidence": {
            "time_sorted": time_sorted,
            "triage_adjacent_share": triage_adjacent,
            "band_adjacent_share": band_adjacent,
            "triage_inversions": inversions,
            "n": len(c1),
            "max_possible_inversions": len(c1) * (len(c1) - 1) // 2,
        },
        "fraud_capture": {
            "total_frauds": total_frauds,
            "half_threshold": half,
            "k_half": k_half,
            "points": capture_points,
        },
        "c6_band_analysis": c6_counts,
        "inversions_c5": {
            key: value["c5_inversions"]
            for key, value in manifest["sizes"].items()
        },
        "sizes_sampled": list(manifest["sizes"]),
    }
    (ANALYSIS_DIR / "data_analysis.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print(f"K_half={k_half:,}; frauds={total_frauds}; output -> {ANALYSIS_DIR}")


if __name__ == "__main__":
    main()
