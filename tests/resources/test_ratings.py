"""Tests for ``cerberus_compliance.resources.ratings`` (CMF rating surfaces)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, NotFoundError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.ratings import AsyncRatingsResource, RatingsResource


class TestRatingsMeta:
    def test_sync_prefix(self) -> None:
        assert RatingsResource._path_prefix == "/ratings"

    def test_async_prefix(self) -> None:
        assert AsyncRatingsResource._path_prefix == "/ratings"

    def test_sync_subclass(self) -> None:
        assert issubclass(RatingsResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncRatingsResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# GET /entities/{rut}/ratings — anonymous boolean guardrail
# ---------------------------------------------------------------------------


class TestEntityRatingsSync:
    def test_get_entity_ratings(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "rut": "96505760-9",
            "has_rating": True,
            "methodology_url": "https://compliance.cerberus.cl/methodology/ratings",
        }
        route = respx_mock.get("/entities/96505760-9/ratings").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = RatingsResource(sync_client)
        out = resource.get_entity_ratings("96505760-9")
        assert out == body
        assert out["has_rating"] is True
        assert route.called

    def test_get_entity_ratings_percent_encodes_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/..%2Fadmin/ratings").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = RatingsResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get_entity_ratings("../admin")
        assert route.called

    def test_get_entity_ratings_propagates_401(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/96505760-9/ratings").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "status": 401})
        )
        resource = RatingsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_entity_ratings("96505760-9")
        assert exc.value.status == 401


class TestEntityRatingsAsync:
    async def test_get_entity_ratings(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "rut": "96505760-9",
            "has_rating": False,
            "methodology_url": "https://compliance.cerberus.cl/methodology/ratings",
        }
        respx_mock.get("/entities/96505760-9/ratings").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncRatingsResource(async_client)
        out = await resource.get_entity_ratings("96505760-9")
        assert out == body
        assert out["has_rating"] is False

    async def test_get_entity_ratings_percent_encodes_rut(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/..%2Fadmin/ratings").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncRatingsResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.get_entity_ratings("../admin")
        assert route.called


# ---------------------------------------------------------------------------
# GET /entities/{rut}/ratings-timeline — scoped valued history
# ---------------------------------------------------------------------------


class TestEntityRatingsTimelineSync:
    def test_get_timeline(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "rut": "96505760-9",
            "has_ratings": True,
            "entries": [
                {
                    "agency": "Feller Rate",
                    "rating": "AA",
                    "fecha": "2024-03-01",
                    "action": "affirmed",
                    "band": "investment_grade",
                    "outlook": "ESTABLE",
                    "instrument": "BE",
                },
            ],
        }
        route = respx_mock.get("/entities/96505760-9/ratings-timeline").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = RatingsResource(sync_client)
        out = resource.get_entity_ratings_timeline("96505760-9")
        assert out == body
        assert out["entries"][0]["agency"] == "Feller Rate"
        assert route.called

    def test_get_timeline_no_data_is_200(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # No ratings on file -> 200 with has_ratings=false + empty entries (not 404).
        respx_mock.get("/entities/00000000-0/ratings-timeline").mock(
            return_value=httpx.Response(
                200, json={"rut": "00000000-0", "has_ratings": False, "entries": []}
            )
        )
        resource = RatingsResource(sync_client)
        out = resource.get_entity_ratings_timeline("00000000-0")
        assert out["has_ratings"] is False
        assert out["entries"] == []

    def test_get_timeline_percent_encodes_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/..%2Fadmin/ratings-timeline").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = RatingsResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.get_entity_ratings_timeline("../admin")
        assert route.called

    def test_get_timeline_propagates_429(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/96505760-9/ratings-timeline").mock(
            return_value=httpx.Response(429, json={"title": "Too Many Requests", "status": 429})
        )
        resource = RatingsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_entity_ratings_timeline("96505760-9")
        assert exc.value.status == 429


class TestEntityRatingsTimelineAsync:
    async def test_get_timeline(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "rut": "96505760-9",
            "has_ratings": True,
            "entries": [
                {
                    "agency": "ICR",
                    "rating": "A+",
                    "fecha": None,
                    "action": "initial",
                    "band": "investment_grade",
                    "outlook": None,
                    "instrument": None,
                },
            ],
        }
        respx_mock.get("/entities/96505760-9/ratings-timeline").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncRatingsResource(async_client)
        out = await resource.get_entity_ratings_timeline("96505760-9")
        assert out == body
        assert out["entries"][0]["fecha"] is None

    async def test_get_timeline_no_data_is_200(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/00000000-0/ratings-timeline").mock(
            return_value=httpx.Response(
                200, json={"rut": "00000000-0", "has_ratings": False, "entries": []}
            )
        )
        resource = AsyncRatingsResource(async_client)
        out = await resource.get_entity_ratings_timeline("00000000-0")
        assert out["has_ratings"] is False
        assert out["entries"] == []


# ---------------------------------------------------------------------------
# GET /ratings/distribution — anonymised bare-array aggregate
# ---------------------------------------------------------------------------


class TestRatingsDistributionSync:
    def test_distribution_bare_array(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # The endpoint returns a TOP-LEVEL JSON array (no envelope).
        rows = [
            {"bucket": "AA", "count": 42, "pct": 35.0},
            {"bucket": "BBB", "count": 12, "pct": 10.0},
        ]
        route = respx_mock.get("/ratings/distribution").mock(
            return_value=httpx.Response(200, json=rows)
        )
        resource = RatingsResource(sync_client)
        out = resource.get_ratings_distribution()
        assert out == rows
        assert out[0]["bucket"] == "AA"
        assert route.called
        # No tipo -> no query string at all.
        assert route.calls.last.request.url.params.multi_items() == []

    def test_distribution_with_tipo(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ratings/distribution").mock(
            return_value=httpx.Response(200, json=[{"bucket": "A", "count": 1, "pct": 100.0}])
        )
        resource = RatingsResource(sync_client)
        resource.get_ratings_distribution(tipo="instrument")
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"tipo": "instrument"}

    def test_distribution_invalid_tipo_returns_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # An unrecognised tipo yields an empty list (200, []), not an error.
        route = respx_mock.get("/ratings/distribution").mock(
            return_value=httpx.Response(200, json=[])
        )
        resource = RatingsResource(sync_client)
        out = resource.get_ratings_distribution(tipo="insurer")
        assert out == []
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"tipo": "insurer"}

    def test_distribution_propagates_403(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/ratings/distribution").mock(
            return_value=httpx.Response(403, json={"title": "Forbidden", "status": 403})
        )
        resource = RatingsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_ratings_distribution()
        assert exc.value.status == 403


class TestRatingsDistributionAsync:
    async def test_distribution_bare_array(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        rows = [{"bucket": "NIVEL 5", "count": 3, "pct": 5.0}]
        route = respx_mock.get("/ratings/distribution").mock(
            return_value=httpx.Response(200, json=rows)
        )
        resource = AsyncRatingsResource(async_client)
        out = await resource.get_ratings_distribution()
        assert out == rows
        assert route.calls.last.request.url.params.multi_items() == []

    async def test_distribution_with_tipo(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ratings/distribution").mock(
            return_value=httpx.Response(200, json=[])
        )
        resource = AsyncRatingsResource(async_client)
        await resource.get_ratings_distribution(tipo="insurer")
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"tipo": "insurer"}


# ---------------------------------------------------------------------------
# GET /ratings/migration — anonymised churn counts
# ---------------------------------------------------------------------------


class TestRatingsMigrationSync:
    def test_migration_default_period(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "period_days": 365,
            "from_date": "2025-06-07",
            "to_date": "2026-06-07",
            "upgrades": 4,
            "downgrades": 2,
            "affirmations": 9,
            "total_actions": 15,
        }
        route = respx_mock.get("/ratings/migration").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = RatingsResource(sync_client)
        out = resource.get_ratings_migration()
        assert out == body
        assert route.called
        # Default period_days must be forwarded.
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"period_days": "365"}

    def test_migration_custom_period(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ratings/migration").mock(
            return_value=httpx.Response(
                200,
                json={
                    "period_days": 90,
                    "from_date": "2026-03-09",
                    "to_date": "2026-06-07",
                    "upgrades": 0,
                    "downgrades": 0,
                    "affirmations": 1,
                    "total_actions": 1,
                },
            )
        )
        resource = RatingsResource(sync_client)
        resource.get_ratings_migration(period_days=90)
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"period_days": "90"}

    def test_migration_out_of_range_422(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # The server enforces ge=1/le=1825 (real 422); SDK forwards verbatim.
        respx_mock.get("/ratings/migration").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable Entity", "status": 422})
        )
        resource = RatingsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_ratings_migration(period_days=99999)
        assert exc.value.status == 422


class TestRatingsMigrationAsync:
    async def test_migration_default_period(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "period_days": 365,
            "from_date": "2025-06-07",
            "to_date": "2026-06-07",
            "upgrades": 1,
            "downgrades": 1,
            "affirmations": 1,
            "total_actions": 3,
        }
        route = respx_mock.get("/ratings/migration").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncRatingsResource(async_client)
        out = await resource.get_ratings_migration()
        assert out == body
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"period_days": "365"}

    async def test_migration_custom_period(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ratings/migration").mock(
            return_value=httpx.Response(
                200,
                json={
                    "period_days": 1825,
                    "from_date": "2021-06-08",
                    "to_date": "2026-06-07",
                    "upgrades": 10,
                    "downgrades": 5,
                    "affirmations": 20,
                    "total_actions": 35,
                },
            )
        )
        resource = AsyncRatingsResource(async_client)
        await resource.get_ratings_migration(period_days=1825)
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"period_days": "1825"}
