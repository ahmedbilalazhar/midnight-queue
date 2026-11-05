"""Shared results.csv schema."""

from __future__ import annotations

RESULT_FIELDS = [
    "record_type",
    "problem",
    "experiment",
    "prediction_id",
    "algorithm",
    "strategy",
    "condition",
    "n",
    "k",
    "width_s",
    "window",
    "repeat",
    "elapsed_s",
    "median_s",
    "run_count",
    "comparisons",
    "moves",
    "peak_extra_bytes",
    "correct",
    "stable",
    "dnf",
    "dnf_reason",
    "extrapolated",
    "largest_completed_n",
    "fraud_capture_count",
    "fraud_fraction",
    "queue_size",
    "seen",
    "window_records",
    "cumulative_s",
    "notes",
]


def result_row(**kwargs) -> dict[str, object]:
    unknown = set(kwargs) - set(RESULT_FIELDS)
    if unknown:
        raise KeyError(f"unknown result fields: {sorted(unknown)}")
    row = {field: "" for field in RESULT_FIELDS}
    row.update(kwargs)
    return row
