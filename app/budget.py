"""Cooperative CPU deadline; no background thread outlives a rejected request."""

from contextlib import contextmanager
from contextvars import ContextVar
import time


_deadline = ContextVar('recommendation_deadline', default=None)


class WorkloadTimeout(RuntimeError):
    pass


def check():
    deadline = _deadline.get()
    if deadline is not None and time.monotonic() >= deadline:
        raise WorkloadTimeout('Recommendation workload exceeded its time budget')


@contextmanager
def computation(seconds=20):
    token = _deadline.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)
