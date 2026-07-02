"""TDD tests for ``cerberus_compliance.resources.indicadores`` (P5.2 G8).

The ``IndicadoresResource`` wraps ``/indicadores/{series_id}`` (the
canonical handle is the dotted BCCh ``series_id``, e.g.
``F073.UFF.PRE.Z.D``) with two public affordances:

* :meth:`IndicadoresResource.get` — single-date lookup (no ``date`` arg
  means "latest").
* :meth:`IndicadoresResource.history` — historical range issued as
  ``?from=YYYY-MM-DD&to=YYYY-MM-DD`` (matching the live API contract in
  ``backend/api/v1_public/indicadores.py``).

Server envelopes are returned verbatim by ``get`` (single document) and
unwrapped for ``history`` (the ``items`` array of date/value pairs from
the ``IndicadorSeries`` schema).
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError, ServerError, ValidationError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.indicadores import (
    AsyncIndicadoresResource,
    IndicadoresResource,
)
from cerberus_compliance.retry import RetryConfig

# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


class TestIndicadoresMeta:
    def test_sync_prefix(self) -> None:
        assert IndicadoresResource._path_prefix == "/indicadores"

    def test_async_prefix(self) -> None:
        assert AsyncIndicadoresResource._path_prefix == "/indicadores"

    def test_sync_subclass(self) -> None:
        assert issubclass(IndicadoresResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncIndicadoresResource, AsyncBaseResource)

    def test_client_wires_attribute(self, sync_client: CerberusClient) -> None:
        assert isinstance(sync_client.indicadores, IndicadoresResource)


# ---------------------------------------------------------------------------
# Sync: IndicadoresResource.get
# ---------------------------------------------------------------------------


class TestIndicadoresGet:
    def test_get_latest_no_date_param(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores/F073.UFF.PRE.Z.D").mock(
            return_value=httpx.Response(
                200,
                json={
                    "name": "F073.UFF.PRE.Z.D",
                    "date": "2026-04-24",
                    "value": "39421.73",
                    "source": "bcentral_api",
                    "title_es": "Unidad de fomento (UF)",
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        result = resource.get("F073.UFF.PRE.Z.D")
        assert result["value"] == "39421.73"
        assert result["title_es"] == "Unidad de fomento (UF)"
        assert route.called
        # No ``date`` query param should have been forwarded.
        request = route.calls.last.request
        assert "date" not in request.url.params

    def test_get_dotted_series_id_path_not_mangled(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Dotted BCCh ``series_id`` travels verbatim in the URL path.

        ``urllib.parse.quote`` never percent-encodes ``.`` (unreserved),
        so ``F073.UFF.PRE.Z.D`` must reach the server literally — this is
        the canonical-handle contract (series_id in, ``title_es`` out).
        """
        route = respx_mock.get("/indicadores/F073.UFF.PRE.Z.D").mock(
            return_value=httpx.Response(
                200,
                json={
                    "series_id": "F073.UFF.PRE.Z.D",
                    "title_es": "Unidad de fomento (UF)",
                    "value": "39421.73",
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        result = resource.get("F073.UFF.PRE.Z.D")
        assert route.called
        assert result["series_id"] == "F073.UFF.PRE.Z.D"
        assert result["title_es"]
        # The dots must NOT be percent-encoded on the wire.
        assert route.calls.last.request.url.path.endswith("/indicadores/F073.UFF.PRE.Z.D")

    def test_get_with_date_param(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores/UF", params={"date": "2026-04-24"}).mock(
            return_value=httpx.Response(
                200,
                json={"name": "UF", "date": "2026-04-24", "value": "39421.73"},
            )
        )
        resource = IndicadoresResource(sync_client)
        result = resource.get("UF", date="2026-04-24")
        assert result["date"] == "2026-04-24"
        assert route.called

    def test_get_percent_encodes_name(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Path-traversal hardening — ``name`` is percent-encoded."""
        route = respx_mock.get("/indicadores/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = IndicadoresResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("../admin")
        assert route.called

    def test_get_404_raises_not_found_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/indicadores/BOGUS").mock(
            return_value=httpx.Response(
                404,
                json={"type": "about:blank", "title": "Not Found", "status": 404},
            )
        )
        resource = IndicadoresResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get("BOGUS")


# ---------------------------------------------------------------------------
# Sync: IndicadoresResource.history
# ---------------------------------------------------------------------------


class TestIndicadoresHistory:
    def test_history_forwards_from_to_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/indicadores/UF",
            params={"from": "2026-01-01", "to": "2026-04-30"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "name": "UF",
                    "source": "cmf_api_sbifv3",
                    "items": [
                        {"date": "2026-01-01", "value": "38989.15"},
                        {"date": "2026-04-24", "value": "39421.73"},
                    ],
                    "total": 2,
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        series = resource.history("UF", from_="2026-01-01", to="2026-04-30")
        assert series == [
            {"date": "2026-01-01", "value": "38989.15"},
            {"date": "2026-04-24", "value": "39421.73"},
        ]
        assert route.called

    def test_history_empty_items_returns_empty_list(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/indicadores/UF",
            params={"from": "2026-01-01", "to": "2026-01-31"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "name": "UF",
                    "source": "cmf_api_sbifv3",
                    "items": [],
                    "total": 0,
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        assert resource.history("UF", from_="2026-01-01", to="2026-01-31") == []

    def test_history_malformed_items_defensively_returns_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Defensive: a server bug returning ``items: null`` must not raise."""
        respx_mock.get(
            "/indicadores/UF",
            params={"from": "2026-01-01", "to": "2026-04-30"},
        ).mock(return_value=httpx.Response(200, json={"name": "UF", "items": None}))
        resource = IndicadoresResource(sync_client)
        assert resource.history("UF", from_="2026-01-01", to="2026-04-30") == []

    @pytest.mark.parametrize(
        ("bad_from", "bad_to"),
        [
            ("2026/01/01", "2026-04-30"),
            ("2026-04-30", "2026/04"),
            ("", "2026-04-30"),
            ("not-a-date", "2026-04-30"),
            # Calendar-invalid: caught by date.fromisoformat (was silently
            # accepted by the previous char-by-char check).
            ("2026-13-01", "2026-04-30"),
            ("2026-02-30", "2026-04-30"),
        ],
    )
    def test_history_rejects_non_iso_dates(
        self, sync_client: CerberusClient, bad_from: str, bad_to: str
    ) -> None:
        resource = IndicadoresResource(sync_client)
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            resource.history("UF", from_=bad_from, to=bad_to)

    def test_history_rejects_non_string_dates(self, sync_client: CerberusClient) -> None:
        """Non-string inputs hit the ``isinstance`` guard before parsing."""
        resource = IndicadoresResource(sync_client)
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            resource.history("UF", from_=20260101, to="2026-04-30")  # type: ignore[arg-type]

    def test_history_422_raises_validation_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/indicadores/UF",
            params={"from": "2026-04-01", "to": "2026-01-01"},
        ).mock(
            return_value=httpx.Response(
                422,
                json={
                    "type": "about:blank",
                    "title": "Validation error",
                    "status": 422,
                    "detail": "from > to",
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        with pytest.raises(ValidationError):
            resource.history("UF", from_="2026-04-01", to="2026-01-01")


# ---------------------------------------------------------------------------
# Sync: IndicadoresResource.forecast
# ---------------------------------------------------------------------------


_FORECAST_BODY = {
    "name": "F073.UFF.PRE.Z.D",
    "title_es": "Unidad de fomento (UF)",
    "source": "bcentral_api",
    "model": "timesfm-1.0-200m",
    "horizon": 6,
    "context_points": 1024,
    "interval_pct": 80,
    "interval_method": "calibrated-quantiles",
    "points": [
        {"step": 1, "point": "39421.73", "lower": "39400.00", "upper": "39443.00"},
        {"step": 2, "point": "39430.10", "lower": "39405.00", "upper": "39455.00"},
    ],
    "disclaimer": "Model forecast, not advice. Past performance is not indicative.",
}


class TestIndicadoresForecast:
    def test_forecast_default_horizon_omits_param(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores/UF/forecast").mock(
            return_value=httpx.Response(200, json=_FORECAST_BODY)
        )
        resource = IndicadoresResource(sync_client)
        result = resource.forecast("UF")
        assert result["model"] == "timesfm-1.0-200m"
        assert result["points"][0]["point"] == "39421.73"
        assert route.called
        # No ``horizon`` query param when omitted.
        assert "horizon" not in route.calls.last.request.url.params

    def test_forecast_with_horizon_forwards_param(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores/UF/forecast", params={"horizon": "12"}).mock(
            return_value=httpx.Response(200, json={**_FORECAST_BODY, "horizon": 12})
        )
        resource = IndicadoresResource(sync_client)
        result = resource.forecast("UF", horizon=12)
        assert result["horizon"] == 12
        assert route.called
        assert route.calls.last.request.url.params["horizon"] == "12"

    def test_forecast_percent_encodes_name(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Path-traversal hardening — ``name`` is percent-encoded."""
        route = respx_mock.get("/indicadores/..%2Fadmin/forecast").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = IndicadoresResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.forecast("../admin")
        assert route.called

    def test_forecast_404_unknown_name(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/indicadores/BOGUS/forecast").mock(
            return_value=httpx.Response(
                404,
                json={"type": "about:blank", "title": "Not Found", "status": 404},
            )
        )
        resource = IndicadoresResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.forecast("BOGUS")

    def test_forecast_422_horizon_out_of_range(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/indicadores/UF/forecast", params={"horizon": "999"}).mock(
            return_value=httpx.Response(
                422,
                json={
                    "type": "about:blank",
                    "title": "Validation error",
                    "status": 422,
                    "detail": "horizon must be <= 256",
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        with pytest.raises(ValidationError):
            resource.forecast("UF", horizon=999)

    def test_forecast_503_model_not_provisioned(
        self, base_url: str, api_key: str, respx_mock: respx.MockRouter
    ) -> None:
        """503 (model not provisioned) surfaces as ServerError; capacity absence.

        Uses ``max_attempts=1`` so the retryable 503 is raised immediately
        without sleeping through the backoff schedule.
        """
        respx_mock.get("/indicadores/UF/forecast").mock(
            return_value=httpx.Response(
                503,
                headers={"Retry-After": "3600"},
                json={"detail": "forecast model not provisioned"},
            )
        )
        client = CerberusClient(
            api_key=api_key,
            base_url=base_url,
            timeout=2.0,
            retry=RetryConfig(max_attempts=1),
        )
        try:
            resource = IndicadoresResource(client)
            with pytest.raises(ServerError) as excinfo:
                resource.forecast("UF")
            assert excinfo.value.status == 503
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Async mirrors
# ---------------------------------------------------------------------------


class TestIndicadoresAsync:
    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/indicadores/UF", params={"date": "2026-04-24"}).mock(
            return_value=httpx.Response(
                200,
                json={"name": "UF", "date": "2026-04-24", "value": "39421.73"},
            )
        )
        resource = AsyncIndicadoresResource(async_client)
        out = await resource.get("UF", date="2026-04-24")
        assert out["value"] == "39421.73"

    async def test_history(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/indicadores/UF", params={"from": "2026-01-01", "to": "2026-04-30"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "name": "UF",
                    "source": "cmf_api_sbifv3",
                    "items": [{"date": "2026-01-01", "value": "38989.15"}],
                    "total": 1,
                },
            )
        )
        resource = AsyncIndicadoresResource(async_client)
        series = await resource.history("UF", from_="2026-01-01", to="2026-04-30")
        assert series == [{"date": "2026-01-01", "value": "38989.15"}]

    async def test_history_rejects_bad_dates(self, async_client: AsyncCerberusClient) -> None:
        resource = AsyncIndicadoresResource(async_client)
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            await resource.history("UF", from_="nope", to="2026-04-30")

    async def test_history_malformed_items_defensively_returns_empty(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Async mirror of the defensive null-items branch."""
        respx_mock.get("/indicadores/UF", params={"from": "2026-01-01", "to": "2026-04-30"}).mock(
            return_value=httpx.Response(200, json={"name": "UF", "items": None})
        )
        resource = AsyncIndicadoresResource(async_client)
        assert await resource.history("UF", from_="2026-01-01", to="2026-04-30") == []

    async def test_forecast_default_horizon(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores/UF/forecast").mock(
            return_value=httpx.Response(200, json=_FORECAST_BODY)
        )
        resource = AsyncIndicadoresResource(async_client)
        out = await resource.forecast("UF")
        assert out["interval_pct"] == 80
        assert "horizon" not in route.calls.last.request.url.params

    async def test_forecast_with_horizon(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores/PIB/forecast", params={"horizon": "4"}).mock(
            return_value=httpx.Response(200, json={**_FORECAST_BODY, "name": "PIB", "horizon": 4})
        )
        resource = AsyncIndicadoresResource(async_client)
        out = await resource.forecast("PIB", horizon=4)
        assert out["horizon"] == 4
        assert route.calls.last.request.url.params["horizon"] == "4"

    async def test_forecast_404_unknown_name(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/indicadores/BOGUS/forecast").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncIndicadoresResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.forecast("BOGUS")

    async def test_forecast_503_model_not_provisioned(
        self, base_url: str, api_key: str, respx_mock: respx.MockRouter
    ) -> None:
        """Async mirror of the 503 capacity-absence branch (no retry sleeps)."""
        respx_mock.get("/indicadores/UF/forecast").mock(
            return_value=httpx.Response(
                503,
                headers={"Retry-After": "3600"},
                json={"detail": "forecast model not provisioned"},
            )
        )
        client = AsyncCerberusClient(
            api_key=api_key,
            base_url=base_url,
            timeout=2.0,
            retry=RetryConfig(max_attempts=1),
        )
        try:
            resource = AsyncIndicadoresResource(client)
            with pytest.raises(ServerError) as excinfo:
                await resource.forecast("UF")
            assert excinfo.value.status == 503
        finally:
            await client.close()


# ---------------------------------------------------------------------------
# Sync: IndicadoresResource.buscar (discovery over ~25k BCCh series)
# ---------------------------------------------------------------------------


class TestIndicadoresBuscar:
    def test_buscar_forwards_all_filter_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/indicadores/buscar",
            params={
                "q": "cobre",
                "frequency": "MONTHLY",
                "family": "F019",
                "limit": "20",
                "offset": "0",
            },
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "series_id": "F019.PPB.PRE.40.M",
                            "title_es": "Precio del cobre refinado BML (dólares/libra)",
                            "frequency": "MONTHLY",
                            "source": "bcentral_api",
                            "tracked": True,
                            "has_forecast": True,
                        }
                    ],
                    "total": 1,
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        results = resource.buscar(q="cobre", frequency="MONTHLY", family="F019", limit=20, offset=0)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["series_id"] == "F019.PPB.PRE.40.M"
        assert results[0]["title_es"]
        assert route.called

    def test_buscar_no_params_omits_query_string(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """``buscar()`` with no args collapses ``params`` to ``None``."""
        route = respx_mock.get("/indicadores/buscar").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = IndicadoresResource(sync_client)
        resource.buscar()
        assert route.called
        request = route.calls.last.request
        for param in ("q", "frequency", "family", "limit", "offset"):
            assert param not in request.url.params

    def test_buscar_unwraps_data_envelope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """A ``{"data": [...]}`` envelope (SDK-documented shape) unwraps too."""
        respx_mock.get("/indicadores/buscar", params={"q": "uf"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "series_id": "F073.UFF.PRE.Z.D",
                            "title_es": "Unidad de fomento (UF)",
                            "frequency": "DAILY",
                            "source": "bcentral_api",
                            "tracked": True,
                            "has_forecast": True,
                        }
                    ]
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        results = resource.buscar(q="uf")
        assert len(results) == 1
        assert results[0]["series_id"] == "F073.UFF.PRE.Z.D"

    def test_buscar_empty_returns_empty_list(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/indicadores/buscar", params={"q": "nomatch"}).mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = IndicadoresResource(sync_client)
        assert resource.buscar(q="nomatch") == []

    def test_buscar_bare_list_response(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """A bare top-level JSON array is wrapped by ``_request`` as
        ``{"data": [...]}`` and unwrapped again by ``_extract_items``.
        """
        respx_mock.get("/indicadores/buscar", params={"family": "F073"}).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series_id": "F073.UFF.PRE.Z.D",
                        "title_es": "Unidad de fomento (UF)",
                        "frequency": "DAILY",
                        "source": "bcentral_api",
                        "tracked": True,
                        "has_forecast": True,
                    }
                ],
            )
        )
        resource = IndicadoresResource(sync_client)
        results = resource.buscar(family="F073")
        assert results == [
            {
                "series_id": "F073.UFF.PRE.Z.D",
                "title_es": "Unidad de fomento (UF)",
                "frequency": "DAILY",
                "source": "bcentral_api",
                "tracked": True,
                "has_forecast": True,
            }
        ]


class TestIndicadoresList:
    def test_list_unwraps_items_envelope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "name": "F073.UFF.PRE.Z.D",
                            "title_es": "Unidad de fomento (UF)",
                            "source": "bcentral_api",
                            "frequency": "daily",
                            "min_date": "1977-01-01",
                            "max_date": "2026-06-26",
                            "latest_value": "40133.5",
                            "latest_date": "2026-06-26",
                            "has_forecast": True,
                        }
                    ],
                    "total": 1,
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        results = resource.list()
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["name"] == "F073.UFF.PRE.Z.D"
        assert results[0]["has_forecast"] is True
        assert route.called
        # The catalog endpoint takes no query params — none must be sent.
        assert not dict(route.calls.last.request.url.params)

    def test_list_empty_catalog_returns_empty_list(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/indicadores").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = IndicadoresResource(sync_client)
        assert resource.list() == []


class TestIndicadoresCompare:
    _COMPARE_BODY: ClassVar[dict[str, Any]] = {
        "series": [
            {
                "name": "F073.UFF.PRE.Z.D",
                "source": "bcentral_api",
                "title_es": "Unidad de fomento (UF)",
                "items": [{"date": "2026-05-01", "value": "40133.5"}],
            },
            {
                "name": "F074.IPC.IND.Z.2023.C.M",
                "source": "bcentral_api",
                "title_es": "IPC",
                "items": [{"date": "2026-05-01", "value": "104.5"}],
            },
        ]
    }

    def test_compare_joins_series_ids_and_forwards_range(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/indicadores/compare",
            params={
                "names": "F073.UFF.PRE.Z.D,F074.IPC.IND.Z.2023.C.M",
                "from": "2026-05-01",
                "to": "2026-06-01",
            },
        ).mock(return_value=httpx.Response(200, json=self._COMPARE_BODY))
        resource = IndicadoresResource(sync_client)
        series = resource.compare(
            ["F073.UFF.PRE.Z.D", "F074.IPC.IND.Z.2023.C.M"],
            from_="2026-05-01",
            to="2026-06-01",
        )
        assert [s["name"] for s in series] == [
            "F073.UFF.PRE.Z.D",
            "F074.IPC.IND.Z.2023.C.M",
        ]
        assert series[0]["items"] == [{"date": "2026-05-01", "value": "40133.5"}]
        assert route.called

    def test_compare_rejects_bare_string_series_ids(self, sync_client: CerberusClient) -> None:
        """A bare ``str`` would be comma-joined char by char — hard error."""
        resource = IndicadoresResource(sync_client)
        with pytest.raises(ValueError, match="sequence of series_id strings"):
            resource.compare(
                "F073.UFF.PRE.Z.D",  # type: ignore[arg-type]
                from_="2026-05-01",
                to="2026-06-01",
            )

    def test_compare_rejects_non_iso_dates(self, sync_client: CerberusClient) -> None:
        resource = IndicadoresResource(sync_client)
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            resource.compare(
                ["F073.UFF.PRE.Z.D", "F074.IPC.IND.Z.2023.C.M"],
                from_="2026/05/01",
                to="2026-06-01",
            )

    def test_compare_422_raises_validation_error(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Cardinality (2-6 series) is enforced server-side → 422."""
        respx_mock.get(
            "/indicadores/compare",
            params={"names": "F073.UFF.PRE.Z.D", "from": "2026-05-01", "to": "2026-06-01"},
        ).mock(
            return_value=httpx.Response(
                422,
                json={
                    "type": "about:blank",
                    "title": "Validation error",
                    "status": 422,
                    "detail": "Provide between 2 and 6 comma-separated indicator names.",
                },
            )
        )
        resource = IndicadoresResource(sync_client)
        with pytest.raises(ValidationError):
            resource.compare(["F073.UFF.PRE.Z.D"], from_="2026-05-01", to="2026-06-01")

    def test_compare_malformed_series_defensively_returns_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Defensive: ``series: null`` (or missing) must not raise."""
        respx_mock.get(
            "/indicadores/compare",
            params={
                "names": "F073.UFF.PRE.Z.D,F074.IPC.IND.Z.2023.C.M",
                "from": "2026-05-01",
                "to": "2026-06-01",
            },
        ).mock(return_value=httpx.Response(200, json={"series": None}))
        resource = IndicadoresResource(sync_client)
        assert (
            resource.compare(
                ["F073.UFF.PRE.Z.D", "F074.IPC.IND.Z.2023.C.M"],
                from_="2026-05-01",
                to="2026-06-01",
            )
            == []
        )


class TestIndicadoresListCompareAsync:
    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "name": "F073.UFF.PRE.Z.D",
                            "title_es": "Unidad de fomento (UF)",
                            "source": "bcentral_api",
                            "frequency": "daily",
                            "has_forecast": True,
                        }
                    ],
                    "total": 1,
                },
            )
        )
        resource = AsyncIndicadoresResource(async_client)
        results = await resource.list()
        assert len(results) == 1
        assert results[0]["name"] == "F073.UFF.PRE.Z.D"
        assert route.called

    async def test_compare(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/indicadores/compare",
            params={
                "names": "F073.UFF.PRE.Z.D,F074.IPC.IND.Z.2023.C.M",
                "from": "2026-05-01",
                "to": "2026-06-01",
            },
        ).mock(return_value=httpx.Response(200, json=TestIndicadoresCompare._COMPARE_BODY))
        resource = AsyncIndicadoresResource(async_client)
        series = await resource.compare(
            ["F073.UFF.PRE.Z.D", "F074.IPC.IND.Z.2023.C.M"],
            from_="2026-05-01",
            to="2026-06-01",
        )
        assert [s["name"] for s in series] == [
            "F073.UFF.PRE.Z.D",
            "F074.IPC.IND.Z.2023.C.M",
        ]
        assert route.called

    async def test_compare_rejects_bare_string_series_ids(
        self, async_client: AsyncCerberusClient
    ) -> None:
        resource = AsyncIndicadoresResource(async_client)
        with pytest.raises(ValueError, match="sequence of series_id strings"):
            await resource.compare(
                "F073.UFF.PRE.Z.D",  # type: ignore[arg-type]
                from_="2026-05-01",
                to="2026-06-01",
            )

    async def test_compare_rejects_non_iso_dates(self, async_client: AsyncCerberusClient) -> None:
        resource = AsyncIndicadoresResource(async_client)
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            await resource.compare(
                ["F073.UFF.PRE.Z.D", "F074.IPC.IND.Z.2023.C.M"],
                from_="2026-05-01",
                to="bad",
            )


class TestIndicadoresBuscarAsync:
    async def test_buscar_forwards_all_filter_params(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/indicadores/buscar",
            params={
                "q": "cobre",
                "frequency": "MONTHLY",
                "family": "F019",
                "limit": "20",
                "offset": "0",
            },
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "series_id": "F019.PPB.PRE.40.M",
                            "title_es": "Precio del cobre refinado BML (dólares/libra)",
                            "frequency": "MONTHLY",
                            "source": "bcentral_api",
                            "tracked": True,
                            "has_forecast": True,
                        }
                    ],
                    "total": 1,
                },
            )
        )
        resource = AsyncIndicadoresResource(async_client)
        results = await resource.buscar(
            q="cobre", frequency="MONTHLY", family="F019", limit=20, offset=0
        )
        assert len(results) == 1
        assert results[0]["series_id"] == "F019.PPB.PRE.40.M"
        assert route.called

    async def test_buscar_no_params_omits_query_string(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/indicadores/buscar").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )
        resource = AsyncIndicadoresResource(async_client)
        assert await resource.buscar() == []
        assert route.called
        request = route.calls.last.request
        for param in ("q", "frequency", "family", "limit", "offset"):
            assert param not in request.url.params
