"""Append-only prediction log with outcomes updated after experiments."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
    "prediction_id",
    "problem",
    "round_id",
    "condition",
    "n",
    "k",
    "width_s",
    "predicted_fastest",
    "predicted_slowest",
    "rationale",
    "created_utc",
    "actual_fastest",
    "actual_slowest",
    "outcome",
    "actual_notes",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_predictions(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def add_prediction(
    path: Path,
    *,
    prediction_id: str,
    problem: str,
    round_id: str,
    predicted_fastest: str,
    predicted_slowest: str,
    rationale: str,
    condition: str = "",
    n: int | None = None,
    k: int | None = None,
    width_s: int | None = None,
) -> None:
    rows = read_predictions(path)
    if any(row["prediction_id"] == prediction_id for row in rows):
        return
    rows.append(
        {
            "prediction_id": prediction_id,
            "problem": problem,
            "round_id": round_id,
            "condition": condition,
            "n": "" if n is None else str(n),
            "k": "" if k is None else str(k),
            "width_s": "" if width_s is None else str(width_s),
            "predicted_fastest": predicted_fastest,
            "predicted_slowest": predicted_slowest,
            "rationale": rationale,
            "created_utc": _now(),
            "actual_fastest": "",
            "actual_slowest": "",
            "outcome": "",
            "actual_notes": "",
        }
    )
    _write(path, rows)


def update_outcome(
    path: Path,
    prediction_id: str,
    *,
    actual_fastest: str,
    actual_slowest: str,
    outcome: str,
    notes: str = "",
) -> None:
    rows = read_predictions(path)
    for row in rows:
        if row["prediction_id"] == prediction_id:
            row["actual_fastest"] = actual_fastest
            row["actual_slowest"] = actual_slowest
            row["outcome"] = outcome
            row["actual_notes"] = notes
            break
    else:
        raise KeyError(prediction_id)
    _write(path, rows)


def tournament_prediction(condition: str, n: int) -> tuple[str, str, str]:
    if condition == "C3":
        return (
            "Insertion Sort",
            "Naive Quick Sort",
            "C3 is already triaged; insertion sort sees one linear pass. "
            "Naive last-pivot Lomuto receives the worst element as every "
            "pivot, so its comparison count is quadratic.",
        )
    if condition == "C4":
        return (
            "Hardened Quick Sort",
            "Insertion Sort",
            "C4 is exactly reversed. Insertion sort has every pair inverted; "
            "naive quick sort is also quadratic but moves less. Median-of-three "
            "plus three-way partitioning should remain n log n.",
        )
    if condition == "C5":
        fastest = "Insertion Sort" if n <= 1_000 else "Hardened Quick Sort"
        return (
            fastest,
            "Naive Quick Sort",
            "C5 has only 1% relocation, so insertion sort is cheap at small n "
            "but its inversion count grows with n. Last-pivot Lomuto is still "
            "fragile; three-way partitioning is the safer large-n choice.",
        )
    if condition == "C6":
        return (
            "Hardened Quick Sort",
            "Naive Quick Sort",
            "Only ~7 band values occur, creating large equal groups. Three-way "
            "partitioning groups equal bands in one pass; Lomuto degrades and "
            "also gives unstable tie order (the documented C6 conflict).",
        )
    if condition == "C2":
        return (
            "Hardened Quick Sort",
            "Insertion Sort",
            "C2 is a uniformly shuffled total order. Comparison sorts have "
            "n log n behaviour; insertion sort is quadratic with a larger "
            "constant. Median-of-three should avoid poor pivots.",
        )
    return (
        "Hardened Quick Sort",
        "Insertion Sort",
        "C1 is in Time order but unrelated to the triage key, so it behaves "
        "like a random permutation for ranking. Insertion sort is quadratic; "
        "custom quick/merge/heap sorts are n log n.",
    )


def add_tournament_round(path: Path, condition: str, n: int) -> str:
    prediction_id = f"tournament-{condition}-n{n}"
    fastest, slowest, rationale = tournament_prediction(condition, n)
    add_prediction(
        path,
        prediction_id=prediction_id,
        problem="C",
        round_id=f"C_{condition}_n{n}",
        condition=condition,
        n=n,
        predicted_fastest=fastest,
        predicted_slowest=slowest,
        rationale=rationale,
    )
    return prediction_id
