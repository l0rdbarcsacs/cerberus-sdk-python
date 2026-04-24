"""Authentication helpers for the Cerberus Compliance SDK.

Provides:

* :class:`ApiKeyAuth` — an :class:`httpx.Auth` implementation that injects the
  ``Authorization: Bearer <api_key>`` header (and a default ``User-Agent``)
  on every outbound request.
* :func:`resolve_api_key` — explicit-arg → environment-variable → error
  resolution for the API key.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Final

import httpx

from cerberus_compliance import __version__

__all__ = ["API_KEY_ENV_VAR", "ApiKeyAuth", "resolve_api_key"]

API_KEY_ENV_VAR: Final[str] = "CERBERUS_API_KEY"

_DEFAULT_USER_AGENT: Final[str] = f"cerberus-compliance/{__version__}"


class ApiKeyAuth(httpx.Auth):
    """Authenticate every outbound request with a bearer API key.

    Adds ``Authorization: Bearer <api_key>`` and, when not already set by the
    caller, a ``User-Agent: cerberus-compliance/<sdk_version>`` header.
    """

    requires_request_body = False
    requires_response_body = False

    def __init__(self, api_key: str) -> None:
        """Store the API key after validating it is non-empty."""
        if not api_key or not api_key.strip():
            raise ValueError("api_key must be a non-empty, non-whitespace string")
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        """Return the configured API key (verbatim)."""
        return self._api_key

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Inject auth headers and yield the request exactly once."""
        request.headers["Authorization"] = f"Bearer {self._api_key}"
        # Treat httpx's auto-injected default UA as "absent" so the SDK identifies
        # itself by default; preserve any UA the caller explicitly set.
        existing_ua = request.headers.get("User-Agent")
        if existing_ua is None or existing_ua.startswith("python-httpx/"):
            request.headers["User-Agent"] = _DEFAULT_USER_AGENT
        yield request


def resolve_api_key(api_key: str | None) -> str:
    """Resolve the effective API key from explicit argument or environment.

    Resolution order:

    1. ``api_key`` argument when non-empty / non-whitespace.
    2. ``$CERBERUS_API_KEY`` when non-empty / non-whitespace.
    3. Raise :class:`ValueError`.
    """
    if api_key is not None and api_key.strip():
        return api_key

    env_value = os.environ.get(API_KEY_ENV_VAR)
    if env_value is not None and env_value.strip():
        return env_value

    raise ValueError("Cerberus API key not provided. Pass api_key= or set CERBERUS_API_KEY.")
