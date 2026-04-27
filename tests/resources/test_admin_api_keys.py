"""Tests for ``cerberus_compliance.resources.admin_api_keys`` (P5.4.2)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import AuthError, RateLimitError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.admin_api_keys import (
    AdminApiKeysResource,
    AsyncAdminApiKeysResource,
)
from cerberus_compliance.retry import RetryConfig

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestAdminApiKeysMeta:
    def test_sync_prefix(self) -> None:
        assert AdminApiKeysResource._path_prefix == "/admin/api-keys"

    def test_async_prefix(self) -> None:
        assert AsyncAdminApiKeysResource._path_prefix == "/admin/api-keys"

    def test_sync_subclass(self) -> None:
        assert issubclass(AdminApiKeysResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncAdminApiKeysResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestAdminApiKeysSync:
    def test_me_happy_path(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "key_prefix": "ck_live_4f2e",
            "env": "live",
            "tier": "growth",
            "scopes": ["read", "write"],
            "expires_at": "2026-01-01T00:00:00Z",
            "last_used_at": "2025-04-25T13:30:00Z",
            "quota": {
                "monthly_limit": 10000,
                "monthly_consumed": 1234,
                "monthly_remaining": 8766,
                "period_end": "2025-05-01T00:00:00Z",
            },
            "daily_quota": {
                "daily_limit": 1000,
                "daily_consumed": 50,
                "daily_remaining": 950,
                "period_end": "2025-04-26T00:00:00Z",
            },
        }
        route = respx_mock.get("/admin/api-keys/me").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AdminApiKeysResource(sync_client)
        result = resource.me()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_me_returns_dict(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/admin/api-keys/me").mock(
            return_value=httpx.Response(200, json={"key_prefix": "ck_test_1234"})
        )
        resource = AdminApiKeysResource(sync_client)
        result = resource.me()
        assert isinstance(result, dict)
        assert result["key_prefix"] == "ck_test_1234"

    def test_me_401_raises_auth_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/admin/api-keys/me").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "status": 401})
        )
        resource = AdminApiKeysResource(sync_client)
        with pytest.raises(AuthError):
            resource.me()

    def test_me_429_raises_rate_limit(
        self, api_key: str, base_url: str, respx_mock: respx.MockRouter
    ) -> None:
        client = CerberusClient(
            api_key=api_key,
            base_url=base_url,
            timeout=2.0,
            retry=RetryConfig(max_attempts=1, base_delay_ms=1),
        )
        try:
            respx_mock.get("/admin/api-keys/me").mock(
                return_value=httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"title": "Too Many Requests", "status": 429},
                )
            )
            resource = AdminApiKeysResource(client)
            with pytest.raises(RateLimitError):
                resource.me()
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestAdminApiKeysAsync:
    async def test_me_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "key_prefix": "ck_live_abc1",
            "env": "live",
            "tier": "enterprise",
            "scopes": ["read"],
            "expires_at": None,
            "last_used_at": "2025-04-25T13:30:00Z",
            "quota": {
                "monthly_limit": 100000,
                "monthly_consumed": 0,
                "monthly_remaining": 100000,
                "period_end": "2025-05-01T00:00:00Z",
            },
            "daily_quota": {
                "daily_limit": 10000,
                "daily_consumed": 0,
                "daily_remaining": 10000,
                "period_end": "2025-04-26T00:00:00Z",
            },
        }
        route = respx_mock.get("/admin/api-keys/me").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncAdminApiKeysResource(async_client)
        result = await resource.me()
        assert result == body
        assert route.called

    async def test_me_401_raises_auth_error(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/admin/api-keys/me").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "status": 401})
        )
        resource = AsyncAdminApiKeysResource(async_client)
        with pytest.raises(AuthError):
            await resource.me()

    async def test_me_no_query_params(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/admin/api-keys/me").mock(return_value=httpx.Response(200, json={}))
        resource = AsyncAdminApiKeysResource(async_client)
        await resource.me()
        assert route.called
        assert route.calls.last.request.url.query == b""
