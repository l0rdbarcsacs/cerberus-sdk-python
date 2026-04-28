"""Typed accessor for the Cerberus Compliance ``/webhooks`` resource.

Webhooks let callers register an HTTPS callback that the platform will
``POST`` to whenever a subscribed event fires (e.g.
``sanction.matched``, ``hecho.published``, ``export.ready``).  The full
lifecycle is mediated by this module:

- :meth:`WebhooksResource.create` — register a new endpoint.  The
  response includes the **plaintext signing secret exactly once** — the
  caller is responsible for storing it; the API will never return it again.
- :meth:`WebhooksResource.list` / :meth:`get` — inspect existing
  webhooks (without their secret).
- :meth:`update` — mutate ``callback_url``, ``event_types``, ``status``,
  or ``description`` after creation.
- :meth:`delete` — permanently remove a webhook (returns ``204``).
- :meth:`deliveries` — last 50 delivery attempts for an endpoint, with
  HTTP status, latency, and error tail.
- :meth:`test` — synthetic ping for end-to-end verification.

Signature verification
----------------------

The SDK ships a Stripe-compatible offline verifier as a ``staticmethod``
so receiving services can validate webhooks without spinning up a full
client::

    from cerberus_compliance.resources.webhooks import WebhooksResource

    ok = WebhooksResource.verify_signature(
        payload=request.body,
        signature_header=request.headers["X-Cerberus-Signature"],
        secret=os.environ["CERBERUS_WEBHOOK_SECRET"],
    )
    if not ok:
        raise HTTPException(status_code=401)
"""

from __future__ import annotations

import builtins
import hashlib
import hmac
import time
from typing import TYPE_CHECKING, Any, Literal

from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = [
    "AsyncWebhooksResource",
    "WebhookEventType",
    "WebhookStatus",
    "WebhooksResource",
]

WebhookStatus = Literal["active", "disabled"]

WebhookEventType = Literal[
    "hecho_esencial.new",
    "sancion.new",
    "resolucion.new",
    "tdc.new",
    "dictamen.new",
    "comunicacion.new",
    "opa.new",
    "art12.new",
    "art20.new",
    "entity.changed",
    "ping",
]
"""Every event type the platform may emit on a delivery.

Mirrors ``backend/schemas/v1_webhooks.py::WebhookEventType``. Passed
through verbatim to ``POST /webhooks`` and ``PATCH /webhooks/{id}``;
the server enforces the same allowlist server-side, so an unknown
value will surface as a ``422 ValidationError`` from the SDK.
"""


def _build_create_body(
    *,
    callback_url: str,
    event_types: builtins.list[WebhookEventType],
    description: str | None,
) -> dict[str, Any]:
    """Build the JSON body for ``POST /webhooks``.

    ``description`` is omitted when ``None`` so the wire payload mirrors
    the documented OpenAPI schema (the field is optional, not nullable).
    """
    body: dict[str, Any] = {
        "callback_url": callback_url,
        "event_types": event_types,
    }
    if description is not None:
        body["description"] = description
    return body


def _build_update_body(
    *,
    callback_url: str | None,
    event_types: builtins.list[WebhookEventType] | None,
    status: WebhookStatus | None,
    description: str | None,
) -> dict[str, Any]:
    """Build the JSON body for ``PATCH /webhooks/{id}``.

    Drops every ``None`` so the partial-update semantics are explicit:
    only fields the caller actually passed land on the wire.
    """
    body: dict[str, Any] = {}
    if callback_url is not None:
        body["callback_url"] = callback_url
    if event_types is not None:
        body["event_types"] = event_types
    if status is not None:
        body["status"] = status
    if description is not None:
        body["description"] = description
    return body


def _verify_signature(
    *,
    payload: bytes,
    signature_header: str,
    secret: str,
    max_age_seconds: int,
) -> bool:
    """Implementation of the Stripe-compatible HMAC-SHA256 verifier.

    Pulled out as a module-level helper so both the sync and async
    resource classes can re-expose it as a ``staticmethod`` without
    duplicating the body.
    """
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        ts = int(parts["t"])
        sig_v1 = parts["v1"]
    except (ValueError, KeyError):
        return False

    if abs(time.time() - ts) > max_age_seconds:
        return False

    signed = f"{ts}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig_v1, expected)


class WebhooksResource(BaseResource):
    """Sync accessor for the ``/webhooks`` endpoint family."""

    _path_prefix = "/webhooks"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def create(
        self,
        *,
        callback_url: str,
        event_types: builtins.list[WebhookEventType],
        description: str | None = None,
    ) -> dict[str, Any]:
        """Register a new webhook endpoint.

        The response includes a ``secret`` field — the **plaintext signing
        key**, returned exactly once.  Persist it immediately; it cannot
        be retrieved later.  Subsequent ``GET`` / ``list`` responses
        only expose a redacted ``key_prefix`` style identifier.

        Args:
            callback_url: HTTPS URL the platform will ``POST`` deliveries to.
            event_types: Subset of :data:`WebhookEventType` to subscribe.
                The server validates each entry against the allowlist —
                unknown values surface as
                :class:`~cerberus_compliance.errors.ValidationError`.
            description: Optional free-form label shown in the dashboard.
        """
        body = _build_create_body(
            callback_url=callback_url,
            event_types=event_types,
            description=description,
        )
        return self._client._request("POST", self._path_prefix, json=body)

    def list(self) -> dict[str, Any]:
        """List webhooks for the calling org.

        Returns the raw envelope so callers can inspect any
        server-supplied counters.  Secrets are never present in this
        payload.
        """
        return self._client._request("GET", self._path_prefix)

    def get(self, webhook_id: str) -> dict[str, Any]:
        """Fetch one webhook by id (without its secret)."""
        return self._get(webhook_id)

    def update(
        self,
        webhook_id: str,
        *,
        callback_url: str | None = None,
        event_types: builtins.list[WebhookEventType] | None = None,
        status: WebhookStatus | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Patch a webhook.  Only fields explicitly passed are mutated."""
        path = f"{self._path_prefix}/{_encode_id(webhook_id)}"
        body = _build_update_body(
            callback_url=callback_url,
            event_types=event_types,
            status=status,
            description=description,
        )
        return self._client._request("PATCH", path, json=body)

    def delete(self, webhook_id: str) -> None:
        """Permanently delete a webhook.  Returns ``None`` on ``204``."""
        path = f"{self._path_prefix}/{_encode_id(webhook_id)}"
        self._client._request("DELETE", path)

    def deliveries(self, webhook_id: str, *, limit: int = 50) -> dict[str, Any]:
        """Last ``limit`` delivery attempts for ``webhook_id``.

        Returned envelope includes per-delivery metadata (HTTP status,
        attempt count, response-time-ms, truncated error body).
        """
        path = f"{self._path_prefix}/{_encode_id(webhook_id)}/deliveries"
        return self._client._request("GET", path, params={"limit": limit})

    def test(self, webhook_id: str) -> dict[str, Any]:
        """Send a synthetic ping to ``webhook_id``.

        Returns ``202 Accepted`` envelope with the queued delivery id so
        the caller can poll :meth:`deliveries` for the outcome.
        """
        path = f"{self._path_prefix}/{_encode_id(webhook_id)}/test"
        return self._client._request("POST", path)

    @staticmethod
    def verify_signature(
        *,
        payload: bytes,
        signature_header: str,
        secret: str,
        max_age_seconds: int = 300,
    ) -> bool:
        """Verify a Cerberus webhook signature.

        Cerberus signs webhook deliveries with HMAC-SHA256 in the
        Stripe-compatible ``X-Cerberus-Signature`` header format::

            t=1714137600,v1=hex_hmac

        Args:
            payload: Raw HTTP body bytes the webhook delivered.
            signature_header: Value of ``X-Cerberus-Signature``.
            secret: The webhook's secret (returned once at create time).
            max_age_seconds: Max delivery age tolerated; defaults to 5 min.

        Returns ``True`` if the signature is valid AND fresh; ``False``
        otherwise.  Never raises on a malformed header.
        """
        return _verify_signature(
            payload=payload,
            signature_header=signature_header,
            secret=secret,
            max_age_seconds=max_age_seconds,
        )


class AsyncWebhooksResource(AsyncBaseResource):
    """Async mirror of :class:`WebhooksResource`."""

    _path_prefix = "/webhooks"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def create(
        self,
        *,
        callback_url: str,
        event_types: builtins.list[WebhookEventType],
        description: str | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`WebhooksResource.create`."""
        body = _build_create_body(
            callback_url=callback_url,
            event_types=event_types,
            description=description,
        )
        return await self._client._request("POST", self._path_prefix, json=body)

    async def list(self) -> dict[str, Any]:
        """Async variant of :meth:`WebhooksResource.list`."""
        return await self._client._request("GET", self._path_prefix)

    async def get(self, webhook_id: str) -> dict[str, Any]:
        """Async variant of :meth:`WebhooksResource.get`."""
        return await self._get(webhook_id)

    async def update(
        self,
        webhook_id: str,
        *,
        callback_url: str | None = None,
        event_types: builtins.list[WebhookEventType] | None = None,
        status: WebhookStatus | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`WebhooksResource.update`."""
        path = f"{self._path_prefix}/{_encode_id(webhook_id)}"
        body = _build_update_body(
            callback_url=callback_url,
            event_types=event_types,
            status=status,
            description=description,
        )
        return await self._client._request("PATCH", path, json=body)

    async def delete(self, webhook_id: str) -> None:
        """Async variant of :meth:`WebhooksResource.delete`."""
        path = f"{self._path_prefix}/{_encode_id(webhook_id)}"
        await self._client._request("DELETE", path)

    async def deliveries(self, webhook_id: str, *, limit: int = 50) -> dict[str, Any]:
        """Async variant of :meth:`WebhooksResource.deliveries`."""
        path = f"{self._path_prefix}/{_encode_id(webhook_id)}/deliveries"
        return await self._client._request("GET", path, params={"limit": limit})

    async def test(self, webhook_id: str) -> dict[str, Any]:
        """Async variant of :meth:`WebhooksResource.test`."""
        path = f"{self._path_prefix}/{_encode_id(webhook_id)}/test"
        return await self._client._request("POST", path)

    @staticmethod
    def verify_signature(
        *,
        payload: bytes,
        signature_header: str,
        secret: str,
        max_age_seconds: int = 300,
    ) -> bool:
        """Mirror of :meth:`WebhooksResource.verify_signature`.

        The verifier itself is offline (no HTTP), so the async variant
        delegates to the same shared implementation.
        """
        return _verify_signature(
            payload=payload,
            signature_header=signature_header,
            secret=secret,
            max_age_seconds=max_age_seconds,
        )
