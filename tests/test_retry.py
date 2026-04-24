"""Unit tests for `cerberus_compliance.retry`.

Strict TDD: written before any implementation exists. Each test exercises
exactly one behavior from the public contract documented in the module.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cerberus_compliance.retry import RetryConfig, backoff_seconds, should_retry

# ---------------------------------------------------------------------------
# RetryConfig validation
# ---------------------------------------------------------------------------


class TestRetryConfigValidation:
    """`RetryConfig.__post_init__` must reject invalid configurations."""

    def test_defaults_are_valid(self) -> None:
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.base_delay_ms == 200
        assert cfg.max_delay_ms == 10_000
        assert cfg.retry_on == (429, 500, 502, 503, 504)
        assert cfg.jitter is True

    def test_is_frozen(self) -> None:
        cfg = RetryConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.max_attempts = 9  # type: ignore[misc]  # frozen-dataclass mutation test

    @pytest.mark.parametrize("bad_attempts", [0, -1, -10])
    def test_rejects_max_attempts_below_one(self, bad_attempts: int) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            RetryConfig(max_attempts=bad_attempts)

    @pytest.mark.parametrize("bad_base", [0, -1, -100])
    def test_rejects_non_positive_base_delay(self, bad_base: int) -> None:
        with pytest.raises(ValueError, match="base_delay_ms"):
            RetryConfig(base_delay_ms=bad_base)

    def test_rejects_max_smaller_than_base(self) -> None:
        with pytest.raises(ValueError, match="max_delay_ms"):
            RetryConfig(base_delay_ms=500, max_delay_ms=100)

    def test_allows_max_equal_to_base(self) -> None:
        cfg = RetryConfig(base_delay_ms=200, max_delay_ms=200)
        assert cfg.max_delay_ms == cfg.base_delay_ms

    @pytest.mark.parametrize("bad_status", [50, 99, 600, 1000, 0, -1])
    def test_rejects_out_of_range_retry_on_codes(self, bad_status: int) -> None:
        with pytest.raises(ValueError, match="retry_on"):
            RetryConfig(retry_on=(200, bad_status))

    def test_accepts_full_valid_status_range(self) -> None:
        cfg = RetryConfig(retry_on=(100, 200, 599))
        assert cfg.retry_on == (100, 200, 599)


# ---------------------------------------------------------------------------
# backoff_seconds — deterministic (jitter=False)
# ---------------------------------------------------------------------------


class TestBackoffNoJitter:
    """With jitter disabled the function is pure exponential * base, clamped."""

    def test_attempt_1_is_base_delay(self) -> None:
        cfg = RetryConfig(base_delay_ms=200, max_delay_ms=10_000, jitter=False)
        assert backoff_seconds(1, cfg) == pytest.approx(0.2)

    def test_doubles_each_attempt(self) -> None:
        cfg = RetryConfig(base_delay_ms=100, max_delay_ms=10_000, jitter=False)
        assert backoff_seconds(1, cfg) == pytest.approx(0.1)
        assert backoff_seconds(2, cfg) == pytest.approx(0.2)
        assert backoff_seconds(3, cfg) == pytest.approx(0.4)
        assert backoff_seconds(4, cfg) == pytest.approx(0.8)

    def test_clamps_to_max_delay(self) -> None:
        cfg = RetryConfig(base_delay_ms=1_000, max_delay_ms=2_500, jitter=False)
        # attempt 1 -> 1.0s, attempt 2 -> 2.0s, attempt 3 -> 4.0s clamped to 2.5s
        assert backoff_seconds(1, cfg) == pytest.approx(1.0)
        assert backoff_seconds(2, cfg) == pytest.approx(2.0)
        assert backoff_seconds(3, cfg) == pytest.approx(2.5)
        assert backoff_seconds(99, cfg) == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# backoff_seconds — jitter=True
# ---------------------------------------------------------------------------


class TestBackoffWithJitter:
    """Jitter multiplies the (clamped) exponential by U[0.5, 1.5]."""

    def test_jitter_within_bounds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = RetryConfig(base_delay_ms=200, max_delay_ms=10_000, jitter=True)
        # Patch random.uniform → return its lower bound
        monkeypatch.setattr("cerberus_compliance.retry.random.uniform", lambda a, _b: a)
        assert backoff_seconds(1, cfg) == pytest.approx(0.2 * 0.5)

        monkeypatch.setattr("cerberus_compliance.retry.random.uniform", lambda _a, b: b)
        assert backoff_seconds(1, cfg) == pytest.approx(0.2 * 1.5)

    def test_jitter_passes_correct_bounds_to_uniform(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, tuple[float, float]] = {}

        def fake_uniform(a: float, b: float) -> float:
            captured["bounds"] = (a, b)
            return 1.0  # neutral multiplier

        monkeypatch.setattr("cerberus_compliance.retry.random.uniform", fake_uniform)
        cfg = RetryConfig(base_delay_ms=100, max_delay_ms=10_000, jitter=True)
        backoff_seconds(2, cfg)
        assert captured["bounds"] == (0.5, 1.5)

    def test_jitter_never_exceeds_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = RetryConfig(base_delay_ms=1_000, max_delay_ms=2_000, jitter=True)
        # Force jitter to its max factor; even after multiplication we cap at max.
        monkeypatch.setattr("cerberus_compliance.retry.random.uniform", lambda _a, b: b)
        # attempt 5 exponential = 16_000ms clamped to 2_000ms; *1.5 -> 3.0s but capped at 2.0s
        assert backoff_seconds(5, cfg) == pytest.approx(2.0)

    def test_jitter_never_below_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Defensive: lower bound is 0.5 so this is naturally satisfied,
        # but if uniform returned a negative we still clamp.
        cfg = RetryConfig(base_delay_ms=100, max_delay_ms=10_000, jitter=True)
        monkeypatch.setattr("cerberus_compliance.retry.random.uniform", lambda *_: -5.0)
        assert backoff_seconds(1, cfg) >= 0.0


# ---------------------------------------------------------------------------
# backoff_seconds — retry_after override
# ---------------------------------------------------------------------------


class TestBackoffRetryAfter:
    """`retry_after` (server-suggested) wins over backoff, but is still capped."""

    def test_positive_retry_after_used_directly(self) -> None:
        cfg = RetryConfig(base_delay_ms=200, max_delay_ms=10_000, jitter=True)
        assert backoff_seconds(5, cfg, retry_after=2.5) == pytest.approx(2.5)

    def test_retry_after_zero_is_honored(self) -> None:
        cfg = RetryConfig(base_delay_ms=200, max_delay_ms=10_000, jitter=True)
        assert backoff_seconds(1, cfg, retry_after=0.0) == pytest.approx(0.0)

    def test_retry_after_clamped_to_max(self) -> None:
        cfg = RetryConfig(base_delay_ms=200, max_delay_ms=5_000, jitter=False)
        assert backoff_seconds(1, cfg, retry_after=999.0) == pytest.approx(5.0)

    def test_negative_retry_after_falls_back_to_backoff(self) -> None:
        cfg = RetryConfig(base_delay_ms=200, max_delay_ms=10_000, jitter=False)
        # negative retry_after is ignored → use exponential path
        assert backoff_seconds(1, cfg, retry_after=-1.0) == pytest.approx(0.2)

    def test_retry_after_none_falls_back_to_backoff(self) -> None:
        cfg = RetryConfig(base_delay_ms=200, max_delay_ms=10_000, jitter=False)
        assert backoff_seconds(1, cfg, retry_after=None) == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# should_retry matrix
# ---------------------------------------------------------------------------


class TestShouldRetry:
    """`should_retry` combines status check + attempt budget."""

    def test_retryable_status_with_attempts_left(self) -> None:
        cfg = RetryConfig(max_attempts=3)
        assert should_retry(status=503, attempt=1, cfg=cfg) is True
        assert should_retry(status=429, attempt=2, cfg=cfg) is True

    def test_non_retryable_status(self) -> None:
        cfg = RetryConfig(max_attempts=5)
        assert should_retry(status=400, attempt=1, cfg=cfg) is False
        assert should_retry(status=404, attempt=1, cfg=cfg) is False
        assert should_retry(status=200, attempt=1, cfg=cfg) is False

    def test_no_attempts_left(self) -> None:
        cfg = RetryConfig(max_attempts=3)
        assert should_retry(status=500, attempt=3, cfg=cfg) is False
        assert should_retry(status=500, attempt=4, cfg=cfg) is False

    def test_max_attempts_one_means_no_retry_ever(self) -> None:
        cfg = RetryConfig(max_attempts=1)
        assert should_retry(status=503, attempt=1, cfg=cfg) is False

    def test_custom_retry_on_set(self) -> None:
        cfg = RetryConfig(max_attempts=3, retry_on=(418,))
        assert should_retry(status=418, attempt=1, cfg=cfg) is True
        assert should_retry(status=503, attempt=1, cfg=cfg) is False
