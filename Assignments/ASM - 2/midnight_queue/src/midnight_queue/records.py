"""Transaction records and the single centralized ranking comparator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Txn:
    """One transaction with its precomputed risk fields.

    ``label`` is the Kaggle Class value and is never read by ranking code.
    """

    txn_id: int
    time: float
    amount: float
    band: int
    risk: float
    label: int = 0


class OrderMode(str, Enum):
    TRIAGE = "triage"
    BAND = "band"


@dataclass(slots=True)
class Counters:
    comparisons: int = 0
    moves: int = 0

    def reset(self) -> None:
        self.comparisons = 0
        self.moves = 0

    def as_dict(self) -> dict[str, int]:
        return {"comparisons": self.comparisons, "moves": self.moves}


class TriageOrder:
    """Centralized assignment comparator.

    ``cmp(a, b) < 0`` means that ``a`` appears before ``b`` in the ranking.
    Every logical comparison increments exactly one shared counter.

    In TRIAGE mode the order is the complete assignment key:
    band desc, Amount desc, Time asc, txn_id asc.

    In BAND mode only the band is consulted.  Equal bands compare as 0.
    Deliberately, no Amount/Time/txn_id/Class fallback is present.
    """

    __slots__ = ("mode", "counters")

    def __init__(
        self,
        mode: OrderMode | str = OrderMode.TRIAGE,
        counters: Counters | None = None,
    ) -> None:
        self.mode = OrderMode(mode)
        self.counters = counters if counters is not None else Counters()

    def cmp(self, a: Txn, b: Txn) -> int:
        self.counters.comparisons += 1
        ab = a.band
        bb = b.band
        if ab != bb:
            return -1 if ab > bb else 1
        if self.mode is OrderMode.BAND:
            return 0
        aa = a.amount
        ba = b.amount
        if aa != ba:
            return -1 if aa > ba else 1
        at = a.time
        bt = b.time
        if at != bt:
            return -1 if at < bt else 1
        ai = a.txn_id
        bi = b.txn_id
        if ai != bi:
            return -1 if ai < bi else 1
        return 0

    def less(self, a: Txn, b: Txn) -> bool:
        return self.cmp(a, b) < 0

    def __call__(self, a: Txn, b: Txn) -> int:
        return self.cmp(a, b)


def require_shared_counters(order: TriageOrder, counters: Counters) -> None:
    """Prevent silently splitting comparisons and moves into different records."""
    if order.counters is not counters:
        raise ValueError("order and algorithm must share the same Counters object")


def triage_key(txn: Txn) -> tuple[int, float, float, int]:
    """Reference-only key.  This mirrors TriageOrder TRIAGE exactly."""

    return (-txn.band, -txn.amount, txn.time, txn.txn_id)


def band_key(txn: Txn) -> tuple[int]:
    """Reference-only literal band key."""

    return (-txn.band,)


def is_sorted(records: list[Txn], order: TriageOrder) -> bool:
    return all(order.cmp(records[i - 1], records[i]) <= 0 for i in range(1, len(records)))


def bands_non_increasing(records: list[Txn]) -> bool:
    return all(records[i - 1].band >= records[i].band for i in range(1, len(records)))
