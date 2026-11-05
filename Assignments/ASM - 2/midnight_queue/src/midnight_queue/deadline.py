"""Hard measured-region deadlines for disposable benchmark child processes."""
from contextlib import contextmanager
import os
from threading import Timer

TIMEOUT_EXIT_CODE=124


@contextmanager
def algorithm_deadline(seconds: float | None):
    """Kill only the benchmark child when its algorithm budget is exhausted.

    The parent additionally enforces a generous process envelope. CSV/cache
    reading and reference verification happen outside this measured-region
    guard. Use this only inside disposable benchmark workers.
    """
    if seconds is None:
        yield
        return
    if seconds<=0:
        os._exit(TIMEOUT_EXIT_CODE)
    timer=Timer(seconds,os._exit,args=(TIMEOUT_EXIT_CODE,))
    timer.daemon=True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
