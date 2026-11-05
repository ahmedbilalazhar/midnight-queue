from __future__ import annotations

from midnight_queue.reference import reference_triage
from midnight_queue.records import (
    Counters,
    OrderMode,
    TriageOrder,
    bands_non_increasing,
    is_sorted,
)
from midnight_queue.sorting import SORT_ALGORITHMS, count_inversions


def test_comparator_uses_complete_triage_order(make_txn):
    a = make_txn(1, band=3, amount=10.0, time=5.0)
    b = make_txn(2, band=3, amount=9.0, time=1.0)
    c = make_txn(3, band=2, amount=100.0, time=0.0)
    d = make_txn(4, band=3, amount=10.0, time=5.0)
    order = TriageOrder()
    assert order.cmp(a, b) < 0
    assert order.cmp(b, c) < 0
    assert order.cmp(a, d) < 0 and order.cmp(d, a) > 0
    assert order.counters.comparisons == 4


def test_band_comparator_has_no_secondary_key(make_txn):
    a = make_txn(1, band=3, amount=10.0, time=5.0)
    b = make_txn(2, band=3, amount=9.0, time=1.0)
    order = TriageOrder(OrderMode.BAND)
    assert order.cmp(a, b) == 0
    assert order.cmp(b, a) == 0
    assert bands_non_increasing([a, b])


def test_class_label_never_affects_comparison(make_txn):
    clean = make_txn(1, band=2, amount=7.0, time=3.0, label=0)
    fraud = make_txn(1, band=2, amount=7.0, time=3.0, label=1)
    order = TriageOrder()
    assert order.cmp(clean, fraud) == 0
    assert [t.txn_id for t in reference_triage([clean, fraud])] == [1, 1]


def test_all_full_sorts_match_reference_on_mixed_input(make_txn):
    records = [
        make_txn(1, band=2, amount=5.0, time=3.0),
        make_txn(2, band=4, amount=1.0, time=2.0),
        make_txn(3, band=2, amount=5.0, time=1.0),
        make_txn(4, band=0, amount=9.0, time=4.0),
        make_txn(5, band=4, amount=8.0, time=0.0),
        make_txn(6, band=2, amount=7.0, time=9.0),
        make_txn(7, band=2, amount=5.0, time=1.0),
    ]
    expected = reference_triage(records)
    for name, algorithm in SORT_ALGORITHMS.items():
        counters = Counters()
        actual = algorithm(list(records), TriageOrder(counters=counters), counters)
        assert actual == expected, name
        assert is_sorted(actual, TriageOrder()), name
        assert counters.comparisons > 0, name
        assert counters.moves > 0, name


def test_all_full_sorts_handle_empty_one_and_all_equal(make_txn):
    cases = [
        [],
        [make_txn(1)],
        [make_txn(i, band=3, amount=2.0, time=4.0) for i in range(1, 40)],
    ]
    for records in cases:
        expected = reference_triage(records)
        for name, algorithm in SORT_ALGORITHMS.items():
            counters = Counters()
            actual = algorithm(list(records), TriageOrder(counters=counters), counters)
            assert actual == expected, (name, len(records))


def test_naive_quicksort_survives_sorted_and_reverse_sorted(make_txn):
    records = [make_txn(i, band=i % 10, amount=float(i % 7)) for i in range(1, 201)]
    expected = reference_triage(records)
    for name in ("Naive Quick Sort", "Hardened Quick Sort"):
        counters = Counters()
        actual = SORT_ALGORITHMS[name](
            list(records), TriageOrder(counters=counters), counters
        )
        assert actual == expected
        reverse_counters = Counters()
        reverse = SORT_ALGORITHMS[name](
            list(reversed(records)),
            TriageOrder(counters=reverse_counters),
            reverse_counters,
        )
        assert reverse == expected


def test_c6_literal_band_order_is_correct_but_ties_are_not_total(make_txn):
    records = [
        make_txn(1, band=1, amount=9.0),
        make_txn(2, band=3, amount=1.0),
        make_txn(3, band=1, amount=8.0),
        make_txn(4, band=3, amount=2.0),
    ]
    for name, algorithm in SORT_ALGORITHMS.items():
        counters = Counters()
        actual = algorithm(
            list(records), TriageOrder(OrderMode.BAND, counters), counters
        )
        assert bands_non_increasing(actual), name
        assert sorted(t.txn_id for t in actual) == [1, 2, 3, 4], name


def test_inversion_count_matches_brute_force(make_txn):
    records = [make_txn(i, band=i % 4, amount=float((i * 7) % 11)) for i in range(1, 30)]
    order = TriageOrder()
    expected = sum(
        1
        for i in range(len(records))
        for j in range(i + 1, len(records))
        if order.cmp(records[i], records[j]) > 0
    )
    assert count_inversions(records, TriageOrder()) == expected
