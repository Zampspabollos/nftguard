"""Limitador de intentos de login en memoria: sencillo a propósito, pensado para
una única instancia de backend (el caso de uso de nftguard), no para un cluster."""

import time
from collections import defaultdict

_WINDOW_SECONDS = 300
_MAX_FAILURES = 5
_LOCKOUT_SECONDS = 60

_failures: dict[str, list[float]] = defaultdict(list)


def _recent(key: str, now: float) -> list[float]:
    attempts = [t for t in _failures.get(key, []) if now - t < _WINDOW_SECONDS]
    _failures[key] = attempts
    return attempts


def is_locked_out(key: str) -> tuple[bool, int]:
    now = time.monotonic()
    attempts = _recent(key, now)
    if len(attempts) < _MAX_FAILURES:
        return False, 0
    remaining = int(_LOCKOUT_SECONDS - (now - max(attempts)))
    return (remaining > 0), max(remaining, 0)


def register_failure(key: str) -> None:
    _failures[key].append(time.monotonic())


def clear(key: str) -> None:
    _failures.pop(key, None)
