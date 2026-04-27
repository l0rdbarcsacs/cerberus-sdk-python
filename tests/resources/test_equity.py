"""Tests for ``cerberus_compliance.resources.equity`` (P5.4.2)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError, ValidationError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.equity import (
    AsyncEquityResource,
    EquityResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestEquityMeta:
    def test_sync_prefix(self) -> None:
        assert EquityResource._path_prefix == "/equity"

    def test_async_prefix(self) -> None:
        assert AsyncEquityResource._path_prefix == "/equity"

    def test_sync_subclass(self) -> None:
        assert issubclass(EquityResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncEquityResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestEquitySync:
    def test_prices_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "ticker": "FALABELLA",
            "entity_id": "ent_1",
            "from": "2024-01-01",
            "to": "2024-03-31",
            "source": "lva",
            "prices": [
                {
                    "date": "2024-01-02",
                    "open": 1500.0,
                    "high": 1525.0,
                    "low": 1490.0,
                    "close": 1520.0,
                    "volume": 12345,
                }
            ],
            "total": 1,
        }
        route = respx_mock.get("/equity/FALABELLA/prices").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = EquityResource(sync_client)
        result = resource.prices("FALABELLA")
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_prices_with_from_and_to(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/equity/LTM/prices", params={"from": "2024-01-01", "to": "2024-03-31"}
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ticker": "LTM",
                    "entity_id": "ent_2",
                    "from": "2024-01-01",
                    "to": "2024-03-31",
                    "source": "yf",
                    "prices": [],
                    "total": 0,
                },
            )
        )
        resource = EquityResource(sync_client)
        result = resource.prices("LTM", from_="2024-01-01", to="2024-03-31")
        assert result["ticker"] == "LTM"
        assert route.called

    def test_prices_only_from(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/equity/CCU/prices", params={"from": "2024-01-01"}).mock(
            return_value=httpx.Response(200, json={"ticker": "CCU", "prices": []})
        )
        resource = EquityResource(sync_client)
        resource.prices("CCU", from_="2024-01-01")
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"from": "2024-01-01"}
        assert "to" not in params

    def test_prices_only_to(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/equity/CCU/prices", params={"to": "2024-12-31"}).mock(
            return_value=httpx.Response(200, json={"ticker": "CCU", "prices": []})
        )
        resource = EquityResource(sync_client)
        resource.prices("CCU", to="2024-12-31")
        assert route.called

    def test_prices_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/equity/CCU/prices").mock(
            return_value=httpx.Response(200, json={"ticker": "CCU", "prices": []})
        )
        resource = EquityResource(sync_client)
        resource.prices("CCU", from_=None, to=None)
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_prices_404(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/equity/BOGUS/prices").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = EquityResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.prices("BOGUS")

    def test_prices_422_validation(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/equity/CCU/prices", params={"from": "not-a-date"}).mock(
            return_value=httpx.Response(
                422,
                json={
                    "title": "Unprocessable Entity",
                    "status": 422,
                    "errors": [{"field": "from", "code": "invalid_date"}],
                },
            )
        )
        resource = EquityResource(sync_client)
        with pytest.raises(ValidationError) as exc:
            resource.prices("CCU", from_="not-a-date")
        assert exc.value.status == 422

    def test_ticker_with_dot_is_encoded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A symbol with a dot must round-trip through the path encoder
        # without breaking out of the /equity prefix.
        route = respx_mock.get("/equity/BRK.B/prices").mock(
            return_value=httpx.Response(200, json={"ticker": "BRK.B", "prices": []})
        )
        resource = EquityResource(sync_client)
        result = resource.prices("BRK.B")
        assert result["ticker"] == "BRK.B"
        assert route.called

    def test_ticker_traversal_encoded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # `..` must be percent-encoded so it cannot escape the prefix.
        route = respx_mock.get("/equity/..%2Fadmin/prices").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = EquityResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.prices("../admin")
        assert route.called


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestEquityAsync:
    async def test_prices_happy(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "ticker": "FALABELLA",
            "entity_id": "ent_1",
            "from": "2024-01-01",
            "to": "2024-03-31",
            "source": "lva",
            "prices": [{"date": "2024-01-02", "close": 1520.0}],
            "total": 1,
        }
        route = respx_mock.get(
            "/equity/FALABELLA/prices",
            params={"from": "2024-01-01", "to": "2024-03-31"},
        ).mock(return_value=httpx.Response(200, json=body))
        resource = AsyncEquityResource(async_client)
        result = await resource.prices("FALABELLA", from_="2024-01-01", to="2024-03-31")
        assert result == body
        assert route.called

    async def test_prices_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/equity/CCU/prices").mock(
            return_value=httpx.Response(200, json={"ticker": "CCU", "prices": []})
        )
        resource = AsyncEquityResource(async_client)
        await resource.prices("CCU")
        assert route.called
        assert route.calls.last.request.url.query == b""

    async def test_prices_404(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/equity/MISSING/prices").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncEquityResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.prices("MISSING")

    async def test_prices_drops_none(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/equity/CCU/prices", params={"from": "2024-01-01"}).mock(
            return_value=httpx.Response(200, json={"ticker": "CCU", "prices": []})
        )
        resource = AsyncEquityResource(async_client)
        await resource.prices("CCU", from_="2024-01-01", to=None)
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"from": "2024-01-01"}
