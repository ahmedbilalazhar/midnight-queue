"""Assignment configuration and personal parameters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "creditcard.csv"

ROLL_DISPLAY = "23I-2581"
SEED = 232581
SECTION = "DS-B"
REQUIRED_SIZES = (1_000, 10_000, 100_000, 284_807)
FULL_ROWS = 284_807
SHIFT_MODULUS = 226


def shift_capacity(seed: int) -> int:
    """Return the assignment's K = 25 + (s mod 226)."""

    if seed < 0:
        raise ValueError("roll-number seed must be non-negative")
    return 25 + (seed % SHIFT_MODULUS)


@dataclass(frozen=True, slots=True)
class AssignmentConfig:
    roll_display: str
    seed: int
    section: str
    k: int
    sizes: tuple[int, ...] = REQUIRED_SIZES

    def __post_init__(self) -> None:
        digits = re.sub(r"\D", "", self.roll_display)
        if not digits:
            raise ValueError("roll number must contain digits")
        if int(digits) != self.seed:
            raise ValueError(
                f"roll digits {digits!r} do not match seed {self.seed}"
            )
        if self.k != shift_capacity(self.seed):
            raise ValueError("K does not satisfy K = 25 + (seed mod 226)")
        if any(n <= 0 for n in self.sizes):
            raise ValueError("dataset sizes must be positive")
        if tuple(sorted(set(self.sizes))) != tuple(self.sizes):
            raise ValueError("dataset sizes must be strictly increasing")

    @classmethod
    def from_roll(
        cls,
        roll_display: str,
        section: str,
        sizes: tuple[int, ...] = REQUIRED_SIZES,
    ) -> "AssignmentConfig":
        digits = re.sub(r"\D", "", roll_display)
        if not digits:
            raise ValueError("roll number must contain digits")
        seed = int(digits)
        return cls(roll_display, seed, section, shift_capacity(seed), sizes)

    @property
    def submission_stem(self) -> str:
        return f"{self.roll_display}-A2-{self.section}"


CONFIG = AssignmentConfig.from_roll(ROLL_DISPLAY, SECTION)


def load_config() -> AssignmentConfig:
    return CONFIG
