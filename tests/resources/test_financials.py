"""Tests for ``cerberus_compliance.resources.financials``.

Covers the five per-entity endpoints (summary / ratios / distress /
benchmark / timeseries) plus the two public aggregate endpoints
(distress histogram / sector stats), in both the sync and async surfaces.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.financials import (
    AsyncFinancialsResource,
    FinancialsResource,
)

RUT = "96505760-9"


# ---------------------------------------------------------------------------
# Metadata / wiring
# ---------------------------------------------------------------------------


class TestFinancialsMeta:
    def test_sync_prefix(self) -> None:
        assert FinancialsResource._path_prefix == "/entities"

    def test_async_prefix(self) -> None:
        assert AsyncFinancialsResource._path_prefix == "/entities"

    def test_sync_subclass(self) -> None:
        assert issubclass(FinancialsResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncFinancialsResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# get_summary — GET /entities/{rut}/financials
# ---------------------------------------------------------------------------


class TestSummarySync:
    def test_happy_path(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "rut": RUT,
            "periodo": "202312",
            "has_ifrs": True,
            "key_accounts": [
                {
                    "cuenta_codigo": "10000",
                    "valor": "12345.67",
                    "cuenta_descripcion": "Activos totales",
                    "tipo_estado": "BS",
                    "tipo_norma": "C",
                }
            ],
        }
        route = respx_mock.get(f"/entities/{RUT}/financials").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_summary(RUT)
        assert out == body
        assert out["key_accounts"][0]["valor"] == "12345.67"
        assert route.called

    def test_no_ifrs_returns_200(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"rut": "00000000-0", "periodo": None, "has_ifrs": False, "key_accounts": []}
        respx_mock.get("/entities/00000000-0/financials").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_summary("00000000-0")
        assert out["has_ifrs"] is False
        assert out["periodo"] is None

    def test_percent_encodes_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/..%2Fadmin/financials").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = FinancialsResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get_summary("../admin")
        assert route.called


class TestSummaryAsync:
    async def test_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"rut": RUT, "periodo": "202312", "has_ifrs": True, "key_accounts": []}
        respx_mock.get(f"/entities/{RUT}/financials").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_summary(RUT)
        assert out == body


# ---------------------------------------------------------------------------
# get_ratios — GET /entities/{rut}/financials/ratios
# ---------------------------------------------------------------------------


class TestRatiosSync:
    def test_happy_path(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        ratio_period = {
            "periodo": "202312",
            "tipo_norma": "C",
            "current_ratio": "1.42",
            "debt_to_equity": "0.85",
            "debt_ratio": "0.46",
            "operating_margin": "0.12",
            "net_margin": None,
        }
        body = {"rut": RUT, "has_ifrs": True, "latest": ratio_period, "periods": [ratio_period]}
        route = respx_mock.get(f"/entities/{RUT}/financials/ratios").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_ratios(RUT)
        assert out == body
        assert out["latest"]["net_margin"] is None
        assert route.called

    def test_no_ifrs(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {"rut": RUT, "has_ifrs": False, "latest": None, "periods": []}
        respx_mock.get(f"/entities/{RUT}/financials/ratios").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_ratios(RUT)
        assert out["latest"] is None
        assert out["periods"] == []

    def test_propagates_401(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(f"/entities/{RUT}/financials/ratios").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "status": 401})
        )
        resource = FinancialsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_ratios(RUT)
        assert exc.value.status == 401


class TestRatiosAsync:
    async def test_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"rut": RUT, "has_ifrs": True, "latest": None, "periods": []}
        respx_mock.get(f"/entities/{RUT}/financials/ratios").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_ratios(RUT)
        assert out["has_ifrs"] is True


# ---------------------------------------------------------------------------
# get_distress — GET /entities/{rut}/financials/distress
# ---------------------------------------------------------------------------


class TestDistressSync:
    def test_happy_path(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "rut": RUT,
            "has_distress": True,
            "excluded": False,
            "excluded_reason": None,
            "periodo": "202312",
            "tipo_norma": "C",
            "z_score": "3.10",
            "zone": "safe",
            "x1_working_capital_to_ta": "0.21",
            "x2_retained_earnings_to_ta": "0.30",
            "x3_ebit_to_ta": "0.11",
            "x4_equity_to_liabilities": "1.05",
        }
        route = respx_mock.get(f"/entities/{RUT}/financials/distress").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_distress(RUT)
        assert out == body
        assert out["zone"] == "safe"
        assert route.called

    def test_excluded_bank(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "rut": RUT,
            "has_distress": False,
            "excluded": True,
            "excluded_reason": "bank",
            "periodo": None,
            "tipo_norma": None,
            "z_score": None,
            "zone": "excluded",
            "x1_working_capital_to_ta": None,
            "x2_retained_earnings_to_ta": None,
            "x3_ebit_to_ta": None,
            "x4_equity_to_liabilities": None,
        }
        respx_mock.get(f"/entities/{RUT}/financials/distress").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_distress(RUT)
        assert out["excluded"] is True
        assert out["zone"] == "excluded"


class TestDistressAsync:
    async def test_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"rut": RUT, "has_distress": False, "excluded": False, "zone": None}
        respx_mock.get(f"/entities/{RUT}/financials/distress").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_distress(RUT)
        assert out["has_distress"] is False


# ---------------------------------------------------------------------------
# get_benchmark — GET /entities/{rut}/financials/benchmark
# ---------------------------------------------------------------------------


class TestBenchmarkSync:
    def test_happy_path(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "rut": RUT,
            "has_benchmark": True,
            "periodo": "202312",
            "sector_division": "G",
            "sector_label": "Comercio",
            "ratios": [
                {
                    "ratio_name": "current_ratio",
                    "value": "1.42",
                    "percentile": "62.0",
                    "sector": {
                        "ratio_name": "current_ratio",
                        "n_entities": 18,
                        "median": "1.20",
                        "p25": "0.95",
                        "p75": "1.60",
                        "mean": "1.30",
                    },
                }
            ],
        }
        route = respx_mock.get(f"/entities/{RUT}/financials/benchmark").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_benchmark(RUT)
        assert out == body
        assert out["ratios"][0]["sector"]["n_entities"] == 18
        assert route.called

    def test_no_benchmark(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "rut": RUT,
            "has_benchmark": False,
            "periodo": None,
            "sector_division": None,
            "sector_label": None,
            "ratios": [],
        }
        respx_mock.get(f"/entities/{RUT}/financials/benchmark").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_benchmark(RUT)
        assert out["has_benchmark"] is False
        assert out["ratios"] == []


class TestBenchmarkAsync:
    async def test_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"rut": RUT, "has_benchmark": True, "ratios": []}
        respx_mock.get(f"/entities/{RUT}/financials/benchmark").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_benchmark(RUT)
        assert out["has_benchmark"] is True


# ---------------------------------------------------------------------------
# get_timeseries — GET /entities/{rut}/financials/timeseries
# ---------------------------------------------------------------------------


class TestTimeseriesSync:
    def test_happy_path(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        point = {
            "periodo": "202312",
            "tipo_norma": "C",
            "total_assets": "100.0",
            "total_liabilities": "40.0",
            "equity": "60.0",
            "current_assets": "30.0",
            "current_liabilities": "20.0",
            "revenue": "80.0",
            "current_ratio": "1.5",
            "debt_to_equity": "0.66",
        }
        body = {"rut": RUT, "has_ifrs": True, "points": [point]}
        route = respx_mock.get(f"/entities/{RUT}/financials/timeseries").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_timeseries(RUT)
        assert out == body
        assert out["points"][0]["periodo"] == "202312"
        assert route.called

    def test_no_ifrs(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {"rut": RUT, "has_ifrs": False, "points": []}
        respx_mock.get(f"/entities/{RUT}/financials/timeseries").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_timeseries(RUT)
        assert out["points"] == []


class TestTimeseriesAsync:
    async def test_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"rut": RUT, "has_ifrs": True, "points": []}
        respx_mock.get(f"/entities/{RUT}/financials/timeseries").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_timeseries(RUT)
        assert out["has_ifrs"] is True


# ---------------------------------------------------------------------------
# get_distress_histogram — GET /entities/financials/distress/histogram
# ---------------------------------------------------------------------------


class TestDistressHistogramSync:
    def test_default_no_periodo(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "periodo": None,
            "total_scored": 612,
            "suppression_threshold": 5,
            "buckets": [
                {"zone": "safe", "count": 400},
                {"zone": "grey", "count": 150},
                {"zone": "distress", "count": 62},
            ],
        }
        route = respx_mock.get("/entities/financials/distress/histogram").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_distress_histogram()
        assert out == body
        assert route.called
        # No periodo query param should be sent.
        assert "periodo" not in route.calls.last.request.url.params

    def test_with_periodo(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get(
            "/entities/financials/distress/histogram", params={"periodo": "202312"}
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "periodo": "202312",
                    "total_scored": 100,
                    "suppression_threshold": 5,
                    "buckets": [],
                },
            )
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_distress_histogram(periodo="202312")
        assert out["periodo"] == "202312"
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"periodo": "202312"}


class TestDistressHistogramAsync:
    async def test_with_periodo(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/entities/financials/distress/histogram", params={"periodo": "202406"}
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "periodo": "202406",
                    "total_scored": 90,
                    "suppression_threshold": 5,
                    "buckets": [],
                },
            )
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_distress_histogram(periodo="202406")
        assert out["periodo"] == "202406"
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"periodo": "202406"}

    async def test_default_no_periodo(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/financials/distress/histogram").mock(
            return_value=httpx.Response(
                200,
                json={
                    "periodo": None,
                    "total_scored": 0,
                    "suppression_threshold": 5,
                    "buckets": [],
                },
            )
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_distress_histogram()
        assert out["total_scored"] == 0
        assert "periodo" not in route.calls.last.request.url.params


# ---------------------------------------------------------------------------
# get_sector_stats — GET /entities/financials/sector-stats
# ---------------------------------------------------------------------------


class TestSectorStatsSync:
    def test_default_no_periodo(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "periodo": "202312",
            "suppression_threshold": 5,
            "sectors": [
                {
                    "sector_division": "G",
                    "sector_label": "Comercio",
                    "ratios": [
                        {
                            "ratio_name": "current_ratio",
                            "n_entities": 18,
                            "median": "1.20",
                            "p25": "0.95",
                            "p75": "1.60",
                            "mean": "1.30",
                        }
                    ],
                }
            ],
        }
        route = respx_mock.get("/entities/financials/sector-stats").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_sector_stats()
        assert out == body
        assert route.called
        assert "periodo" not in route.calls.last.request.url.params

    def test_with_periodo(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get(
            "/entities/financials/sector-stats", params={"periodo": "202312"}
        ).mock(
            return_value=httpx.Response(
                200,
                json={"periodo": "202312", "suppression_threshold": 5, "sectors": []},
            )
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_sector_stats(periodo="202312")
        assert out["sectors"] == []
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"periodo": "202312"}

    def test_empty_snapshot(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/financials/sector-stats").mock(
            return_value=httpx.Response(
                200,
                json={"periodo": None, "suppression_threshold": 5, "sectors": []},
            )
        )
        resource = FinancialsResource(sync_client)
        out = resource.get_sector_stats()
        assert out["sectors"] == []


class TestSectorStatsAsync:
    async def test_default_no_periodo(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/financials/sector-stats").mock(
            return_value=httpx.Response(
                200,
                json={"periodo": None, "suppression_threshold": 5, "sectors": []},
            )
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_sector_stats()
        assert out["suppression_threshold"] == 5
        assert "periodo" not in route.calls.last.request.url.params

    async def test_with_periodo(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/entities/financials/sector-stats", params={"periodo": "202406"}
        ).mock(
            return_value=httpx.Response(
                200,
                json={"periodo": "202406", "suppression_threshold": 5, "sectors": []},
            )
        )
        resource = AsyncFinancialsResource(async_client)
        out = await resource.get_sector_stats(periodo="202406")
        assert out["periodo"] == "202406"
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"periodo": "202406"}
