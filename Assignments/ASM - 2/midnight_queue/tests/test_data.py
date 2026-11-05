from __future__ import annotations

import numpy as np
import pandas as pd

from midnight_queue.data import FEATURE_COLUMNS, load_dataset, sample_records
from midnight_queue.records import triage_key


def _write_csv(path, rows=8):
    base = {
        "Time": list(range(rows)),
        "Amount": [float(i + 1) for i in range(rows)],
        "Class": [0] * rows,
    }
    for i in range(rows):
        for j, col in enumerate(FEATURE_COLUMNS):
            base.setdefault(col, []).append(float((i + 1) * (j % 4 == 0)))
    pd.DataFrame(base, columns=["Time", *FEATURE_COLUMNS, "Amount", "Class"]).to_csv(
        path, index=False
    )


def test_loader_assigns_one_based_ids_and_risk(tmp_path):
    path = tmp_path / "creditcard.csv"
    _write_csv(path)
    ds = load_dataset(path, verify_checksum=False)
    assert ds.n == 8
    assert [t.txn_id for t in ds.records] == list(range(1, 9))
    assert all(0 <= t.band <= 9 for t in ds.records)
    assert all(t.risk >= 0 for t in ds.records)
    assert ds.fraud_count == 0


def test_zero_variance_features_contribute_zero_and_risk_zero_gets_band_zero(tmp_path):
    rows = 4
    frame = pd.DataFrame(
        {
            "Time": range(rows),
            **{c: [0.0] * rows for c in FEATURE_COLUMNS},
            "Amount": [1.0] * rows,
            "Class": [0] * rows,
        }
    )
    path = tmp_path / "zero.csv"
    frame.to_csv(path, index=False)
    ds = load_dataset(path, verify_checksum=False)
    assert all(t.risk == 0.0 for t in ds.records)
    assert all(t.band == 0 for t in ds.records)


def test_sampling_is_deterministic_time_ordered_and_uses_same_records(tmp_path):
    path = tmp_path / "creditcard.csv"
    _write_csv(path)
    ds = load_dataset(path, verify_checksum=False)
    a = sample_records(ds.records, 5, 232581)
    b = sample_records(ds.records, 5, 232581)
    assert a == b
    assert all(a[i].time <= a[i + 1].time for i in range(len(a) - 1))
    assert len({t.txn_id for t in a}) == 5


def test_sampling_rejects_too_many(tmp_path):
    path = tmp_path / "creditcard.csv"
    _write_csv(path, rows=3)
    ds = load_dataset(path, verify_checksum=False)
    try:
        sample_records(ds.records, 4, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("sampling too many records must fail")
