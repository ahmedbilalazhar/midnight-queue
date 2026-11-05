"""Keep idle standby out of a benchmark without changing the power plan."""
from contextlib import contextmanager
import sys


@contextmanager
def awake_host():
    previous=None
    if sys.platform=="win32":
        import ctypes
        previous=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        if not previous:
            raise OSError("Unable to request a temporary system-awake benchmark interval")
    try:
        yield
    finally:
        if previous:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
