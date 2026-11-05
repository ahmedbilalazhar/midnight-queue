from __future__ import annotations

import numpy as np

from midnight_queue.conditions import build_conditions
from midnight_queue.reference import reference_triage
from midnight_queue.records import TriageOrder, is_sorted


def _records(make_txn, n=1000):
    return [
        make_txn(
            i,
            band=(i * 7) % 10,
            amount=float((i * 37) % 500),
            time=float(i // 3),
            risk=float((i % 13) + 0.1),
        )
        for i in range(1, n + 1)
    ]


def test_all_conditions_use_identical_multiset(make_txn):
    records = _records(make_txn)
    conditions = build_conditions(records, 232581)
    expected_ids = sorted(t.txn_id for t in records)
    for cid, condition in conditions.items():
        assert sorted(t.txn_id for t in condition.records) == expected_ids, cid
        assert condition.n == len(records), cid


def test_c1_to_c5_structural_properties(make_txn):
    records = _records(make_txn)
    c = build_conditions(records, 232581)
    assert c["C1"].records == sorted(records, key=lambda t: (t.time, t.txn_id))
    assert c["C2"].records != c["C1"].records
    assert is_sorted(c["C3"].records, TriageOrder())
    assert c["C4"].records == list(reversed(c["C3"].records))
    assert c["C6"].records == c["C1"].records
    assert c["C6"].order_mode == "band"
    assert all(x.order_mode == "triage" for k, x in c.items() if k != "C6")


def test_c5_moves_exactly_one_percent_of_positions(make_txn):
    n = 1000
    c = build_conditions(_records(make_txn, n), 232581)
    before = c["C3"].records
    after = c["C5"].records
    changed = sum(1 for a, b in zip(before, after) if a != b)
    assert changed == 10
    assert sorted(t.txn_id for t in after) == sorted(t.txn_id for t in before)


def test_c5_is_deterministic_and_changes_with_seed(make_txn):
    records = _records(make_txn)
    a = build_conditions(records, 232581)["C5"].records
    b = build_conditions(records, 232581)["C5"].records
    c = build_conditions(records, 232582)["C5"].records
    assert [t.txn_id for t in a] == [t.txn_id for t in b]
    assert [t.txn_id for t in a] != [t.txn_id for t in c]


def test_c2_is_deterministic(make_txn):
    records = _records(make_txn)
    a = build_conditions(records, 232581)["C2"].records
    b = build_conditions(records, 232581)["C2"].records
    assert [t.txn_id for t in a] == [t.txn_id for t in b]


def test_conditions_reject_empty_input():
    try:
        build_conditions([], 232581)
    except ValueError:
        pass
    else:
        raise AssertionError("empty conditions should fail")
