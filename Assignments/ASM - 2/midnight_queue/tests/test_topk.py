from __future__ import annotations

from midnight_queue.reference import reference_topk
from midnight_queue.records import Counters, OrderMode, TriageOrder, bands_non_increasing
from midnight_queue.topk import (
    TOPK_ALGORITHMS,
    TopKHeap,
    topk_buffer,
    topk_heap,
)


def _records(make_txn, n=60):
    return [
        make_txn(
            i,
            band=(i * 11) % 10,
            amount=float((i * 17) % 101),
            time=float((i * 13) % 37),
        )
        for i in range(1, n + 1)
    ]


def test_topk_matches_ordered_reference_for_boundaries(make_txn):
    records = _records(make_txn)
    for k in (0, 1, 2, 10, len(records) - 1, len(records), len(records) + 5):
        expected = reference_topk(records, k)
        for name, algorithm in TOPK_ALGORITHMS.items():
            counters = Counters()
            actual = algorithm(
                list(records), k, TriageOrder(counters=counters), counters
            )
            assert actual == expected, (name, k)
            assert len(actual) == min(max(k, 0), len(records))


def test_topk_empty_input(make_txn):
    for algorithm in TOPK_ALGORITHMS.values():
        counters = Counters()
        assert algorithm([], 5, TriageOrder(counters=counters), counters) == []


def test_topk_duplicate_heavy_input_matches_reference(make_txn):
    records = [
        make_txn(1, band=3, amount=9.0, time=1.0),
        make_txn(2, band=3, amount=9.0, time=2.0),
        make_txn(3, band=3, amount=9.0, time=1.0),
        make_txn(4, band=3, amount=8.0, time=4.0),
        make_txn(5, band=1, amount=50.0, time=0.0),
        make_txn(6, band=9, amount=0.1, time=3.0),
    ]
    expected = reference_topk(records, 4)
    for algorithm in TOPK_ALGORITHMS.values():
        counters = Counters()
        assert algorithm(
            list(records), 4, TriageOrder(counters=counters), counters
        ) == expected


def test_incremental_heap_matches_one_shot(make_txn):
    records = _records(make_txn, 61)
    counters = Counters()
    state = TopKHeap(7, TriageOrder(counters=counters))
    state.offer_many(records[:31])
    state.offer_many(records[31:])
    reference_counters = Counters()
    assert state.publish() == topk_heap(
        list(records), 7, TriageOrder(counters=reference_counters), reference_counters
    )


def test_buffer_on_c6_returns_band_order(make_txn):
    records = _records(make_txn, 30)
    counters = Counters()
    actual = topk_buffer(
        list(records), 12, TriageOrder(OrderMode.BAND, counters), counters
    )
    assert bands_non_increasing(actual)
