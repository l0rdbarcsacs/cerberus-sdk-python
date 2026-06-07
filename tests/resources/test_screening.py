"""Tests for ``cerberus_compliance.resources.screening`` (sanction-contagion)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, ValidationError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.screening import (
    AsyncScreeningResource,
    ScreeningResource,
)

# Representative exposure payload reused across happy-path assertions.
_EXPOSURE_BODY = {
    "rut": "96505760-9",
    "node_type": "company",
    "has_exposure": True,
    "exposure_score": 14.0,
    "connected_sanctioned": [
        {
            "node_type": "person",
            "rut": "12345678-5",
            "name": "Persona Sancionada",
            "sanction_source": "cmf_persona",
            "sanction_detail": None,
            "hop_distance": 1,
            "relationship_path": ["DIRECTS"],
            "node_exposure_score": 10.0,
        },
    ],
}

_DISTRIBUTION_BODY = {
    "total_scored": 1234,
    "suppression_threshold": 5,
    "buckets": [
        {"bucket": "none", "count": 900},
        {"bucket": "low", "count": 280},
        {"bucket": "medium", "count": 54},
    ],
}


class TestScreeningMeta:
    def test_sync_prefix(self) -> None:
        assert ScreeningResource._path_prefix == "/screening"

    def test_async_prefix(self) -> None:
        assert AsyncScreeningResource._path_prefix == "/screening"

    def test_sync_subclass(self) -> None:
        assert issubclass(ScreeningResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncScreeningResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# get_exposure — GET /screening/{rut}/exposure
# ---------------------------------------------------------------------------


class TestScreeningExposureSync:
    def test_get_exposure_happy_path(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/screening/96505760-9/exposure").mock(
            return_value=httpx.Response(200, json=_EXPOSURE_BODY)
        )
        resource = ScreeningResource(sync_client)
        out = resource.get_exposure("96505760-9")
        assert out == _EXPOSURE_BODY
        assert out["has_exposure"] is True
        assert out["connected_sanctioned"][0]["sanction_source"] == "cmf_persona"
        assert route.called

    def test_get_exposure_no_exposure_is_200(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "rut": "76000000-0",
            "node_type": None,
            "has_exposure": False,
            "exposure_score": 0.0,
            "connected_sanctioned": [],
        }
        respx_mock.get("/screening/76000000-0/exposure").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = ScreeningResource(sync_client)
        out = resource.get_exposure("76000000-0")
        assert out["has_exposure"] is False
        assert out["node_type"] is None
        assert out["connected_sanctioned"] == []

    def test_get_exposure_percent_encodes_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/screening/..%2Fadmin/exposure").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = ScreeningResource(sync_client)
        with pytest.raises(ValidationError):
            resource.get_exposure("../admin")
        assert route.called

    def test_get_exposure_invalid_rut_raises_422(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/screening/not-a-rut/exposure").mock(
            return_value=httpx.Response(
                422,
                json={"title": "Unprocessable Entity", "status": 422, "detail": "Invalid RUT: ..."},
            )
        )
        resource = ScreeningResource(sync_client)
        with pytest.raises(ValidationError) as exc:
            resource.get_exposure("not-a-rut")
        assert exc.value.status == 422

    def test_get_exposure_propagates_401(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/screening/96505760-9/exposure").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "status": 401})
        )
        resource = ScreeningResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_exposure("96505760-9")
        assert exc.value.status == 401


class TestScreeningExposureAsync:
    async def test_get_exposure_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/screening/96505760-9/exposure").mock(
            return_value=httpx.Response(200, json=_EXPOSURE_BODY)
        )
        resource = AsyncScreeningResource(async_client)
        out = await resource.get_exposure("96505760-9")
        assert out == _EXPOSURE_BODY
        assert route.called

    async def test_get_exposure_invalid_rut_raises_422(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/screening/not-a-rut/exposure").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = AsyncScreeningResource(async_client)
        with pytest.raises(ValidationError):
            await resource.get_exposure("not-a-rut")


# ---------------------------------------------------------------------------
# get_exposure_distribution — GET /screening/exposure/distribution
# ---------------------------------------------------------------------------


class TestScreeningDistributionSync:
    def test_distribution_happy_path(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/screening/exposure/distribution").mock(
            return_value=httpx.Response(200, json=_DISTRIBUTION_BODY)
        )
        resource = ScreeningResource(sync_client)
        out = resource.get_exposure_distribution()
        assert out == _DISTRIBUTION_BODY
        assert out["total_scored"] == 1234
        assert out["suppression_threshold"] == 5
        assert len(out["buckets"]) == 3
        assert route.called
        # No query params on the wire.
        assert dict(route.calls.last.request.url.params.multi_items()) == {}

    def test_distribution_propagates_401(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/screening/exposure/distribution").mock(
            return_value=httpx.Response(401, json={"title": "Unauthorized", "status": 401})
        )
        resource = ScreeningResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_exposure_distribution()
        assert exc.value.status == 401


class TestScreeningDistributionAsync:
    async def test_distribution_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/screening/exposure/distribution").mock(
            return_value=httpx.Response(200, json=_DISTRIBUTION_BODY)
        )
        resource = AsyncScreeningResource(async_client)
        out = await resource.get_exposure_distribution()
        assert out == _DISTRIBUTION_BODY
        assert route.called

    async def test_distribution_propagates_429(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/screening/exposure/distribution").mock(
            return_value=httpx.Response(429, json={"title": "Too Many Requests", "status": 429})
        )
        resource = AsyncScreeningResource(async_client)
        with pytest.raises(CerberusAPIError) as exc:
            await resource.get_exposure_distribution()
        assert exc.value.status == 429
