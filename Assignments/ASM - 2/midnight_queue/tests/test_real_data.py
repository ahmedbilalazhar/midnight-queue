from __future__ import annotations

import dataclasses

import pytest

from midnight_queue.config import CONFIG, DEFAULT_DATA_PATH
from midnight_queue.data import load_dataset, sample_records
from midnight_queue.conditions import build_conditions
from midnight_queue.records import (
    Counters,
    OrderMode,
    TriageOrder,
    bands_non_increasing,
)
from midnight_queue.reference import reference_band_stable, reference_triage
from midnight_queue.sorting import SORT_ALGORITHMS
from midnight_queue.topk import topk_buffer, topk_heap


@pytest.fixture(scope="module")
def real_records():
    if not DEFAULT_DATA_PATH.exists():
        pytest.skip("official creditcard.csv is not present")
    dataset = load_dataset(DEFAULT_DATA_PATH, verify_checksum=False)
    return dataset, sample_records(dataset.records, 1_000, CONFIG.seed)


@pytest.mark.slow
def test_real_sample_all_conditions_all_contenders(real_records):
    _, records = real_records
    conditions = build_conditions(records, CONFIG.seed)
    for cid, condition in conditions.items():
        if condition.order_mode == "triage":
            expected = reference_triage(condition.records)
        else:
            expected = reference_band_stable(condition.records)
        for name, algorithm in SORT_ALGORITHMS.items():
            counters = Counters()
            actual = algorithm(
                list(condition.records),
                TriageOrder(condition.order_mode, counters),
                counters,
            )
            if condition.order_mode == "triage":
                assert actual == expected, (cid, name)
            else:
                assert bands_non_increasing(actual), (cid, name)
                assert sorted(t.txn_id for t in actual) == sorted(
                    t.txn_id for t in condition.records
                ), (cid, name)


@pytest.mark.slow
def test_class_label_does_not_change_rank_order(real_records):
    _, records = real_records
    condition = build_conditions(records, CONFIG.seed)["C2"]
    expected = reference_triage(condition.records)
    flipped = [
        dataclasses.replace(t, label=1 - t.label) for t in condition.records
    ]
    actual = reference_triage(flipped)
    assert [t.txn_id for t in actual] == [t.txn_id for t in expected]


@pytest.mark.slow
def test_real_topk_boundaries(real_records):
    _, records = real_records
    condition = build_conditions(records, CONFIG.seed)["C1"]
    for k in (1, CONFIG.k, len(records)):
        expected = reference_triage(condition.records)[:k]
        for algorithm in (topk_heap, topk_buffer):
            counters = Counters()
            actual = algorithm(
                list(condition.records), k, TriageOrder(counters=counters), counters
            )
            assert actual == expected
