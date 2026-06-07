"""Tests for ``cerberus_compliance.resources.insider`` (Art.12 — Ley 18.045)."""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.insider import (
    AsyncInsiderResource,
    InsiderResource,
)


def _persona_profile() -> dict[str, object]:
    """A minimal ``subject_type='persona'`` (insider) payload."""
    return {
        "query_rut": "12345678-5",
        "subject_type": "persona",
        "nombre": "Juan Pérez",
        "has_activity": True,
        "total_transactions": 3,
        "total_monto_clp": "1500000.00",
        "total_monto_uf": "40.5",
        "distinct_emisor_count": 1,
        "emisores": [
            {
                "emisor_rut": "96505760-9",
                "emisor_nombre": "Falabella SA",
                "transaction_count": 3,
                "total_monto_clp": "1500000.00",
                "total_monto_uf": "40.5",
                "first_fecha": "2024-01-10",
                "last_fecha": "2024-03-22",
                "by_instrumento": [
                    {
                        "instrumento": "FALABELLA",
                        "transaction_count": 3,
                        "total_monto_clp": "1500000.00",
                        "total_monto_uf": "40.5",
                    }
                ],
                "by_tipo_operacion": [
                    {
                        "tipo_operacion": "compra",
                        "transaction_count": 3,
                        "total_monto_clp": "1500000.00",
                        "total_monto_uf": "40.5",
                    }
                ],
            }
        ],
        "distinct_insider_count": 0,
        "insiders": [],
        "disclaimer": "Actividad Art.12 — uso informativo.",
    }


def _emisor_profile() -> dict[str, object]:
    """A minimal ``subject_type='emisor'`` (issuer) payload."""
    return {
        "query_rut": "96505760-9",
        "subject_type": "emisor",
        "nombre": "Falabella SA",
        "has_activity": True,
        "total_transactions": 5,
        "total_monto_clp": "9000000.00",
        "total_monto_uf": None,
        "distinct_emisor_count": 0,
        "emisores": [],
        "distinct_insider_count": 1,
        "insiders": [
            {
                "persona_rut": "12345678-5",
                "persona_nombre": "Juan Pérez",
                "transaction_count": 5,
                "total_monto_clp": "9000000.00",
                "total_monto_uf": None,
                "first_fecha": "2024-01-10",
                "last_fecha": "2024-05-01",
            }
        ],
        "disclaimer": "Actividad Art.12 — uso informativo.",
    }


def _unknown_profile() -> dict[str, object]:
    """A well-formed RUT with no Art.12 activity (HTTP 200)."""
    return {
        "query_rut": "11111111-1",
        "subject_type": "unknown",
        "nombre": None,
        "has_activity": False,
        "total_transactions": 0,
        "total_monto_clp": None,
        "total_monto_uf": None,
        "distinct_emisor_count": 0,
        "emisores": [],
        "distinct_insider_count": 0,
        "insiders": [],
        "disclaimer": "Actividad Art.12 — uso informativo.",
    }


class TestInsiderMeta:
    def test_sync_prefix(self) -> None:
        assert InsiderResource._path_prefix == "/insider"

    def test_async_prefix(self) -> None:
        assert AsyncInsiderResource._path_prefix == "/insider"

    def test_sync_subclass(self) -> None:
        assert issubclass(InsiderResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncInsiderResource, AsyncBaseResource)


class TestInsiderSync:
    def test_get_profile_persona(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = _persona_profile()
        route = respx_mock.get("/insider/12345678-5/profile").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = InsiderResource(sync_client)
        result = resource.get_profile("12345678-5")
        assert result == body
        assert result["subject_type"] == "persona"
        assert result["emisores"][0]["emisor_rut"] == "96505760-9"
        assert result["insiders"] == []
        assert "disclaimer" in result
        assert route.called

    def test_get_profile_emisor(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = _emisor_profile()
        route = respx_mock.get("/insider/96505760-9/profile").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = InsiderResource(sync_client)
        result = resource.get_profile("96505760-9")
        assert result["subject_type"] == "emisor"
        assert result["emisores"] == []
        assert result["insiders"][0]["persona_rut"] == "12345678-5"
        assert route.called

    def test_get_profile_unknown_is_200_not_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = _unknown_profile()
        route = respx_mock.get("/insider/11111111-1/profile").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = InsiderResource(sync_client)
        result = resource.get_profile("11111111-1")
        assert result["has_activity"] is False
        assert result["subject_type"] == "unknown"
        assert result["total_transactions"] == 0
        assert route.called

    def test_get_profile_accepts_dotted_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A dotted RUT contains '.' which is path-safe but the '-' and digits
        # must reach the server verbatim; the segment is percent-encoded.
        route = respx_mock.get("/insider/12.345.678-5/profile").mock(
            return_value=httpx.Response(200, json=_persona_profile())
        )
        resource = InsiderResource(sync_client)
        resource.get_profile("12.345.678-5")
        assert route.called

    def test_get_profile_percent_encodes_segment(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/insider/..%2Fadmin/profile").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = InsiderResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_profile("../admin")
        assert exc.value.status == 422
        assert route.called

    def test_get_profile_non_parseable_rut_422(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/insider/not-a-rut/profile").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable Entity", "status": 422})
        )
        resource = InsiderResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_profile("not-a-rut")
        assert exc.value.status == 422

    def test_get_profile_propagates_403(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/insider/12345678-5/profile").mock(
            return_value=httpx.Response(403, json={"title": "Forbidden", "status": 403})
        )
        resource = InsiderResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get_profile("12345678-5")
        assert exc.value.status == 403


class TestInsiderAsync:
    async def test_get_profile_persona(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = _persona_profile()
        route = respx_mock.get("/insider/12345678-5/profile").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncInsiderResource(async_client)
        result = await resource.get_profile("12345678-5")
        assert result == body
        assert result["subject_type"] == "persona"
        assert route.called

    async def test_get_profile_unknown_is_200(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/insider/11111111-1/profile").mock(
            return_value=httpx.Response(200, json=_unknown_profile())
        )
        resource = AsyncInsiderResource(async_client)
        result = await resource.get_profile("11111111-1")
        assert result["has_activity"] is False
        assert result["subject_type"] == "unknown"
        assert route.called

    async def test_get_profile_percent_encodes_segment(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/insider/..%2Fadmin/profile").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = AsyncInsiderResource(async_client)
        with pytest.raises(CerberusAPIError) as exc:
            await resource.get_profile("../admin")
        assert exc.value.status == 422
        assert route.called

    async def test_get_profile_propagates_422(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/insider/not-a-rut/profile").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable Entity", "status": 422})
        )
        resource = AsyncInsiderResource(async_client)
        with pytest.raises(CerberusAPIError) as exc:
            await resource.get_profile("not-a-rut")
        assert exc.value.status == 422
