"""Separate timing and peak-extra-memory measurement."""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def timed_call(function: Callable[..., T], *args: Any, **kwargs: Any) -> tuple[T, float]:
    start = time.perf_counter()
    result = function(*args, **kwargs)
    return result, time.perf_counter() - start


def peak_extra_memory(function: Callable[..., T], *args: Any, **kwargs: Any) -> tuple[T, int]:
    """Measure peak Python allocations made by one call.

    The caller must allocate input data before calling, so the result is peak
    extra memory rather than total process memory.  Never use this in a timed
    measurement.
    """

    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        result = function(*args, **kwargs)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, int(peak)
