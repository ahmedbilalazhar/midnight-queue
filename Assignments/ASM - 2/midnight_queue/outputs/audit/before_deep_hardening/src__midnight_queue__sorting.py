"""Custom full-sort contenders.

All public sort functions have the same interface:

    sort(items, order, counters) -> list[Txn]

They may mutate the list supplied by the caller.  Benchmarks therefore give
every contender a fresh copy, created outside the timed region.  No built-in
sort is called anywhere in this module.
"""

from __future__ import annotations

from .records import Counters, Txn, TriageOrder


def _swap(a: list[Txn], i: int, j: int, counters: Counters) -> None:
    if i == j:
        return
    a[i], a[j] = a[j], a[i]
    counters.moves += 3


def insertion_sort(
    items: list[Txn], order: TriageOrder, counters: Counters
) -> list[Txn]:
    cmp = order.cmp
    a = items
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        while j >= 0 and cmp(a[j], key) > 0:
            a[j + 1] = a[j]
            counters.moves += 1
            j -= 1
        a[j + 1] = key
        counters.moves += 1
    return a


def merge_sort(
    items: list[Txn], order: TriageOrder, counters: Counters
) -> list[Txn]:
    n = len(items)
    if n <= 1:
        return items
    a = items
    buffer: list[Txn | None] = [None] * n
    cmp = order.cmp

    def merge(lo: int, mid: int, hi: int) -> None:
        i, j, k = lo, mid, lo
        while i < mid and j < hi:
            # Take from the right only when strictly smaller; hence stable.
            if cmp(a[j], a[i]) < 0:  # type: ignore[arg-type]
                buffer[k] = a[j]
                j += 1
            else:
                buffer[k] = a[i]
                i += 1
            counters.moves += 1
            k += 1
        while i < mid:
            buffer[k] = a[i]
            i += 1
            k += 1
            counters.moves += 1
        while j < hi:
            buffer[k] = a[j]
            j += 1
            k += 1
            counters.moves += 1
        for p in range(lo, hi):
            a[p] = buffer[p]  # type: ignore[assignment]
            counters.moves += 1

    def rec(lo: int, hi: int) -> None:
        if hi - lo <= 1:
            return
        mid = (lo + hi) // 2
        rec(lo, mid)
        rec(mid, hi)
        merge(lo, mid, hi)

    rec(0, n)
    return a


def _lomuto_partition(
    a: list[Txn], lo: int, hi: int, cmp, counters: Counters
) -> int:
    pivot = a[hi]
    i = lo
    for j in range(lo, hi):
        if cmp(a[j], pivot) <= 0:
            _swap(a, i, j, counters)
            i += 1
    _swap(a, i, hi, counters)
    return i


def naive_quicksort(
    items: list[Txn], order: TriageOrder, counters: Counters
) -> list[Txn]:
    """Last-element-pivot Lomuto quick sort, iterative to avoid recursion limits."""

    a = items
    if len(a) < 2:
        return a
    cmp = order.cmp
    stack: list[tuple[int, int]] = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            pivot = _lomuto_partition(a, lo, hi, cmp, counters)
            # Process the smaller side first, limiting explicit-stack depth.
            if pivot - lo < hi - pivot:
                if pivot + 1 < hi:
                    stack.append((pivot + 1, hi))
                hi = pivot - 1
            else:
                if lo < pivot - 1:
                    stack.append((lo, pivot - 1))
                lo = pivot + 1
    return a


def _median3_index(a: list[Txn], i: int, j: int, k: int, cmp) -> int:
    if cmp(a[i], a[j]) < 0:
        if cmp(a[j], a[k]) < 0:
            return j
        if cmp(a[i], a[k]) < 0:
            return k
        return i
    if cmp(a[i], a[k]) < 0:
        return i
    if cmp(a[j], a[k]) < 0:
        return k
    return j


def hardened_quicksort(
    items: list[Txn], order: TriageOrder, counters: Counters
) -> list[Txn]:
    """Median-of-three pivot plus three-way (Dutch national flag) partition."""

    a = items
    if len(a) < 2:
        return a
    cmp = order.cmp
    stack: list[tuple[int, int]] = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            mid = (lo + hi) // 2
            pivot_index = _median3_index(a, lo, mid, hi, cmp)
            _swap(a, pivot_index, hi, counters)
            pivot = a[hi]
            lt = lo
            scan = lo
            gt = hi
            while scan <= gt:
                relation = cmp(a[scan], pivot)
                if relation < 0:
                    _swap(a, lt, scan, counters)
                    lt += 1
                    scan += 1
                elif relation > 0:
                    _swap(a, scan, gt, counters)
                    gt -= 1
                else:
                    scan += 1
            # Equal block is [lt, gt].  Recurse into the two outer blocks.
            if lt - lo < hi - gt:
                if gt + 1 < hi:
                    stack.append((gt + 1, hi))
                hi = lt - 1
            else:
                if lo < lt - 1:
                    stack.append((lo, lt - 1))
                lo = gt + 1
    return a


def _sift_down_max(
    a: list[Txn], root: int, end: int, cmp, counters: Counters
) -> None:
    """Sift in a max-heap under the comparator (root is worst)."""

    while True:
        child = 2 * root + 1
        if child >= end:
            return
        right = child + 1
        if right < end and cmp(a[right], a[child]) > 0:
            child = right
        if cmp(a[child], a[root]) <= 0:
            return
        _swap(a, root, child, counters)
        root = child


def heap_sort(
    items: list[Txn], order: TriageOrder, counters: Counters
) -> list[Txn]:
    """Heap sort with a max-heap of worst-first elements.

    Extracting the worst element to the end leaves the final array in triage
    order (best first).  Build is bottom-up and uses no heapq.
    """

    a = items
    n = len(a)
    if n < 2:
        return a
    cmp = order.cmp
    for root in range(n // 2 - 1, -1, -1):
        _sift_down_max(a, root, n, cmp, counters)
    for end in range(n - 1, 0, -1):
        _swap(a, 0, end, counters)
        _sift_down_max(a, 0, end, cmp, counters)
    return a


SORT_ALGORITHMS = {
    "Insertion Sort": insertion_sort,
    "Merge Sort": merge_sort,
    "Naive Quick Sort": naive_quicksort,
    "Hardened Quick Sort": hardened_quicksort,
    "Heap Sort": heap_sort,
}

STABILITY = {
    "Insertion Sort": "stable",
    "Merge Sort": "stable",
    "Naive Quick Sort": "unstable",
    "Hardened Quick Sort": "unstable",
    "Heap Sort": "unstable",
}


def count_inversions(records: list[Txn], order: TriageOrder) -> int:
    """Count inversions relative to ``order`` in O(n log n), no built-in sort."""

    n = len(records)
    if n < 2:
        return 0
    a = list(records)
    buffer = [None] * n
    cmp = order.cmp

    def rec(lo: int, hi: int) -> int:
        if hi - lo <= 1:
            return 0
        mid = (lo + hi) // 2
        inversions = rec(lo, mid) + rec(mid, hi)
        i, j, k = lo, mid, lo
        while i < mid and j < hi:
            if cmp(a[j], a[i]) < 0:
                buffer[k] = a[j]
                j += 1
                inversions += mid - i
            else:
                buffer[k] = a[i]
                i += 1
            k += 1
        while i < mid:
            buffer[k] = a[i]
            i += 1
            k += 1
        while j < hi:
            buffer[k] = a[j]
            j += 1
            k += 1
        for p in range(lo, hi):
            a[p] = buffer[p]
        return inversions

    return rec(0, n)
