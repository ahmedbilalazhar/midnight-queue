"""Live-feed simulation over consecutive Time windows."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from .records import Counters, Txn, TriageOrder, triage_key
from .sorting import hardened_quicksort, merge_sort
from .topk import TopKHeap
from .deadline import algorithm_deadline


@dataclass(slots=True)
class Window:
    number: int
    records: list[Txn]


@dataclass(slots=True)
class LiveFeedResult:
    strategy: str
    width_seconds: int
    k: int
    rows: list[dict[str, object]] = field(default_factory=list)
    queues: dict[int, list[Txn]] = field(default_factory=dict)
    total_seconds: float = 0.0
    wall_seconds: float = 0.0
    counters: Counters = field(default_factory=Counters)


def make_windows(records: list[Txn], width_seconds: int) -> list[Window]:
    """Split C1 records into consecutive windows, including empty gaps."""

    if width_seconds <= 0:
        raise ValueError("window width must be positive")
    if not records:
        return []
    ordered = sorted(records, key=lambda t: (t.time, t.txn_id))
    origin = ordered[0].time
    buckets: dict[int, list[Txn]] = {}
    for record in ordered:
        number = int((record.time - origin) // width_seconds)
        buckets.setdefault(number, []).append(record)
    last = max(buckets)
    return [Window(i, buckets.get(i, [])) for i in range(last + 1)]


def _queue_digest(queue: list[Txn]) -> str:
    h = hashlib.blake2b(digest_size=8)
    for record in queue:
        h.update(str(record.txn_id).encode("ascii"))
        h.update(b",")
    return h.hexdigest()


def _merge_topk(
    left: list[Txn],
    right: list[Txn],
    k: int,
    order: TriageOrder,
    counters: Counters,
) -> list[Txn]:
    """Merge two ranked lists and retain at most K, in order."""

    if k <= 0:
        return []
    i = j = 0
    result: list[Txn] = []
    cmp = order.cmp
    while len(result) < k and i < len(left) and j < len(right):
        if cmp(left[i], right[j]) <= 0:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
        counters.moves += 1
    while len(result) < k and i < len(left):
        result.append(left[i])
        i += 1
        counters.moves += 1
    while len(result) < k and j < len(right):
        result.append(right[j])
        j += 1
        counters.moves += 1
    return result


def build_expected_queues(
    records: list[Txn], width_seconds: int, k: int
) -> dict[int, list[Txn]]:
    """Verification-only baseline using the built-in sort.

    This is deliberately outside every timed region and is never used by a
    contender.
    """

    windows = make_windows(records, width_seconds)
    seen: list[Txn] = []
    expected: dict[int, list[Txn]] = {}
    for window in windows:
        seen.extend(window.records)
        expected[window.number] = sorted(seen, key=triage_key)[: max(0, k)]
    return expected


def run_live_feed(
    records: list[Txn],
    width_seconds: int,
    k: int,
    strategy: str,
    *,
    expected: dict[int, list[Txn]] | None = None,
    windows: list[Window] | None = None,
    keep_queues: bool = True,
    timeout_seconds: float | None = None,
) -> LiveFeedResult:
    """Run strategy ``rerank``, ``heap`` or ``merge`` and record every window.

    ``windows`` may be supplied by a caller that wants to build the shared
    input structure before starting a memory trace.  It is the same immutable
    window split either way.
    """

    if windows is None:
        windows = make_windows(records, width_seconds)
    if strategy not in {"rerank", "heap", "merge"}:
        raise ValueError("unknown live-feed strategy")
    counters = Counters()
    order = TriageOrder(counters=counters)
    result = LiveFeedResult(strategy, width_seconds, k)
    seen: list[Txn] = []
    seen_count = 0
    current: list[Txn] = []
    heap = TopKHeap(k, order)
    cumulative = 0.0
    started_all = time.perf_counter()

    for window in windows:
        seen_count += len(window.records)
        # Only re-ranking needs the whole prefix.  Keeping it for the heap or
        # window-merge strategies would make their measured memory O(n) even
        # though their algorithms are O(K) and O(n/w + K).
        if strategy == "rerank":
            seen.extend(window.records)
        before_comparisons = counters.comparisons
        before_moves = counters.moves
        remaining=None if timeout_seconds is None else timeout_seconds-cumulative
        with algorithm_deadline(remaining):
            start = time.perf_counter()
            if strategy == "rerank":
                work = list(seen)
                hardened_quicksort(work, order, counters)
                queue = work[: max(0, k)]
            elif strategy == "heap":
                heap.offer_many(window.records)
                queue = heap.publish()
            else:
                sorted_window = merge_sort(list(window.records), order, counters)
                current = _merge_topk(current, sorted_window, k, order, counters)
                queue = current
            elapsed = time.perf_counter() - start
        cumulative += elapsed

        correct: bool | None = None
        if expected is not None:
            if window.number not in expected:
                raise ValueError(f"Missing reference queue for window {window.number}")
            correct = [t.txn_id for t in queue] == [
                t.txn_id for t in expected[window.number]
            ]
        if keep_queues:
            result.queues[window.number] = queue
        result.rows.append(
            {
                "strategy": strategy,
                "window": window.number + 1,
                "window_zero_based": window.number,
                "window_width_s": width_seconds,
                "window_records": len(window.records),
                "seen": seen_count,
                "elapsed_s": elapsed,
                "cumulative_s": cumulative,
                "window_comparisons": counters.comparisons - before_comparisons,
                "window_moves": counters.moves - before_moves,
                "comparisons": counters.comparisons,
                "moves": counters.moves,
                "queue_size": len(queue),
                "correct": correct,
                "queue_digest": _queue_digest(queue),
            }
        )

    result.wall_seconds = time.perf_counter() - started_all
    result.total_seconds = cumulative
    result.counters = counters
    return result


def run_all_live_feed(
    records: list[Txn],
    width_seconds: int,
    k: int,
    *,
    verify: bool = True,
) -> dict[str, LiveFeedResult]:
    expected = build_expected_queues(records, width_seconds, k) if verify else None
    return {
        name: run_live_feed(
            records, width_seconds, k, name, expected=expected if verify else None
        )
        for name in ("rerank", "heap", "merge")
    }
