"""Top-K selection: a size-K heap and a bounded insertion buffer.

Both methods return an *ordered* queue of at most K transactions.  Their
counters therefore include producing the ordered queue, not merely choosing the
set.  No built-in sort is used.
"""

from __future__ import annotations

from .records import Counters, Txn, TriageOrder
from .sorting import _sift_down_max, _swap, merge_sort


class TopKHeap:
    """Size-K max-heap under the comparator, so the root is the worst kept.

    ``cmp(candidate, root) < 0`` means the candidate is better and replaces it.
    """

    __slots__ = ("capacity", "order", "counters", "heap")

    def __init__(self, capacity: int, order: TriageOrder) -> None:
        self.capacity = max(0, capacity)
        self.order = order
        self.counters = order.counters
        self.heap: list[Txn] = []

    def offer(self, item: Txn) -> None:
        heap = self.heap
        if self.capacity == 0:
            return
        if len(heap) < self.capacity:
            heap.append(item)
            self.counters.moves += 1
            self._sift_up(len(heap) - 1)
            return
        if self.order.cmp(item, heap[0]) < 0:
            heap[0] = item
            self.counters.moves += 1
            _sift_down_max(heap, 0, len(heap), self.order.cmp, self.counters)

    def offer_many(self, items: list[Txn]) -> None:
        for item in items:
            self.offer(item)

    def _sift_up(self, index: int) -> None:
        heap = self.heap
        cmp = self.order.cmp
        while index > 0:
            parent = (index - 1) // 2
            if cmp(heap[index], heap[parent]) <= 0:
                return
            _swap(heap, index, parent, self.counters)
            index = parent

    def publish(self) -> list[Txn]:
        """Return the retained queue best-first without destroying the heap."""

        if not self.heap:
            return []
        # The copy is part of publishing an immutable snapshot.
        snapshot = list(self.heap)
        self.counters.moves += len(snapshot)
        _heap_queue_from_max_heap(snapshot, self.order, self.counters)
        return snapshot


def _heap_queue_from_max_heap(
    heap: list[Txn], order: TriageOrder, counters: Counters
) -> list[Txn]:
    n = len(heap)
    for end in range(n - 1, 0, -1):
        _swap(heap, 0, end, counters)
        _sift_down_max(heap, 0, end, order.cmp, counters)
    return heap


def topk_heap(
    items: list[Txn], k: int, order: TriageOrder, counters: Counters
) -> list[Txn]:
    if k <= 0 or not items:
        return []
    capacity = min(k, len(items))
    heap = list(items[:capacity])
    counters.moves += capacity
    for root in range(capacity // 2 - 1, -1, -1):
        _sift_down_max(heap, root, capacity, order.cmp, counters)
    for index in range(capacity, len(items)):
        candidate = items[index]
        if order.cmp(candidate, heap[0]) < 0:
            heap[0] = candidate
            counters.moves += 1
            _sift_down_max(heap, 0, capacity, order.cmp, counters)
    _heap_queue_from_max_heap(heap, order, counters)
    return heap


def topk_buffer(
    items: list[Txn], k: int, order: TriageOrder, counters: Counters
) -> list[Txn]:
    """Sorted bounded buffer, with binary-search insertion into sorted order.

    The first min(k,n) records are sorted once with the custom merge sort.
    Every later candidate is first compared with the current worst.  If better,
    it is inserted by explicit right-shifting.  This is an insertion buffer,
    not a disguised call to a library sort.
    """

    if k <= 0 or not items:
        return []
    capacity = min(k, len(items))
    buffer = list(items[:capacity])
    counters.moves += capacity
    merge_sort(buffer, order, counters)
    cmp = order.cmp
    for index in range(capacity, len(items)):
        candidate = items[index]
        if cmp(candidate, buffer[-1]) >= 0:
            continue
        # First position whose element is worse than the candidate.
        lo, hi = 0, capacity - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cmp(candidate, buffer[mid]) < 0:
                hi = mid
            else:
                lo = mid + 1
        for j in range(capacity - 1, lo, -1):
            buffer[j] = buffer[j - 1]
            counters.moves += 1
        buffer[lo] = candidate
        counters.moves += 1
    return buffer


TOPK_ALGORITHMS = {
    "Size-K Heap": topk_heap,
    "Bounded Insertion Buffer": topk_buffer,
}
