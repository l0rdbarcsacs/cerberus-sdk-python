"""TDD tests for ``cerberus_compliance.resources.norms``.

The ``norms`` resource exposes the public citation graph over Chilean CMF
norms: ``GET /norms/top-cited`` (the most-cited norms, ranked) and
``GET /norms/{regulation_id}/citations`` (the resolved citing rows for a
single norm). Both are counts-only aggregates (no PII per Ley 21.719) and
return a plain envelope ``dict`` — neither is cursor-paginated, so there
is no ``iter_all``. Both require the ``regulations:read`` scope.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.norms import (
    AsyncNormsResource,
    NormsResource,
)

_TOP_CITED_BODY: dict[str, Any] = {
    "norms": [
        {
            "regulation_id": "11111111-1111-1111-1111-111111111111",
            "type": "ncg",
            "title": "NCG 30",
            "ncg_number": 30,
            "circular_number": None,
            "citation_count": 42,
        },
        {
            "regulation_id": "22222222-2222-2222-2222-222222222222",
            "type": "circular",
            "title": "Circular 1234",
            "ncg_number": None,
            "circular_number": 1234,
            "citation_count": 17,
        },
    ],
    "total": 2,
}

_CITATIONS_BODY: dict[str, Any] = {
    "regulation_id": "11111111-1111-1111-1111-111111111111",
    "ncg_number": 30,
    "circular_number": None,
    "citations": [
        {
            "source_table": "cmf_dictamenes",
            "source_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "raw_citation": "NCG N° 30",
            "citation_kind": "ncg",
            "citation_number": 30,
        },
        {
            "source_table": "cmf_sanciones",
            "source_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "raw_citation": "Norma de Carácter General 30",
            "citation_kind": "ncg",
            "citation_number": 30,
        },
    ],
    "total": 2,
}


# ---------------------------------------------------------------------------
# Meta / typing sanity
# ---------------------------------------------------------------------------


class TestNormsResourceMeta:
    def test_sync_path_prefix(self) -> None:
        assert NormsResource._path_prefix == "/norms"

    def test_async_path_prefix(self) -> None:
        assert AsyncNormsResource._path_prefix == "/norms"

    def test_sync_subclass_of_base(self) -> None:
        assert issubclass(NormsResource, BaseResource)

    def test_async_subclass_of_base(self) -> None:
        assert issubclass(AsyncNormsResource, AsyncBaseResource)

    def test_sync_constructor_binds_client(self, sync_client: CerberusClient) -> None:
        resource = NormsResource(sync_client)
        assert resource._client is sync_client

    def test_async_constructor_binds_client(self, async_client: AsyncCerberusClient) -> None:
        resource = AsyncNormsResource(async_client)
        assert resource._client is async_client


# ---------------------------------------------------------------------------
# Sync — top_cited
# ---------------------------------------------------------------------------


class TestNormsTopCited:
    def test_top_cited_no_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/norms/top-cited").mock(
            return_value=httpx.Response(200, json=_TOP_CITED_BODY)
        )
        resource = NormsResource(sync_client)
        body = resource.top_cited()
        assert body == _TOP_CITED_BODY
        assert body["total"] == 2
        assert body["norms"][0]["citation_count"] == 42
        assert route.called
        # `limit` must NOT be sent when None.
        assert "limit" not in route.calls.last.request.url.params

    def test_top_cited_forwards_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/norms/top-cited", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json=_TOP_CITED_BODY)
        )
        resource = NormsResource(sync_client)
        body = resource.top_cited(limit=10)
        assert body == _TOP_CITED_BODY
        assert route.called
        assert route.calls.last.request.url.params.get("limit") == "10"

    def test_top_cited_422_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/norms/top-cited", params={"limit": "9999"}).mock(
            return_value=httpx.Response(
                422,
                json=problem_json(
                    status=422,
                    title="Unprocessable Entity",
                    detail="limit must be <= 100",
                ),
                headers={"Content-Type": "application/problem+json"},
            )
        )
        resource = NormsResource(sync_client)
        with pytest.raises(CerberusAPIError) as excinfo:
            resource.top_cited(limit=9999)
        assert excinfo.value.status == 422


# ---------------------------------------------------------------------------
# Sync — citations
# ---------------------------------------------------------------------------


class TestNormsCitations:
    def test_citations_no_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/norms/11111111-1111-1111-1111-111111111111/citations").mock(
            return_value=httpx.Response(200, json=_CITATIONS_BODY)
        )
        resource = NormsResource(sync_client)
        body = resource.citations("11111111-1111-1111-1111-111111111111")
        assert body == _CITATIONS_BODY
        assert body["total"] == 2
        assert body["citations"][0]["source_table"] == "cmf_dictamenes"
        assert route.called
        assert "limit" not in route.calls.last.request.url.params

    def test_citations_forwards_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/norms/11111111-1111-1111-1111-111111111111/citations",
            params={"limit": "200"},
        ).mock(return_value=httpx.Response(200, json=_CITATIONS_BODY))
        resource = NormsResource(sync_client)
        body = resource.citations("11111111-1111-1111-1111-111111111111", limit=200)
        assert body == _CITATIONS_BODY
        assert route.called
        assert route.calls.last.request.url.params.get("limit") == "200"

    def test_citations_empty_list(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        empty = {
            "regulation_id": "33333333-3333-3333-3333-333333333333",
            "ncg_number": None,
            "circular_number": None,
            "citations": [],
            "total": 0,
        }
        respx_mock.get("/norms/33333333-3333-3333-3333-333333333333/citations").mock(
            return_value=httpx.Response(200, json=empty)
        )
        resource = NormsResource(sync_client)
        body = resource.citations("33333333-3333-3333-3333-333333333333")
        assert body == empty
        assert body["citations"] == []
        assert body["total"] == 0

    def test_citations_percent_encodes_path(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A path-traversal attempt must be encoded into a single segment.
        route = respx_mock.get("/norms/..%2Fadmin/citations").mock(
            return_value=httpx.Response(200, json=_CITATIONS_BODY)
        )
        resource = NormsResource(sync_client)
        body = resource.citations("../admin")
        assert body == _CITATIONS_BODY
        assert route.called
        assert route.calls.last.request.url.raw_path.startswith(b"/v1/norms/..%2Fadmin/citations")

    def test_citations_404_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/norms/44444444-4444-4444-4444-444444444444/citations").mock(
            return_value=httpx.Response(
                404,
                json=problem_json(
                    status=404,
                    title="Not Found",
                    detail="Regulation '44444444-...' not found",
                ),
                headers={"Content-Type": "application/problem+json"},
            )
        )
        resource = NormsResource(sync_client)
        with pytest.raises(CerberusAPIError) as excinfo:
            resource.citations("44444444-4444-4444-4444-444444444444")
        assert excinfo.value.status == 404


# ---------------------------------------------------------------------------
# Async — top_cited
# ---------------------------------------------------------------------------


class TestAsyncNormsTopCited:
    async def test_top_cited_no_limit(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/norms/top-cited").mock(
            return_value=httpx.Response(200, json=_TOP_CITED_BODY)
        )
        resource = AsyncNormsResource(async_client)
        body = await resource.top_cited()
        assert body == _TOP_CITED_BODY
        assert route.called
        assert "limit" not in route.calls.last.request.url.params

    async def test_top_cited_forwards_limit(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/norms/top-cited", params={"limit": "5"}).mock(
            return_value=httpx.Response(200, json=_TOP_CITED_BODY)
        )
        resource = AsyncNormsResource(async_client)
        body = await resource.top_cited(limit=5)
        assert body == _TOP_CITED_BODY
        assert route.called
        assert route.calls.last.request.url.params.get("limit") == "5"

    async def test_top_cited_422_raises(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/norms/top-cited", params={"limit": "0"}).mock(
            return_value=httpx.Response(
                422,
                json=problem_json(
                    status=422,
                    title="Unprocessable Entity",
                    detail="limit must be >= 1",
                ),
                headers={"Content-Type": "application/problem+json"},
            )
        )
        resource = AsyncNormsResource(async_client)
        with pytest.raises(CerberusAPIError) as excinfo:
            await resource.top_cited(limit=0)
        assert excinfo.value.status == 422


# ---------------------------------------------------------------------------
# Async — citations
# ---------------------------------------------------------------------------


class TestAsyncNormsCitations:
    async def test_citations_no_limit(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/norms/11111111-1111-1111-1111-111111111111/citations").mock(
            return_value=httpx.Response(200, json=_CITATIONS_BODY)
        )
        resource = AsyncNormsResource(async_client)
        body = await resource.citations("11111111-1111-1111-1111-111111111111")
        assert body == _CITATIONS_BODY
        assert route.called
        assert "limit" not in route.calls.last.request.url.params

    async def test_citations_forwards_limit(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/norms/11111111-1111-1111-1111-111111111111/citations",
            params={"limit": "500"},
        ).mock(return_value=httpx.Response(200, json=_CITATIONS_BODY))
        resource = AsyncNormsResource(async_client)
        body = await resource.citations("11111111-1111-1111-1111-111111111111", limit=500)
        assert body == _CITATIONS_BODY
        assert route.called
        assert route.calls.last.request.url.params.get("limit") == "500"

    async def test_citations_404_raises(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/norms/44444444-4444-4444-4444-444444444444/citations").mock(
            return_value=httpx.Response(
                404,
                json=problem_json(
                    status=404,
                    title="Not Found",
                    detail="Regulation not found",
                ),
                headers={"Content-Type": "application/problem+json"},
            )
        )
        resource = AsyncNormsResource(async_client)
        with pytest.raises(CerberusAPIError) as excinfo:
            await resource.citations("44444444-4444-4444-4444-444444444444")
        assert excinfo.value.status == 404
