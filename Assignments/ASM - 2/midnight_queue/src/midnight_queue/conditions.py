"""Deterministic construction of the six assignment conditions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .records import Txn, triage_key

CONDITION_IDS = ("C1", "C2", "C3", "C4", "C5", "C6")
CONDITION_NAMES = {
    "C1": "Arrival",
    "C2": "Shuffled",
    "C3": "Pre-ranked",
    "C4": "Reverse-ranked",
    "C5": "Nearly ranked",
    "C6": "Band-only",
}


@dataclass(slots=True)
class ConditionInput:
    condition: str
    records: list[Txn]
    order_mode: str
    description: str

    @property
    def n(self) -> int:
        return len(self.records)


def _displace_one_percent(records: list[Txn], seed: int) -> list[Txn]:
    """Move exactly floor(0.01 n) selected records to new positions.

    For q > 1, q positions are chosen and their records are deranged among
    those positions.  For q == 1 the selected record is removed and reinserted
    at a different random index.  The function is deterministic for a seed.
    """

    n = len(records)
    q = int(np.floor(0.01 * n))
    if q <= 0:
        return list(records)
    rng = np.random.default_rng(seed)
    selected_positions = rng.choice(n, size=q, replace=False)
    moved = list(records)
    if q == 1:
        source = int(selected_positions[0])
        record = moved.pop(source)
        destination = int(rng.integers(0, n - 1))
        if destination >= source:
            destination += 1
        moved.insert(destination, record)
        return moved

    values = [records[int(i)] for i in selected_positions]
    # Rejection sampling makes a true derangement: every selected record moves.
    while True:
        permutation = rng.permutation(q)
        if not np.any(permutation == np.arange(q)):
            break
    for slot, value_index in zip(selected_positions, permutation):
        moved[int(slot)] = values[int(value_index)]
    return moved


def build_conditions(records: list[Txn], seed: int) -> dict[str, ConditionInput]:
    """Build C1-C6 from one identical underlying record list."""

    if not records:
        raise ValueError("conditions require at least one record")
    c1 = sorted(records, key=lambda t: (t.time, t.txn_id))
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(len(c1))
    c2 = [c1[int(i)] for i in permutation]
    c3 = sorted(c1, key=triage_key)
    c4 = list(reversed(c3))
    c5 = _displace_one_percent(c3, seed)
    c6 = list(c1)
    return {
        "C1": ConditionInput("C1", c1, "triage", CONDITION_NAMES["C1"]),
        "C2": ConditionInput("C2", c2, "triage", CONDITION_NAMES["C2"]),
        "C3": ConditionInput("C3", c3, "triage", CONDITION_NAMES["C3"]),
        "C4": ConditionInput("C4", c4, "triage", CONDITION_NAMES["C4"]),
        "C5": ConditionInput("C5", c5, "triage", CONDITION_NAMES["C5"]),
        "C6": ConditionInput("C6", c6, "band", CONDITION_NAMES["C6"]),
    }


def condition_summary(condition: ConditionInput) -> dict[str, object]:
    bands = [r.band for r in condition.records]
    return {
        "condition": condition.condition,
        "name": condition.description,
        "n": condition.n,
        "order_mode": condition.order_mode,
        "min_band": min(bands),
        "max_band": max(bands),
        "distinct_bands": len(set(bands)),
    }
