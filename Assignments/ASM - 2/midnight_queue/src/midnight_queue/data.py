"""Data loading, validation, standardisation and risk scoring."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .records import Txn

FEATURE_COLUMNS = tuple(f"V{i}" for i in range(1, 29))
REQUIRED_COLUMNS = ("Time", *FEATURE_COLUMNS, "Amount", "Class")
EXPECTED_ROWS = 284_807
EXPECTED_FRAUDS = 492
EXPECTED_SHA256 = "76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89"


@dataclass(frozen=True, slots=True)
class Dataset:
    records: tuple[Txn, ...]
    means: tuple[float, ...]
    stds: tuple[float, ...]
    sha256: str
    source_path: str
    fraud_count: int

    @property
    def n(self) -> int:
        return len(self.records)

    def __len__(self) -> int:
        return len(self.records)


def file_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_dataset(path: str | Path, *, verify_checksum: bool = True) -> Dataset:
    """Load and validate the official credit-card CSV.

    Risk uses population z-scores over the full input file.  No rows are
    imputed, dropped or sorted here.  txn_id is the original 1-based row number.
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {path}. Download creditcard.csv from Kaggle."
        )
    checksum = file_sha256(path) if verify_checksum else ""
    if verify_checksum and checksum != EXPECTED_SHA256:
        raise ValueError("dataset SHA-256 differs from the official creditcard.csv; "
                         "use verify_checksum=False only for explicitly synthetic tests")

    frame = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if len(frame) == 0:
        raise ValueError("dataset is empty")
    if frame[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("dataset contains missing values")

    numeric = frame[list(REQUIRED_COLUMNS)].apply(pd.to_numeric, errors="raise")
    matrix = numeric.to_numpy(dtype=np.float64, copy=False)
    if not np.isfinite(matrix).all():
        raise ValueError("dataset contains non-finite values")

    time = matrix[:, 0]
    amount = matrix[:, 29]
    label_float = matrix[:, 30]
    if (time < 0).any():
        raise ValueError("Time must be non-negative")
    if not np.all(np.diff(time) >= 0):
        raise ValueError("raw file is not in ascending Time order")
    if not np.isin(label_float, (0.0, 1.0)).all():
        raise ValueError("Class must contain only 0/1")

    features = matrix[:, 1:29]
    means = features.mean(axis=0)
    stds = features.std(axis=0, ddof=0)
    safe_stds = np.where(stds == 0.0, 1.0, stds)
    z = (features - means) / safe_stds
    z[:, stds == 0.0] = 0.0
    risk = np.square(z).sum(axis=1)
    if not np.isfinite(risk).all():
        raise ValueError("risk score overflowed to a non-finite value")

    bands = np.zeros(len(risk), dtype=np.int64)
    positive = risk > 0.0
    bands[positive] = np.floor(np.log2(risk[positive])).astype(np.int64)
    np.clip(bands, 0, 9, out=bands)

    labels = label_float.astype(np.int64)
    records = tuple(
        Txn(
            txn_id=i + 1,
            time=float(time[i]),
            amount=float(amount[i]),
            band=int(bands[i]),
            risk=float(risk[i]),
            label=int(labels[i]),
        )
        for i in range(len(frame))
    )
    if verify_checksum and (len(records) != EXPECTED_ROWS or int(labels.sum()) != EXPECTED_FRAUDS):
        raise ValueError("official dataset row/fraud counts do not match the assignment")
    return Dataset(
        records=records,
        means=tuple(float(v) for v in means),
        stds=tuple(float(v) for v in stds),
        sha256=checksum,
        source_path=str(path.resolve()),
        fraud_count=int(labels.sum()),
    )


def sample_records(records: tuple[Txn, ...], n: int, seed: int) -> list[Txn]:
    """Sample uniformly without replacement, then restore Time order.

    The refresh of RNG state at each requested n is deliberate and documented.
    """

    if n <= 0:
        return []
    if n > len(records):
        raise ValueError(f"cannot sample {n} records from {len(records)}")
    if n == len(records):
        sampled = list(records)
    else:
        rng = np.random.default_rng(seed)
        indices = rng.choice(len(records), size=n, replace=False)
        sampled = [records[int(i)] for i in indices]
    sampled.sort(key=lambda t: (t.time, t.txn_id))
    return sampled


def dataset_profile(dataset: Dataset) -> dict[str, object]:
    risk = np.fromiter((t.risk for t in dataset.records), dtype=np.float64)
    bands = np.fromiter((t.band for t in dataset.records), dtype=np.int64)
    amounts = np.fromiter((t.amount for t in dataset.records), dtype=np.float64)
    labels = np.fromiter((t.label for t in dataset.records), dtype=np.int64)
    band_counts = np.bincount(bands, minlength=10)
    amount_values, amount_counts = np.unique(amounts, return_counts=True)
    top_amount_order = np.argsort(-amount_counts, kind="stable")[:10]
    top_share = float(amount_counts[top_amount_order].sum() / len(amounts))
    fraud_by_band = np.bincount(bands[labels == 1], minlength=10)
    return {
        "rows": dataset.n,
        "fraud_count": int(labels.sum()),
        "band_counts": {int(i): int(c) for i, c in enumerate(band_counts)},
        "distinct_amounts": int(len(amount_values)),
        "top10_amount_share": top_share,
        "top10_amounts": [
            {"amount": float(amount_values[i]), "count": int(amount_counts[i])}
            for i in top_amount_order
        ],
        "fraud_by_band": {int(i): int(c) for i, c in enumerate(fraud_by_band)},
        "sha256": dataset.sha256,
        "source_path": dataset.source_path,
        "expected_rows": EXPECTED_ROWS,
        "expected_frauds": EXPECTED_FRAUDS,
    }
