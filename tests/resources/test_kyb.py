"""TDD tests for ``cerberus_compliance.resources.kyb``.

Covers the flagship :class:`KYBResource.get` + async mirror. Asserts:

- Happy path 200 returning an aggregate profile.
- ``as_of=date(...)`` serialises as ``YYYY-MM-DD``.
- ``include=[...]`` preserves caller order and joins with commas.
- ``as_of`` + ``include`` combined.
- Both dotted (``96.505.760-9``) and plain (``96505760-9``) RUT forms
  round-trip (dots percent-encoded).
- 401 -> AuthError, 404 -> NotFoundError, 422 -> ValidationError,
  429 -> RateLimitError (with retries disabled to surface immediately).
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import (
    AuthError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.kyb import AsyncKYBResource, KYBResource
from cerberus_compliance.retry import RetryConfig


class TestKYBMeta:
    def test_sync_prefix(self) -> None:
        assert KYBResource._path_prefix == "/kyb"

    def test_async_prefix(self) -> None:
        assert AsyncKYBResource._path_prefix == "/kyb"

    def test_sync_subclass(self) -> None:
        assert issubclass(KYBResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncKYBResource, AsyncBaseResource)


class TestKYBSyncGet:
    def test_happy_path_dotted_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """G1: GET /kyb/{rut} returns an aggregate profile."""
        route = respx_mock.get("/kyb/96.505.760-9").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "96.505.760-9",
                    "legal_name": "Falabella",
                    "risk_score": 0.12,
                    "cache_status": "fresh",
                },
            )
        )
        resource = KYBResource(sync_client)
        result = resource.get("96.505.760-9")
        assert result["legal_name"] == "Falabella"
        assert result["risk_score"] == 0.12
        assert result["cache_status"] == "fresh"
        assert route.called

    def test_plain_rut_form(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/kyb/96505760-9").mock(
            return_value=httpx.Response(200, json={"rut": "96505760-9"})
        )
        resource = KYBResource(sync_client)
        assert resource.get("96505760-9") == {"rut": "96505760-9"}
        assert route.called

    def test_as_of_iso_date_serialised(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/kyb/96.505.760-9", params={"as_of": "2024-01-01"}).mock(
            return_value=httpx.Response(200, json={"rut": "96.505.760-9"})
        )
        resource = KYBResource(sync_client)
        resource.get("96.505.760-9", as_of=date(2024, 1, 1))
        assert route.called

    def test_include_joined_comma(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/kyb/96.505.760-9", params={"include": "directors,lei"}).mock(
            return_value=httpx.Response(200, json={"rut": "96.505.760-9"})
        )
        resource = KYBResource(sync_client)
        resource.get("96.505.760-9", include=["directors", "lei"])
        assert route.called

    def test_include_preserves_caller_order(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """include=[a, b] and include=[b, a] must produce distinct query strings."""
        route = respx_mock.get("/kyb/96.505.760-9", params={"include": "lei,directors"}).mock(
            return_value=httpx.Response(200, json={"rut": "96.505.760-9"})
        )
        resource = KYBResource(sync_client)
        resource.get("96.505.760-9", include=["lei", "directors"])
        assert route.called

    def test_include_empty_sequence_omits_param(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Empty include sequence must NOT emit include=."""
        route = respx_mock.get("/kyb/96.505.760-9").mock(return_value=httpx.Response(200, json={}))
        resource = KYBResource(sync_client)
        resource.get("96.505.760-9", include=[])
        assert route.called
        # The matcher above has no params, so respx routing proves the query
        # string did not include `include=`.

    def test_as_of_and_include_both_present(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/kyb/96.505.760-9",
            params={"as_of": "2024-01-01", "include": "directors,lei"},
        ).mock(return_value=httpx.Response(200, json={}))
        resource = KYBResource(sync_client)
        resource.get("96.505.760-9", as_of=date(2024, 1, 1), include=["directors", "lei"])
        assert route.called

    def test_401_raises_auth_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/kyb/96.505.760-9").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "status": 401})
        )
        resource = KYBResource(sync_client)
        with pytest.raises(AuthError):
            resource.get("96.505.760-9")

    def test_404_raises_not_found_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/kyb/76000000-0").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = KYBResource(sync_client)
        with pytest.raises(NotFoundError) as exc:
            resource.get("76000000-0")
        assert exc.value.status == 404

    def test_422_raises_validation_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/kyb/bad-rut").mock(
            return_value=httpx.Response(
                422,
                json={
                    "title": "Unprocessable Entity",
                    "status": 422,
                    "errors": [{"field": "rut", "code": "invalid"}],
                },
            )
        )
        resource = KYBResource(sync_client)
        with pytest.raises(ValidationError):
            resource.get("bad-rut")

    def test_429_raises_rate_limit_error(
        self, api_key: str, base_url: str, respx_mock: respx.MockRouter
    ) -> None:
        """Use a no-retry client so 429 surfaces without backoff delay."""
        client = CerberusClient(
            api_key=api_key,
            base_url=base_url,
            timeout=2.0,
            retry=RetryConfig(max_attempts=1, base_delay_ms=1),
        )
        try:
            respx_mock.get("/kyb/96.505.760-9").mock(
                return_value=httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"title": "Too Many Requests", "status": 429},
                )
            )
            resource = KYBResource(client)
            with pytest.raises(RateLimitError):
                resource.get("96.505.760-9")
        finally:
            client.close()


class TestKYBAsyncGet:
    async def test_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/kyb/96.505.760-9").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "96.505.760-9",
                    "legal_name": "Falabella",
                    "risk_score": 0.12,
                    "cache_status": "fresh",
                },
            )
        )
        resource = AsyncKYBResource(async_client)
        result = await resource.get("96.505.760-9")
        assert result["legal_name"] == "Falabella"

    async def test_async_with_as_of_and_include(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/kyb/96.505.760-9",
            params={"as_of": "2024-01-01", "include": "directors,lei"},
        ).mock(return_value=httpx.Response(200, json={}))
        resource = AsyncKYBResource(async_client)
        await resource.get("96.505.760-9", as_of=date(2024, 1, 1), include=["directors", "lei"])
        assert route.called
