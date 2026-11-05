from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from midnight_queue.config import AssignmentConfig, shift_capacity
from midnight_queue.data import FEATURE_COLUMNS, load_dataset


def test_personal_parameters():
    assert shift_capacity(232581) == 52
    config = AssignmentConfig.from_roll("23I-2581", "DS-B")
    assert config.seed == 232581
    assert config.k == 52
    assert config.submission_stem == "23I-2581-A2-DS-B"


def test_configuration_rejects_wrong_k():
    with pytest.raises(ValueError):
        AssignmentConfig("23I-2581", 232581, "DS-B", 51)


def _frame(rows=3):
    return pd.DataFrame(
        {
            "Time": list(range(rows)),
            **{c: [0.0] * rows for c in FEATURE_COLUMNS},
            "Amount": [1.0] * rows,
            "Class": [0] * rows,
        }
    )


def test_loader_rejects_unsorted_time(tmp_path):
    frame = _frame()
    # [0, 1, 0] is descending at the last pair; [0, 0, 2] would still be
    # non-decreasing and therefore a valid arrival order.
    frame.loc[2, "Time"] = 0
    path = tmp_path / "bad.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="ascending"):
        load_dataset(path, verify_checksum=False)


def test_loader_rejects_nonfinite(tmp_path):
    frame = _frame()
    frame.loc[0, "V1"] = np.inf
    path = tmp_path / "bad.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="non-finite"):
        load_dataset(path, verify_checksum=False)


def test_loader_rejects_bad_class(tmp_path):
    frame = _frame()
    frame.loc[0, "Class"] = 2
    path = tmp_path / "bad.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="Class"):
        load_dataset(path, verify_checksum=False)


def test_loader_rejects_missing_column(tmp_path):
    frame = _frame().drop(columns=["V3"])
    path = tmp_path / "bad.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing required columns"):
        load_dataset(path, verify_checksum=False)
