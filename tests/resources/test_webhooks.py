"""Tests for ``cerberus_compliance.resources.webhooks`` (P5.4.2)."""

from __future__ import annotations

import hashlib
import hmac
import json as _json
import time

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.webhooks import (
    AsyncWebhooksResource,
    WebhooksResource,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signature(*, secret: str, payload: bytes, ts: int) -> str:
    """Compute the canonical Stripe-style signature header for testing."""
    signed = f"{ts}.".encode() + payload
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestWebhooksMeta:
    def test_sync_prefix(self) -> None:
        assert WebhooksResource._path_prefix == "/webhooks"

    def test_async_prefix(self) -> None:
        assert AsyncWebhooksResource._path_prefix == "/webhooks"

    def test_sync_subclass(self) -> None:
        assert issubclass(WebhooksResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncWebhooksResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestWebhooksSync:
    def test_create_returns_secret_once(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "id": "wh_123",
            "callback_url": "https://example.com/cerberus",
            "event_types": ["sanction.matched"],
            "status": "active",
            "secret": "whsec_super_secret_value",
        }
        route = respx_mock.post("/webhooks").mock(return_value=httpx.Response(201, json=body))
        resource = WebhooksResource(sync_client)
        result = resource.create(
            callback_url="https://example.com/cerberus",
            event_types=["sanction.matched"],
        )
        assert result == body
        sent = _json.loads(route.calls.last.request.content)
        assert sent == {
            "callback_url": "https://example.com/cerberus",
            "event_types": ["sanction.matched"],
        }

    def test_create_with_description(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/webhooks").mock(
            return_value=httpx.Response(201, json={"id": "wh_x", "secret": "s"})
        )
        resource = WebhooksResource(sync_client)
        resource.create(
            callback_url="https://x",
            event_types=["a", "b"],
            description="Production sanctions stream",
        )
        sent = _json.loads(route.calls.last.request.content)
        assert sent["description"] == "Production sanctions stream"

    def test_list(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {"data": [{"id": "wh_1"}, {"id": "wh_2"}], "next": None}
        respx_mock.get("/webhooks").mock(return_value=httpx.Response(200, json=body))
        resource = WebhooksResource(sync_client)
        assert resource.list() == body

    def test_get(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/webhooks/wh_42").mock(
            return_value=httpx.Response(200, json={"id": "wh_42", "status": "active"})
        )
        resource = WebhooksResource(sync_client)
        assert resource.get("wh_42") == {"id": "wh_42", "status": "active"}

    def test_get_404(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/webhooks/missing").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = WebhooksResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("missing")

    def test_update_partial(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.patch("/webhooks/wh_1").mock(
            return_value=httpx.Response(200, json={"id": "wh_1", "status": "disabled"})
        )
        resource = WebhooksResource(sync_client)
        result = resource.update("wh_1", status="disabled")
        assert result["status"] == "disabled"
        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"status": "disabled"}

    def test_update_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.patch("/webhooks/wh_1").mock(
            return_value=httpx.Response(200, json={"id": "wh_1"})
        )
        resource = WebhooksResource(sync_client)
        resource.update(
            "wh_1",
            callback_url="https://new",
            event_types=None,
            status=None,
            description=None,
        )
        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"callback_url": "https://new"}

    def test_delete(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.delete("/webhooks/wh_x").mock(return_value=httpx.Response(204))
        resource = WebhooksResource(sync_client)
        # delete() returns None per its annotation — just make sure it
        # neither raises nor leaves the route uncalled.
        resource.delete("wh_x")
        assert route.called

    def test_deliveries(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {"data": [{"id": "del_1", "status": 200}], "next": None}
        route = respx_mock.get("/webhooks/wh_1/deliveries", params={"limit": "50"}).mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = WebhooksResource(sync_client)
        assert resource.deliveries("wh_1") == body
        assert route.called

    def test_deliveries_custom_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/webhooks/wh_1/deliveries", params={"limit": "5"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = WebhooksResource(sync_client)
        resource.deliveries("wh_1", limit=5)
        assert route.called

    def test_test_endpoint(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.post("/webhooks/wh_1/test").mock(
            return_value=httpx.Response(202, json={"delivery_id": "del_test_1"})
        )
        resource = WebhooksResource(sync_client)
        result = resource.test("wh_1")
        assert result == {"delivery_id": "del_test_1"}
        assert route.called


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestWebhooksAsync:
    async def test_create(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/webhooks").mock(
            return_value=httpx.Response(201, json={"id": "wh", "secret": "s"})
        )
        resource = AsyncWebhooksResource(async_client)
        result = await resource.create(callback_url="https://x", event_types=["e"], description="d")
        assert result == {"id": "wh", "secret": "s"}

    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/webhooks").mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = AsyncWebhooksResource(async_client)
        assert await resource.list() == {"data": [], "next": None}

    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/webhooks/wh_a").mock(return_value=httpx.Response(200, json={"id": "wh_a"}))
        resource = AsyncWebhooksResource(async_client)
        assert await resource.get("wh_a") == {"id": "wh_a"}

    async def test_update(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.patch("/webhooks/wh_a").mock(
            return_value=httpx.Response(200, json={"id": "wh_a", "status": "active"})
        )
        resource = AsyncWebhooksResource(async_client)
        await resource.update("wh_a", callback_url="https://new", event_types=["x", "y"])
        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"callback_url": "https://new", "event_types": ["x", "y"]}

    async def test_delete(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.delete("/webhooks/wh_a").mock(return_value=httpx.Response(204))
        resource = AsyncWebhooksResource(async_client)
        await resource.delete("wh_a")
        assert route.called

    async def test_deliveries(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/webhooks/wh_a/deliveries", params={"limit": "50"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = AsyncWebhooksResource(async_client)
        assert await resource.deliveries("wh_a") == {"data": [], "next": None}

    async def test_test(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/webhooks/wh_a/test").mock(
            return_value=httpx.Response(202, json={"delivery_id": "d1"})
        )
        resource = AsyncWebhooksResource(async_client)
        assert await resource.test("wh_a") == {"delivery_id": "d1"}


# ---------------------------------------------------------------------------
# Signature verifier (offline — no HTTP)
# ---------------------------------------------------------------------------


class TestVerifySignature:
    SECRET = "whsec_test_super_secret"
    PAYLOAD = b'{"event": "sanction.matched", "id": "evt_1"}'

    def test_valid_fresh(self) -> None:
        ts = int(time.time())
        header = _make_signature(secret=self.SECRET, payload=self.PAYLOAD, ts=ts)
        assert (
            WebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header=header,
                secret=self.SECRET,
            )
            is True
        )

    def test_wrong_secret(self) -> None:
        ts = int(time.time())
        header = _make_signature(secret=self.SECRET, payload=self.PAYLOAD, ts=ts)
        assert (
            WebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header=header,
                secret="whsec_different",
            )
            is False
        )

    def test_tampered_payload(self) -> None:
        ts = int(time.time())
        header = _make_signature(secret=self.SECRET, payload=self.PAYLOAD, ts=ts)
        assert (
            WebhooksResource.verify_signature(
                payload=b'{"event": "tampered"}',
                signature_header=header,
                secret=self.SECRET,
            )
            is False
        )

    def test_stale_timestamp(self) -> None:
        # 10 minutes in the past — outside the default 5-minute window.
        ts = int(time.time()) - 600
        header = _make_signature(secret=self.SECRET, payload=self.PAYLOAD, ts=ts)
        assert (
            WebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header=header,
                secret=self.SECRET,
            )
            is False
        )

    def test_future_timestamp_rejected(self) -> None:
        ts = int(time.time()) + 3600
        header = _make_signature(secret=self.SECRET, payload=self.PAYLOAD, ts=ts)
        assert (
            WebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header=header,
                secret=self.SECRET,
            )
            is False
        )

    @pytest.mark.parametrize(
        "header",
        [
            "",
            "garbage",
            "t=abc,v1=def",  # non-numeric timestamp
            "v1=abc",  # missing t
            "t=123",  # missing v1
            "no_equals_at_all",
        ],
    )
    def test_malformed_header(self, header: str) -> None:
        # Verifier must NEVER raise — only return False on bad input.
        assert (
            WebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header=header,
                secret=self.SECRET,
            )
            is False
        )

    def test_custom_max_age(self) -> None:
        # Header is 100s old; default 5-min tolerance accepts it but a
        # tighter 30s window must reject it.
        ts = int(time.time()) - 100
        header = _make_signature(secret=self.SECRET, payload=self.PAYLOAD, ts=ts)
        assert (
            WebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header=header,
                secret=self.SECRET,
            )
            is True
        )
        assert (
            WebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header=header,
                secret=self.SECRET,
                max_age_seconds=30,
            )
            is False
        )

    def test_async_verifier_mirror(self) -> None:
        """Async resource exposes the same staticmethod with identical semantics."""
        ts = int(time.time())
        header = _make_signature(secret=self.SECRET, payload=self.PAYLOAD, ts=ts)
        assert (
            AsyncWebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header=header,
                secret=self.SECRET,
            )
            is True
        )
        assert (
            AsyncWebhooksResource.verify_signature(
                payload=self.PAYLOAD,
                signature_header="garbage",
                secret=self.SECRET,
            )
            is False
        )
