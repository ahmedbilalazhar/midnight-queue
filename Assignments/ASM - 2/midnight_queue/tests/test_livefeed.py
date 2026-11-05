from __future__ import annotations

from midnight_queue.livefeed import (
    build_expected_queues,
    make_windows,
    run_all_live_feed,
    run_live_feed,
)
from midnight_queue.reference import reference_topk


def _records(make_txn, n=120):
    return [
        make_txn(
            i,
            band=(i * 5) % 10,
            amount=float((i * 23) % 311),
            time=float((i * 37) % 3600),
        )
        for i in range(1, n + 1)
    ]


def test_windows_include_empty_gaps(make_txn):
    records = [
        make_txn(1, time=0.0),
        make_txn(2, time=10.0),
        make_txn(3, time=3700.0),
    ]
    windows = make_windows(records, 3600)
    assert [w.number for w in windows] == [0, 1]
    assert len(windows[0].records) == 2
    assert len(windows[1].records) == 1


def test_all_live_strategies_match_reference_every_window(make_txn):
    records = _records(make_txn)
    k = 7
    expected = build_expected_queues(records, 1800, k)
    for strategy in ("rerank", "heap", "merge"):
        result = run_live_feed(records, 1800, k, strategy, expected=expected)
        assert all(row["correct"] for row in result.rows), strategy
        for number, queue in result.queues.items():
            assert queue == expected[number], (strategy, number)


def test_strategies_agree_when_k_exceeds_seen(make_txn):
    records = _records(make_txn, 5)
    results = run_all_live_feed(records, 3600, 50)
    for number in results["rerank"].queues:
        assert results["rerank"].queues[number] == results["heap"].queues[number]
        assert results["rerank"].queues[number] == results["merge"].queues[number]


def test_empty_feed(make_txn):
    for strategy in ("rerank", "heap", "merge"):
        result = run_live_feed([], 600, 10, strategy)
        assert result.rows == []


def test_live_queue_is_ordered_and_correct_at_zero_k(make_txn):
    records = _records(make_txn, 20)
    result = run_live_feed(records, 3600, 0, "merge", expected=build_expected_queues(records, 3600, 0))
    assert all(row["correct"] for row in result.rows)
    assert all(len(queue) == 0 for queue in result.queues.values())
