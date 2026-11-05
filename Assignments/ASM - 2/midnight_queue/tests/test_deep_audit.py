"""Adversarial tests derived from the manual and actual audit findings."""
import dataclasses
import importlib
from pathlib import Path
import random

import pytest

from midnight_queue.records import Counters, TriageOrder
from midnight_queue.reference import reference_triage
from midnight_queue.sorting import SORT_ALGORITHMS, _heap_sort_range
from midnight_queue.topk import TopKHeap, topk_heap, topk_buffer
from midnight_queue.data import load_dataset


@pytest.mark.parametrize("algorithm",list(SORT_ALGORITHMS.values())+[topk_heap,topk_buffer])
def test_split_instrumentation_is_rejected(algorithm):
    other = Counters()
    args = ([],0,TriageOrder(),other) if algorithm in (topk_heap,topk_buffer) else ([],TriageOrder(),other)
    with pytest.raises(ValueError,match="share"):
        algorithm(*args)


def test_introsort_guards_against_adversarial_pivots(make_txn,monkeypatch):
    import midnight_queue.sorting as sorting
    # Force consistently poor pivots. Correctness alone would miss O(n^2).
    monkeypatch.setattr(sorting,"_median3_index",lambda a,i,j,k,cmp:k)
    n = 2048
    records = [make_txn(i,band=3,amount=float(n-i)) for i in range(1,n+1)]
    counters = Counters()
    output = sorting.hardened_quicksort(records[:],TriageOrder(counters=counters),counters)
    assert output == reference_triage(records)
    assert counters.comparisons < 8*n*n.bit_length()


def test_heap_fallback_does_not_touch_neighbouring_ranges(make_txn):
    records = [make_txn(i,band=i%4,amount=float(i)) for i in range(1,100)]
    original = records[:]
    counters = Counters()
    _heap_sort_range(records,7,83,TriageOrder(counters=counters).cmp,counters)
    assert records[:7] == original[:7]
    assert records[83:] == original[83:]
    assert records[7:83] == reference_triage(original[7:83])


def test_c6_group_sizes_alone_do_not_determine_lomuto_comparisons(make_txn):
    # Same two groups of size two; different arrival sequences have different
    # cross-band work. A group-only formula cannot be an exact model.
    counts=[]
    for bands in ([2,2,1,1],[1,2,1,2]):
        records=[make_txn(i,band=b) for i,b in enumerate(bands,1)]
        counters=Counters()
        SORT_ALGORITHMS["Naive Quick Sort"](records,TriageOrder("band",counters),counters)
        counts.append(counters.comparisons)
    assert counts==[6,4]


@pytest.mark.parametrize("seed",range(6))
def test_full_sorts_obey_total_and_band_orders_with_duplicate_keys(make_txn,seed):
    rng = random.Random(seed)
    records = [make_txn(i,band=rng.randrange(4),amount=float(rng.randrange(5)),
                        time=float(rng.randrange(3))) for i in range(1,121)]
    for algorithm in SORT_ALGORITHMS.values():
        for mode in ("triage","band"):
            counters = Counters()
            output = algorithm(records[:],TriageOrder(mode,counters),counters)
            assert sorted(t.txn_id for t in output) == sorted(t.txn_id for t in records)
            if mode == "triage":
                assert output == reference_triage(records)
            else:
                assert all(a.band>=b.band for a,b in zip(output,output[1:]))


def test_stable_sorts_preserve_genuinely_equal_total_keys(make_txn):
    # Different IDs are NOT equal keys; the previous test called them equal.
    records = [make_txn(1,band=3,amount=2.0,time=4.0,label=i%2) for i in range(50)]
    for name in ("Insertion Sort","Merge Sort"):
        counters = Counters()
        output = SORT_ALGORITHMS[name](records[:],TriageOrder(counters=counters),counters)
        assert [id(t) for t in output] == [id(t) for t in records]


def test_band_only_sort_cannot_read_forbidden_secondary_fields():
    class BandRecord:
        def __init__(self,band):
            self.band=band
        def __getattr__(self,name):
            raise AssertionError(f"C6 consulted forbidden field {name}")
    records = [BandRecord(b) for b in [3,1,3,0,1,9]*15]
    for algorithm in SORT_ALGORITHMS.values():
        counters = Counters()
        output = algorithm(records[:],TriageOrder("band",counters),counters)
        assert sorted(map(id,output)) == sorted(map(id,records))
        assert all(a.band>=b.band for a,b in zip(output,output[1:]))


@pytest.mark.parametrize("algorithm",[topk_heap,topk_buffer])
def test_topk_capacity_must_be_an_integer(algorithm):
    counters = Counters()
    with pytest.raises(TypeError):
        algorithm([],1.5,TriageOrder(counters=counters),counters)
    with pytest.raises(TypeError):
        TopKHeap(1.5,TriageOrder())


def test_official_checksum_is_enforced(tmp_path):
    path=tmp_path/"creditcard.csv"
    path.write_text("Time,Amount,Class\n0,1,0\n")
    with pytest.raises(ValueError,match="SHA-256"):
        load_dataset(path)


def test_c6_exact_model_matches_descending_lomuto(make_txn,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/"scripts"))
    model = importlib.import_module("analyze_data")._lomuto_band_comparisons
    rng = random.Random(232581)
    for n in (0,1,2,17,100,300):
        bands = [rng.randrange(10) for _ in range(n)]
        records = [make_txn(i,band=b) for i,b in enumerate(bands,1)]
        counters = Counters()
        SORT_ALGORITHMS["Naive Quick Sort"](records,TriageOrder("band",counters),counters)
        assert model(bands) == counters.comparisons
