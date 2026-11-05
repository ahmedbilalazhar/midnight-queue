"""Consolidate every measured row into the submission's ``results.csv``.

The raw CSVs are deliberately kept separate.  This script only assembles them;
it never recomputes or edits a measurement.  DNF cells are retained with empty
elapsed/median fields, and a clearly labelled quadratic projection is added for
each missing point from the largest completed size of the same cell.
"""

from __future__ import annotations

import csv
from pathlib import Path

from midnight_queue.config import PROJECT_ROOT
from midnight_queue.results import RESULT_FIELDS, result_row

RAW = PROJECT_ROOT / "outputs" / "raw"
OUT = PROJECT_ROOT / "results.csv"

RECORD_ORDER = {
    "run": 0,
    "median": 1,
    "memory": 2,
    "summary": 3,
    "dnf": 4,
    "extrapolation": 5,
}


def read(name: str) -> list[dict[str, str]]:
    path = RAW / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(row: dict, key: str) -> float | None:
    try:
        value = row.get(key, "")
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def add_tournament_extrapolations(rows: list[dict]) -> list[dict]:
    """Add n^2 projections for every DNF cell with a completed smaller size."""

    by_cell: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        if row.get("experiment") != "full_sort":
            continue
        if row.get("record_type") not in {"median", "dnf"}:
            continue
        key = (row.get("algorithm", ""), row.get("condition", ""))
        by_cell.setdefault(key, []).append(row)

    extras: list[dict] = []
    for (algorithm, condition), cell_rows in sorted(by_cell.items()):
        completed = [
            row
            for row in cell_rows
            if row.get("record_type") == "median" and number(row, "median_s")
        ]
        if not completed:
            continue
        source = max(completed, key=lambda row: number(row, "n") or 0)
        source_n = number(source, "n")
        source_s = number(source, "median_s")
        if not source_n or not source_s:
            continue
        for row in cell_rows:
            if row.get("record_type") != "dnf":
                continue
            target_n = number(row, "n")
            if not target_n or target_n <= source_n:
                continue
            projection = source_s * (target_n / source_n) ** 2
            extras.append(
                result_row(
                    record_type="extrapolation",
                    problem="C",
                    experiment="full_sort",
                    algorithm=algorithm,
                    condition=condition,
                    n=int(target_n),
                    median_s=projection,
                    extrapolated=True,
                    dnf=False,
                    largest_completed_n=int(source_n),
                    notes=(
                        "quadratic projection from the largest completed n; "
                        f"t({int(source_n):,})={source_s:.6f}s; not a measurement"
                    ),
                )
            )
    return extras


def sort_key(row: dict):
    n = number(row, "n")
    k = number(row, "k")
    return (
        str(row.get("problem", "")),
        str(row.get("experiment", "")),
        str(row.get("condition", "")),
        -1 if n is None else n,
        -1 if k is None else k,
        str(row.get("algorithm", "")),
        str(row.get("strategy", "")),
        RECORD_ORDER.get(str(row.get("record_type", "")), 9),
        number(row, "width_s") or 0,
        number(row, "window") or 0,
        number(row, "repeat") or 0,
    )


def main() -> None:
    rows: list[dict] = []
    rows.extend(read("tournament.csv"))
    rows.extend(add_tournament_extrapolations(rows[:]))
    rows.extend(read("topk.csv"))
    rows.extend(read("livefeed.csv"))
    rows.extend(read("console.csv"))

    # Drop exact duplicate rows while preserving provenance.  A row is a
    # duplicate only when every field, including its run number, is identical.
    seen: set[tuple[str, ...]] = set()
    unique: list[dict] = []
    for row in rows:
        key = tuple(str(row.get(field, "")) for field in RESULT_FIELDS)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    unique.sort(key=sort_key)
    tmp = OUT.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(unique)
    tmp.replace(OUT)

    counts: dict[str, int] = {}
    for row in unique:
        kind = str(row.get("record_type", ""))
        counts[kind] = counts.get(kind, 0) + 1
    print(f"wrote {OUT} with {len(unique):,} rows")
    print(", ".join(f"{key}={value}" for key, value in sorted(counts.items())))


if __name__ == "__main__":
    main()
