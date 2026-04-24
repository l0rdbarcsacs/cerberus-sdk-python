"""Retry policy primitives for the Cerberus Compliance SDK.

This module exposes a small, dependency-free retry layer:

* :class:`RetryConfig` — immutable, validated configuration object.
* :func:`backoff_seconds` — compute the sleep delay for the next attempt
  (exponential backoff with optional jitter and ``Retry-After`` override).
* :func:`should_retry` — decide whether an HTTP failure should be retried.

The functions are pure and synchronous so they can be reused unchanged by both
the synchronous and asynchronous transport layers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

__all__ = ["RetryConfig", "backoff_seconds", "should_retry"]


@dataclass(frozen=True)
class RetryConfig:
    """Immutable retry policy.

    Attributes:
        max_attempts: Total attempt budget (>= 1). ``1`` means no retries.
        base_delay_ms: First-attempt delay in milliseconds (> 0).
        max_delay_ms: Hard ceiling for any single sleep (>= base_delay_ms).
        retry_on: HTTP status codes that trigger a retry. Each entry must be
            in ``[100, 599]``.
        jitter: When ``True``, multiply the computed delay by a uniform
            factor in ``[0.5, 1.5]`` to avoid thundering-herd effects.
    """

    max_attempts: int = 3
    base_delay_ms: int = 200
    max_delay_ms: int = 10_000
    retry_on: tuple[int, ...] = (429, 500, 502, 503, 504)
    jitter: bool = True

    def __post_init__(self) -> None:
        """Validate the policy. Raises :class:`ValueError` on bad input."""
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {self.max_attempts}")
        if self.base_delay_ms <= 0:
            raise ValueError(f"base_delay_ms must be > 0, got {self.base_delay_ms}")
        if self.max_delay_ms < self.base_delay_ms:
            raise ValueError(
                "max_delay_ms must be >= base_delay_ms "
                f"(max_delay_ms={self.max_delay_ms}, base_delay_ms={self.base_delay_ms})"
            )
        for status in self.retry_on:
            if not (100 <= status <= 599):
                raise ValueError(
                    f"retry_on entries must be HTTP status codes in [100, 599], got {status}"
                )


def backoff_seconds(
    attempt: int,
    cfg: RetryConfig,
    *,
    retry_after: float | None = None,
) -> float:
    """Compute the sleep duration before the next retry attempt.

    Args:
        attempt: 1-based attempt index — ``1`` schedules the second try, etc.
        cfg: Active :class:`RetryConfig`.
        retry_after: Server-suggested delay (e.g. parsed from the
            ``Retry-After`` header). When provided and ``>= 0`` it overrides
            the exponential backoff but is still capped by
            ``cfg.max_delay_ms``.

    Returns:
        Number of seconds to sleep (always ``>= 0``).
    """
    max_seconds = cfg.max_delay_ms / 1000.0

    if retry_after is not None and retry_after >= 0:
        return min(retry_after, max_seconds)

    # Exponential backoff in milliseconds, then clamp before unit conversion.
    raw_ms = cfg.base_delay_ms * (2 ** (attempt - 1))
    clamped_ms = min(raw_ms, cfg.max_delay_ms)
    delay_seconds = clamped_ms / 1000.0

    if cfg.jitter:
        factor = random.uniform(0.5, 1.5)
        delay_seconds = delay_seconds * factor

    # Final clamp: never negative, never above max.
    bounded: float = max(0.0, min(delay_seconds, max_seconds))
    return bounded


def should_retry(*, status: int, attempt: int, cfg: RetryConfig) -> bool:
    """Decide whether to retry after observing ``status`` on attempt ``attempt``.

    Args:
        status: HTTP status code just received.
        attempt: How many attempts have already been made (``1`` after the
            first try).
        cfg: Active :class:`RetryConfig`.

    Returns:
        ``True`` iff ``status`` is in :attr:`RetryConfig.retry_on` *and* the
        attempt budget has not been exhausted.
    """
    if attempt >= cfg.max_attempts:
        return False
    return status in cfg.retry_on
