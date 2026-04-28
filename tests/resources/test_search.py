"""Tests for ``cerberus_compliance.resources.search`` (P5.3 — universal semantic search).

Aligned with the live API contract in
``backend/schemas/cmf_public.py::{SearchHit, SearchResponse,
SearchFilters, SearchDateRange}``. The wire schema uses
``source_row_id`` (UUID), ``total_searched`` (int), and a flat
taxonomy filter bag (``tipo_documento``, ``marco_regulatorio``,
``tipo_entidad_target``, ``materias``, ``entity_rut``,
``date_range``).
"""

from __future__ import annotations

import json
from uuid import UUID

import httpx
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources.search import (
    AsyncSearchClient,
    SearchClient,
    SearchDateRange,
    SearchFilters,
    SearchHit,
    SearchResponse,
)

_HIT_1_ID = "11111111-1111-4111-8111-111111111111"
_HIT_2_ID = "22222222-2222-4222-8222-222222222222"

_SAMPLE_RESPONSE = {
    "query": "NCG 461 sostenibilidad",
    "hits": [
        {
            "score": 0.95,
            "source_table": "cmf_normativa",
            "source_row_id": _HIT_1_ID,
            "tipo_documento": "normativa",
            "marco_regulatorio": ["ncg_461"],
            "tipo_entidad_target": ["emisor"],
            "materias": ["esg", "gobierno_corporativo"],
            "entity_rut": None,
            "publicacion_at": "2024-06-01T15:00:00Z",
            "payload": {"ncg_number": 461},
        },
        {
            "score": 0.88,
            "source_table": "cmf_comunicaciones",
            "source_row_id": _HIT_2_ID,
            "tipo_documento": "comunicacion",
            "marco_regulatorio": [],
            "tipo_entidad_target": [],
            "materias": [],
            "payload": {},
        },
    ],
    "total_searched": 1234,
}


# ---------------------------------------------------------------------------
# SearchDateRange — alias semantics
# ---------------------------------------------------------------------------


class TestSearchDateRange:
    def test_from_alias_round_trips_to_wire(self) -> None:
        """``from_`` Python attribute serialises to the wire field ``from``."""
        dr = SearchDateRange(from_="2024-01-01", to="2024-12-31")
        wire = dr.model_dump(by_alias=True, exclude_none=True, mode="json")
        assert wire == {"from": "2024-01-01", "to": "2024-12-31"}

    def test_partial_range(self) -> None:
        dr = SearchDateRange(from_="2024-01-01")
        wire = dr.model_dump(by_alias=True, exclude_none=True, mode="json")
        assert wire == {"from": "2024-01-01"}


# ---------------------------------------------------------------------------
# SearchFilters
# ---------------------------------------------------------------------------


class TestSearchFilters:
    def test_to_api_dict_drops_none(self) -> None:
        f = SearchFilters(tipo_documento=["normativa"])
        assert f.to_api_dict() == {"tipo_documento": ["normativa"]}

    def test_to_api_dict_all_fields(self) -> None:
        f = SearchFilters(
            tipo_documento=["normativa", "comunicacion"],
            marco_regulatorio=["ncg_461"],
            tipo_entidad_target=["emisor"],
            materias=["esg"],
            entity_rut="96.505.760-9",
            date_range=SearchDateRange(from_="2024-01-01", to="2024-12-31"),
        )
        d = f.to_api_dict()
        assert d["tipo_documento"] == ["normativa", "comunicacion"]
        assert d["marco_regulatorio"] == ["ncg_461"]
        assert d["tipo_entidad_target"] == ["emisor"]
        assert d["materias"] == ["esg"]
        assert d["entity_rut"] == "96.505.760-9"
        assert d["date_range"] == {"from": "2024-01-01", "to": "2024-12-31"}

    def test_empty_filters_to_api_dict(self) -> None:
        f = SearchFilters()
        assert f.to_api_dict() == {}

    def test_empty_date_range_dropped(self) -> None:
        """A ``SearchDateRange`` with no fields set must not surface an empty
        ``date_range`` key on the wire (it would be a no-op the server still
        has to parse).
        """
        f = SearchFilters(date_range=SearchDateRange())
        assert f.to_api_dict() == {}


# ---------------------------------------------------------------------------
# SearchHit / SearchResponse
# ---------------------------------------------------------------------------


class TestSearchHit:
    def test_hit_with_full_payload(self) -> None:
        hit = SearchHit.model_validate(_SAMPLE_RESPONSE["hits"][0])
        assert hit.score == 0.95
        assert hit.source_table == "cmf_normativa"
        assert hit.source_row_id == UUID(_HIT_1_ID)
        assert hit.tipo_documento == "normativa"
        assert hit.marco_regulatorio == ["ncg_461"]
        assert hit.payload == {"ncg_number": 461}

    def test_hit_with_minimal_payload_uses_defaults(self) -> None:
        hit = SearchHit.model_validate(_SAMPLE_RESPONSE["hits"][1])
        assert hit.entity_rut is None
        assert hit.publicacion_at is None
        assert hit.marco_regulatorio == []
        assert hit.payload == {}


class TestSearchResponse:
    def test_parses_sample_response(self) -> None:
        resp = SearchResponse.model_validate(_SAMPLE_RESPONSE)
        assert resp.query == "NCG 461 sostenibilidad"
        assert len(resp.hits) == 2
        assert resp.total_searched == 1234
        assert resp.hits[0].score == 0.95
        assert resp.hits[1].source_table == "cmf_comunicaciones"

    def test_empty_response(self) -> None:
        resp = SearchResponse.model_validate(
            {"query": "x", "hits": [], "total_searched": 0}
        )
        assert resp.hits == []
        assert resp.total_searched == 0


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------


class TestSearchClientSync:
    def test_search_basic(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.post("/search").mock(
            return_value=httpx.Response(200, json=_SAMPLE_RESPONSE)
        )
        sc = SearchClient(sync_client)
        result = sc.search(query="NCG 461 sostenibilidad")
        assert isinstance(result, SearchResponse)
        assert len(result.hits) == 2
        assert result.hits[0].source_row_id == UUID(_HIT_1_ID)
        assert route.called

    def test_search_with_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/search").mock(
            return_value=httpx.Response(
                200,
                json={"query": "test", "hits": [], "total_searched": 0},
            )
        )
        sc = SearchClient(sync_client)
        filters = SearchFilters(
            tipo_documento=["normativa", "comunicacion"],
            date_range=SearchDateRange(from_="2024-01-01"),
        )
        result = sc.search(query="test", filters=filters, top_k=5)
        assert result.total_searched == 0
        assert route.called

        body = json.loads(route.calls.last.request.content)
        assert body["filters"]["tipo_documento"] == ["normativa", "comunicacion"]
        assert body["filters"]["date_range"] == {"from": "2024-01-01"}
        assert body["top_k"] == 5

    def test_search_empty_filters_not_included(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Empty ``SearchFilters`` (all None) must not add a ``filters`` key to the body."""
        route = respx_mock.post("/search").mock(
            return_value=httpx.Response(
                200, json={"query": "q", "hits": [], "total_searched": 0}
            )
        )
        sc = SearchClient(sync_client)
        sc.search(query="q", filters=SearchFilters())
        assert route.called
        body = json.loads(route.calls.last.request.content)
        assert "filters" not in body

    def test_search_top_k_forwarded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/search").mock(
            return_value=httpx.Response(
                200, json={"query": "q", "hits": [], "total_searched": 0}
            )
        )
        sc = SearchClient(sync_client)
        sc.search(query="q", top_k=25)
        body = json.loads(route.calls.last.request.content)
        assert body["top_k"] == 25

    def test_search_returns_typed_hits(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/search").mock(return_value=httpx.Response(200, json=_SAMPLE_RESPONSE))
        sc = SearchClient(sync_client)
        result = sc.search(query="NCG 461 sostenibilidad")
        for hit in result.hits:
            assert isinstance(hit, SearchHit)
            assert isinstance(hit.score, float)
            assert isinstance(hit.source_row_id, UUID)


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------


class TestSearchClientAsync:
    async def test_search_basic(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/search").mock(return_value=httpx.Response(200, json=_SAMPLE_RESPONSE))
        sc = AsyncSearchClient(async_client)
        result = await sc.search(query="NCG 461 sostenibilidad")
        assert isinstance(result, SearchResponse)
        assert len(result.hits) == 2

    async def test_search_with_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/search").mock(
            return_value=httpx.Response(
                200, json={"query": "x", "hits": [], "total_searched": 0}
            )
        )
        sc = AsyncSearchClient(async_client)
        result = await sc.search(
            query="x",
            filters=SearchFilters(tipo_documento=["art20_participacion"], entity_rut="96.505.760-9"),
            top_k=3,
        )
        assert result.total_searched == 0

    async def test_search_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/search").mock(
            return_value=httpx.Response(
                200, json={"query": "y", "hits": [], "total_searched": 0}
            )
        )
        sc = AsyncSearchClient(async_client)
        result = await sc.search(query="y")
        assert isinstance(result, SearchResponse)
