"""Tests for ``cerberus_compliance.resources.ipsa``."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError, ServerError, ValidationError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.ipsa import (
    AsyncIPSAResource,
    IPSAResource,
)

# ---------------------------------------------------------------------------
# Sample envelopes
# ---------------------------------------------------------------------------

RISK_PANEL_BODY = {
    "window": "~250 trading days",
    "annualisation_factor": 252,
    "tickers_total": 25,
    "tickers_skipped": 1,
    "index_proxy": {
        "method": "equal_weight",
        "observations": 250,
        "first_date": "2024-01-02",
        "last_date": "2024-12-30",
        "realized_volatility_annualised": "0.1842",
    },
    "tickers": [
        {
            "ticker": "FALABELLA",
            "observations": 250,
            "first_date": "2024-01-02",
            "last_date": "2024-12-30",
            "realized_volatility_annualised": "0.2731",
            "max_drawdown": "-0.25",
        }
    ],
}

TICKER_RISK_BODY = {
    "window": "~250 trading days",
    "annualisation_factor": 252,
    "risk": {
        "ticker": "FALABELLA",
        "observations": 250,
        "first_date": "2024-01-02",
        "last_date": "2024-12-30",
        "realized_volatility_annualised": "0.2731",
        "max_drawdown": "-0.25",
    },
}

EVENT_STUDY_BODY = {
    "identifier": "FALABELLA",
    "ticker": "FALABELLA",
    "rut": "90413000-1",
    "entity_id": "11111111-2222-3333-4444-555555555555",
    "event_type": "he",
    "method": "raw_abnormal",
    "windows_requested": ["[-1,+1]", "[-1,+5]"],
    "events_total": 3,
    "events_studied": 2,
    "events_skipped": 1,
    "events": [
        {
            "event_date": "2024-06-10",
            "event_trading_day": "2024-06-10",
            "event_id": "he_123",
            "label": "Dividendo",
            "windows": [
                {
                    "window": "[-1,+1]",
                    "start_date": "2024-06-07",
                    "end_date": "2024-06-11",
                    "start_close": "1500.0",
                    "end_close": "1530.0",
                    "raw_return": "0.02",
                    "abnormal_return": "0.015",
                }
            ],
        }
    ],
}


# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestIPSAMeta:
    def test_sync_prefix(self) -> None:
        assert IPSAResource._path_prefix == "/ipsa"

    def test_async_prefix(self) -> None:
        assert AsyncIPSAResource._path_prefix == "/ipsa"

    def test_sync_subclass(self) -> None:
        assert issubclass(IPSAResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncIPSAResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestRiskPanelSync:
    def test_risk_panel(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/ipsa/risk-panel").mock(
            return_value=httpx.Response(200, json=RISK_PANEL_BODY)
        )
        resource = IPSAResource(sync_client)
        result = resource.risk_panel()
        assert result == RISK_PANEL_BODY
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_risk_panel_500(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/ipsa/risk-panel").mock(
            return_value=httpx.Response(500, json={"title": "Internal Server Error", "status": 500})
        )
        resource = IPSAResource(sync_client)
        with pytest.raises(ServerError):
            resource.risk_panel()


class TestTickerRiskSync:
    def test_ticker_risk(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/ipsa/FALABELLA/risk").mock(
            return_value=httpx.Response(200, json=TICKER_RISK_BODY)
        )
        resource = IPSAResource(sync_client)
        result = resource.ticker_risk("FALABELLA")
        assert result == TICKER_RISK_BODY
        assert result["risk"]["ticker"] == "FALABELLA"
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_ticker_risk_lowercase_passthrough(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Client passes case verbatim; server upper-cases. The path segment
        # must be exactly what the caller passed (no client-side casing).
        route = respx_mock.get("/ipsa/falabella/risk").mock(
            return_value=httpx.Response(200, json=TICKER_RISK_BODY)
        )
        resource = IPSAResource(sync_client)
        resource.ticker_risk("falabella")
        assert route.called

    def test_ticker_risk_dot_encoded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ipsa/BRK.B/risk").mock(
            return_value=httpx.Response(200, json=TICKER_RISK_BODY)
        )
        resource = IPSAResource(sync_client)
        resource.ticker_risk("BRK.B")
        assert route.called

    def test_ticker_risk_traversal_encoded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ipsa/..%2Fadmin/risk").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = IPSAResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.ticker_risk("../admin")
        assert route.called

    def test_ticker_risk_404_typo(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/ipsa/BOGUS/risk").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = IPSAResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.ticker_risk("BOGUS")

    def test_ticker_risk_422_insufficient_history(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/ipsa/NEWTICK/risk").mock(
            return_value=httpx.Response(
                422,
                json={
                    "title": "Unprocessable Entity",
                    "status": 422,
                    "errors": [{"field": "ticker", "code": "insufficient_history"}],
                },
            )
        )
        resource = IPSAResource(sync_client)
        with pytest.raises(ValidationError) as exc:
            resource.ticker_risk("NEWTICK")
        assert exc.value.status == 422


class TestEventStudySync:
    def test_event_study_default_event(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/event-study/FALABELLA", params={"event": "he"}).mock(
            return_value=httpx.Response(200, json=EVENT_STUDY_BODY)
        )
        resource = IPSAResource(sync_client)
        result = resource.event_study("FALABELLA")
        assert result == EVENT_STUDY_BODY
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"event": "he"}

    def test_event_study_art12(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/event-study/FALABELLA", params={"event": "art12"}).mock(
            return_value=httpx.Response(200, json={**EVENT_STUDY_BODY, "event_type": "art12"})
        )
        resource = IPSAResource(sync_client)
        result = resource.event_study("FALABELLA", event="art12")
        assert result["event_type"] == "art12"
        assert route.called

    def test_event_study_by_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A RUT with dots/dash must percent-encode within the path segment.
        route = respx_mock.get("/event-study/90.413.000-1", params={"event": "he"}).mock(
            return_value=httpx.Response(200, json=EVENT_STUDY_BODY)
        )
        resource = IPSAResource(sync_client)
        resource.event_study("90.413.000-1")
        assert route.called

    def test_event_study_404_unresolved(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/event-study/NOPE", params={"event": "he"}).mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = IPSAResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.event_study("NOPE")

    def test_event_study_422_bad_event(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/event-study/FALABELLA", params={"event": "bogus"}).mock(
            return_value=httpx.Response(
                422,
                json={
                    "title": "Unprocessable Entity",
                    "status": 422,
                    "errors": [{"field": "event", "code": "invalid_value"}],
                },
            )
        )
        resource = IPSAResource(sync_client)
        # ``event`` is a Literal at type-check time; at runtime the client
        # forwards whatever it gets and the server returns 422. We cast via
        # ``str`` so the (intentional) bad value still exercises the path.
        with pytest.raises(ValidationError) as exc:
            resource.event_study("FALABELLA", event="bogus")  # type: ignore[arg-type]  # exercise server 422
        assert exc.value.status == 422


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestRiskPanelAsync:
    async def test_risk_panel(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ipsa/risk-panel").mock(
            return_value=httpx.Response(200, json=RISK_PANEL_BODY)
        )
        resource = AsyncIPSAResource(async_client)
        result = await resource.risk_panel()
        assert result == RISK_PANEL_BODY
        assert route.called
        assert route.calls.last.request.url.query == b""


class TestTickerRiskAsync:
    async def test_ticker_risk(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ipsa/FALABELLA/risk").mock(
            return_value=httpx.Response(200, json=TICKER_RISK_BODY)
        )
        resource = AsyncIPSAResource(async_client)
        result = await resource.ticker_risk("FALABELLA")
        assert result == TICKER_RISK_BODY
        assert route.called

    async def test_ticker_risk_404(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/ipsa/MISSING/risk").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncIPSAResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.ticker_risk("MISSING")

    async def test_ticker_risk_422(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/ipsa/NEWTICK/risk").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable Entity", "status": 422})
        )
        resource = AsyncIPSAResource(async_client)
        with pytest.raises(ValidationError):
            await resource.ticker_risk("NEWTICK")


class TestEventStudyAsync:
    async def test_event_study_default(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/event-study/FALABELLA", params={"event": "he"}).mock(
            return_value=httpx.Response(200, json=EVENT_STUDY_BODY)
        )
        resource = AsyncIPSAResource(async_client)
        result = await resource.event_study("FALABELLA")
        assert result == EVENT_STUDY_BODY
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"event": "he"}

    async def test_event_study_art12(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/event-study/FALABELLA", params={"event": "art12"}).mock(
            return_value=httpx.Response(200, json=EVENT_STUDY_BODY)
        )
        resource = AsyncIPSAResource(async_client)
        await resource.event_study("FALABELLA", event="art12")
        assert route.called

    async def test_event_study_404(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/event-study/NOPE", params={"event": "he"}).mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncIPSAResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.event_study("NOPE")
