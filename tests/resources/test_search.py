"""Tests for ``cerberus_compliance.resources.search`` (P5.3 — universal semantic search)."""

from __future__ import annotations

import httpx
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources.search import (
    AsyncSearchClient,
    SearchClient,
    SearchFilters,
    SearchHit,
    SearchResponse,
)

_SAMPLE_RESPONSE = {
    "query": "NCG 461 sostenibilidad",
    "hits": [
        {
            "id": "doc-001",
            "score": 0.95,
            "doc_type": "normativa",
            "title": "NCG 461 — Sostenibilidad",
            "snippet": "Norma de caracter general...",
            "metadata": {"year": 2023},
        },
        {
            "id": "doc-002",
            "score": 0.88,
            "doc_type": "comunicaciones",
            "title": "Comunicado NCG 461",
            "snippet": None,
            "metadata": {},
        },
    ],
    "total": 2,
}


class TestSearchFilters:
    def test_to_api_dict_drops_none(self) -> None:
        f = SearchFilters(doc_types=["normativa"], from_date=None, to_date=None)
        assert f.to_api_dict() == {"doc_types": ["normativa"]}

    def test_to_api_dict_all_fields(self) -> None:
        f = SearchFilters(
            doc_types=["normativa", "comunicaciones"],
            from_date="2024-01-01",
            to_date="2024-12-31",
            entity_rut="96505760-9",
        )
        d = f.to_api_dict()
        assert d["doc_types"] == ["normativa", "comunicaciones"]
        assert d["from_date"] == "2024-01-01"
        assert d["to_date"] == "2024-12-31"
        assert d["entity_rut"] == "96505760-9"

    def test_empty_filters_to_api_dict(self) -> None:
        f = SearchFilters()
        assert f.to_api_dict() == {}


class TestSearchHit:
    def test_hit_with_snippet(self) -> None:
        hit = SearchHit(id="x", score=0.9, doc_type="normativa", title="T", snippet="S")
        assert hit.id == "x"
        assert hit.score == 0.9
        assert hit.snippet == "S"

    def test_hit_without_optional_fields(self) -> None:
        hit = SearchHit(id="y", score=0.5, doc_type="opas")
        assert hit.title is None
        assert hit.snippet is None
        assert hit.metadata == {}


class TestSearchResponse:
    def test_parses_sample_response(self) -> None:
        resp = SearchResponse.model_validate(_SAMPLE_RESPONSE)
        assert resp.query == "NCG 461 sostenibilidad"
        assert len(resp.hits) == 2
        assert resp.total == 2
        assert resp.hits[0].score == 0.95
        assert resp.hits[0].doc_type == "normativa"
        assert resp.hits[1].title == "Comunicado NCG 461"

    def test_empty_response(self) -> None:
        resp = SearchResponse.model_validate({"query": "x", "hits": [], "total": 0})
        assert resp.hits == []
        assert resp.total == 0


class TestSearchClientSync:
    def test_search_basic(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.post("/search").mock(
            return_value=httpx.Response(200, json=_SAMPLE_RESPONSE)
        )
        sc = SearchClient(sync_client)
        result = sc.search(query="NCG 461 sostenibilidad")
        assert isinstance(result, SearchResponse)
        assert len(result.hits) == 2
        assert result.hits[0].id == "doc-001"
        assert route.called

    def test_search_with_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/search").mock(
            return_value=httpx.Response(
                200,
                json={"query": "test", "hits": [], "total": 0},
            )
        )
        sc = SearchClient(sync_client)
        filters = SearchFilters(
            doc_types=["normativa", "comunicaciones"],
            from_date="2024-01-01",
        )
        result = sc.search(query="test", filters=filters, top_k=5)
        assert result.total == 0
        assert route.called

    def test_search_empty_filters_not_included(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """Empty SearchFilters (all None) should not add a ``filters`` key to the body."""
        route = respx_mock.post("/search").mock(
            return_value=httpx.Response(200, json={"query": "q", "hits": [], "total": 0})
        )
        sc = SearchClient(sync_client)
        sc.search(query="q", filters=SearchFilters())
        assert route.called
        # The request body should not contain "filters" since all fields are None
        request_body = route.calls.last.request
        import json

        body = json.loads(request_body.content)
        assert "filters" not in body

    def test_search_top_k_forwarded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/search").mock(
            return_value=httpx.Response(200, json={"query": "q", "hits": [], "total": 0})
        )
        sc = SearchClient(sync_client)
        sc.search(query="q", top_k=25)
        import json

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
            assert isinstance(hit.doc_type, str)


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
            return_value=httpx.Response(200, json={"query": "x", "hits": [], "total": 0})
        )
        sc = AsyncSearchClient(async_client)
        result = await sc.search(
            query="x",
            filters=SearchFilters(doc_types=["art20"], entity_rut="96505760-9"),
            top_k=3,
        )
        assert result.total == 0

    async def test_search_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/search").mock(
            return_value=httpx.Response(200, json={"query": "y", "hits": [], "total": 0})
        )
        sc = AsyncSearchClient(async_client)
        result = await sc.search(query="y")
        assert isinstance(result, SearchResponse)
