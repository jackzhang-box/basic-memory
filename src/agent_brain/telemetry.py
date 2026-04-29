"""No-op telemetry stubs.

All external telemetry (Logfire) has been removed for internal use.
This module preserves the public API surface so that existing callers
continue to work without changes — every function is a silent no-op.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


def configure_telemetry(
    service_name: str,
    *,
    environment: str,
    service_version: str | None = None,
    log_level: str = "INFO",
) -> bool:
    """No-op. Returns False (telemetry is always disabled)."""
    return False


def telemetry_enabled() -> bool:
    """Always returns False."""
    return False


@contextmanager
def contextualize(**attrs: Any) -> Iterator[None]:
    """No-op context manager."""
    yield


@contextmanager
def scope(name: str, **attrs: Any) -> Iterator[None]:
    """No-op context manager."""
    yield


operation = scope


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[None]:
    """No-op context manager."""
    yield


@contextmanager
def started_span(name: str, **attrs: Any) -> Iterator[Any | None]:
    """No-op context manager that yields None."""
    yield None


__all__ = [
    "contextualize",
    "configure_telemetry",
    "operation",
    "scope",
    "span",
    "started_span",
    "telemetry_enabled",
]
