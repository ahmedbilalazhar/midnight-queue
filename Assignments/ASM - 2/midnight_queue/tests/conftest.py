import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest

from midnight_queue.records import Txn


@pytest.fixture
def make_txn():
    def _make(
        txn_id: int,
        *,
        band: int = 0,
        amount: float = 1.0,
        time: float | None = None,
        risk: float = 0.0,
        label: int = 0,
    ) -> Txn:
        return Txn(
            txn_id=txn_id,
            time=float(txn_id if time is None else time),
            amount=float(amount),
            band=int(band),
            risk=float(risk),
            label=int(label),
        )

    return _make
