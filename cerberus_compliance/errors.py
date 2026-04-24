"""Exception hierarchy for the Cerberus Compliance SDK.

All HTTP-level failures raised by the client are subclasses of
:class:`CerberusAPIError`. Each error carries the parsed RFC 7807
``application/problem+json`` document plus the ``X-Request-Id`` header
returned by the API gateway, so support tickets can pinpoint the exact
request without the caller needing to plumb extra context.

The :meth:`CerberusAPIError.from_response` factory is the single entry
point used by the transport layer: it parses the body defensively and
dispatches to the correct subclass via the ``_STATUS_DISPATCH`` table.
"""

from __future__ import annotations

import builtins
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import Any, ClassVar

__all__ = [
    "AuthError",
    "CerberusAPIError",
    "QuotaError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
]


def _http_reason(status: int) -> str:
    """Return the IANA reason phrase for ``status`` or ``"Unknown"``."""
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Unknown"


def _parse_body(
    body: bytes | str | dict[str, Any] | None,
    status: int,
) -> dict[str, Any]:
    """Coerce a raw HTTP body into an RFC 7807 problem dict.

    Falls back to a synthetic ``{"title": <reason>, ...}`` envelope when
    the body is missing, malformed, or not a JSON object.
    """
    if isinstance(body, dict):
        return body

    reason = _http_reason(status)

    if body is None:
        return {"title": reason, "status": status}

    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body

    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return {"title": reason, "detail": text, "status": status}

    if isinstance(parsed, dict):
        return parsed

    # Valid JSON but not an object (e.g. list, scalar) -> envelope.
    return {"title": reason, "detail": text, "status": status}


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header into seconds-from-now.

    Accepts either a delta-seconds integer or an HTTP-date (RFC 7231
    IMF-fixdate). Returns ``None`` for malformed or missing values; clamps
    past dates to ``0.0``.
    """
    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    # Numeric form: "60", "60.0".
    try:
        return float(stripped)
    except ValueError:
        pass

    # HTTP-date form.
    try:
        dt = parsedate_to_datetime(stripped)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = (dt - datetime.now(timezone.utc)).total_seconds()
    return max(delta, 0.0)


@dataclass
class CerberusAPIError(Exception):
    """Raised when the Cerberus API responds with a non-2xx status.

    Carries the parsed RFC 7807 problem document plus the ``X-Request-Id``
    header to make support tickets actionable.
    """

    status: int
    problem: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None

    # Populated at module import time once subclasses exist; consulted by
    # `from_response`. Use ``builtins.type`` because the class defines a
    # ``type`` property that would otherwise shadow the builtin in the
    # class scope.
    _STATUS_DISPATCH: ClassVar[dict[int, builtins.type[CerberusAPIError]]] = {}

    def __post_init__(self) -> None:
        # Initialise the underlying ``Exception`` with the rendered message
        # so ``logging.exception`` and bare ``str(exc)`` work correctly.
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = [f"{self.status} {self.title}"]
        if self.detail is not None:
            parts.append(f": {self.detail}")
        if self.request_id is not None:
            parts.append(f" [request_id={self.request_id}]")
        return "".join(parts)

    @property
    def title(self) -> str:
        """Problem ``title`` field, or the HTTP reason phrase as fallback."""
        title = self.problem.get("title")
        if isinstance(title, str) and title:
            return title
        return _http_reason(self.status)

    @property
    def detail(self) -> str | None:
        """Problem ``detail`` field, or ``None`` when absent."""
        value = self.problem.get("detail")
        return value if isinstance(value, str) else None

    @property
    def type(self) -> str:
        """Problem ``type`` URI; defaults to ``"about:blank"`` per RFC 7807."""
        value = self.problem.get("type", "about:blank")
        return value if isinstance(value, str) else "about:blank"

    @property
    def instance(self) -> str | None:
        """Problem ``instance`` URI, or ``None`` when absent."""
        value = self.problem.get("instance")
        return value if isinstance(value, str) else None

    @classmethod
    def from_response(
        cls,
        *,
        status: int,
        body: bytes | str | dict[str, Any] | None,
        request_id: str | None = None,
        retry_after: str | None = None,
    ) -> CerberusAPIError:
        """Parse ``body`` and dispatch to the correct subclass for ``status``.

        ``retry_after`` is only consulted when the dispatched subclass is
        :class:`RateLimitError`.
        """
        problem = _parse_body(body, status)
        target_cls = cls._dispatch_for(status)

        if target_cls is RateLimitError:
            return RateLimitError(
                status=status,
                problem=problem,
                request_id=request_id,
                retry_after=_parse_retry_after(retry_after),
            )

        return target_cls(status=status, problem=problem, request_id=request_id)

    @classmethod
    def _dispatch_for(cls, status: int) -> builtins.type[CerberusAPIError]:
        """Resolve the concrete subclass that represents ``status``."""
        explicit = cls._STATUS_DISPATCH.get(status)
        if explicit is not None:
            return explicit
        if 500 <= status <= 599:
            return ServerError
        return CerberusAPIError


class AuthError(CerberusAPIError):
    """Raised for ``401 Unauthorized`` and ``403 Forbidden`` responses."""


class ValidationError(CerberusAPIError):
    """Raised for ``422 Unprocessable Entity`` responses.

    Convenience: :pyattr:`errors` returns ``problem["errors"]`` or ``[]``.
    """

    @property
    def errors(self) -> list[dict[str, Any]]:
        """Field-level validation errors; empty list when absent."""
        value = self.problem.get("errors")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []


class QuotaError(CerberusAPIError):
    """Raised for ``402 Payment Required`` responses (out of quota)."""


@dataclass
class RateLimitError(CerberusAPIError):
    """Raised for ``429 Too Many Requests`` responses.

    ``retry_after`` is the parsed value of the ``Retry-After`` header,
    expressed in seconds-from-now. ``None`` when the header is missing
    or malformed.
    """

    retry_after: float | None = None


class ServerError(CerberusAPIError):
    """Raised for any ``5xx`` Server Error response."""


# Build the dispatch table after all subclasses exist.
CerberusAPIError._STATUS_DISPATCH.update(
    {
        401: AuthError,
        403: AuthError,
        402: QuotaError,
        422: ValidationError,
        429: RateLimitError,
    }
)
