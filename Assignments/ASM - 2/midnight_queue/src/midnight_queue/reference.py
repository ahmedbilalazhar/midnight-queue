"""Independently implemented, clearly labelled built-in references."""

from __future__ import annotations

from .records import Txn, band_key, triage_key


def reference_triage(records: list[Txn]) -> list[Txn]:
    """Built-in baseline used only for verification."""

    return sorted(records, key=triage_key)


def reference_band_stable(records: list[Txn]) -> list[Txn]:
    """Built-in stable band-only baseline (tie policy: input order)."""

    return sorted(records, key=band_key)


def reference_topk(records: list[Txn], k: int) -> list[Txn]:
    if k <= 0:
        return []
    return reference_triage(records)[:k]


def sequence_digest(records: list[Txn], field: str = "txn_id") -> str:
    import hashlib

    h = hashlib.blake2b(digest_size=16)
    for record in records:
        h.update(str(getattr(record, field)).encode("ascii"))
        h.update(b",")
    return h.hexdigest()
