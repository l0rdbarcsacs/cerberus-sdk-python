"""Tests for ``cerberus_compliance.resources.sasb_topics`` (P5.4.2)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.sasb_topics import (
    AsyncSasbTopicsResource,
    SasbTopicsResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestSasbTopicsMeta:
    def test_sync_prefix(self) -> None:
        assert SasbTopicsResource._path_prefix == "/sasb-topics"

    def test_async_prefix(self) -> None:
        assert AsyncSasbTopicsResource._path_prefix == "/sasb-topics"

    def test_sync_subclass(self) -> None:
        assert issubclass(SasbTopicsResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncSasbTopicsResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestSasbTopicsSync:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "topics": [
                {"topic_code": "EM-CM-110a.1", "topic_name": "GHG Emissions"},
                {"topic_code": "EM-CM-110a.2", "topic_name": "Air Quality"},
            ],
            "total": 2,
        }
        route = respx_mock.get("/sasb-topics").mock(return_value=httpx.Response(200, json=body))
        resource = SasbTopicsResource(sync_client)
        result = resource.list()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_with_industry(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sasb-topics", params={"industry": "EM-CM"}).mock(
            return_value=httpx.Response(200, json={"topics": [], "total": 0})
        )
        resource = SasbTopicsResource(sync_client)
        result = resource.list(industry="EM-CM")
        assert result == {"topics": [], "total": 0}
        assert route.called

    def test_list_with_limit_and_offset(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sasb-topics", params={"limit": "5", "offset": "10"}).mock(
            return_value=httpx.Response(200, json={"topics": [], "total": 0})
        )
        resource = SasbTopicsResource(sync_client)
        resource.list(limit=5, offset=10)
        assert route.called

    def test_list_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sasb-topics").mock(
            return_value=httpx.Response(200, json={"topics": [], "total": 0})
        )
        resource = SasbTopicsResource(sync_client)
        resource.list(industry=None, limit=None, offset=None)
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_iter_all_single_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # One page, fewer items than the SDK's page size (100) — must stop
        # after the first request without issuing a second.
        route = respx_mock.get("/sasb-topics", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "topics": [{"topic_code": "FOO"}, {"topic_code": "BAR"}],
                    "total": 2,
                },
            )
        )
        resource = SasbTopicsResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"topic_code": "FOO"}, {"topic_code": "BAR"}]
        assert route.call_count == 1

    def test_iter_all_multi_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Two pages: a full first page, partial second page; iter_all
        # must walk both before stopping.
        page1_topics = [{"topic_code": f"T{i:03d}"} for i in range(100)]
        respx_mock.get("/sasb-topics", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"topics": page1_topics, "total": 105})
        )
        respx_mock.get("/sasb-topics", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200, json={"topics": [{"topic_code": "TAIL"}], "total": 105}
            )
        )
        resource = SasbTopicsResource(sync_client)
        items = list(resource.iter_all())
        assert len(items) == 101
        assert items[-1] == {"topic_code": "TAIL"}

    def test_iter_all_forwards_industry(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/sasb-topics", params={"industry": "TC-IM", "limit": "100", "offset": "0"}
        ).mock(return_value=httpx.Response(200, json={"topics": [], "total": 0}))
        resource = SasbTopicsResource(sync_client)
        assert list(resource.iter_all(industry="TC-IM")) == []
        assert route.called

    def test_list_500_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Avoid sleeping during retry budget exhaustion.
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/sasb-topics").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = SasbTopicsResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list()


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestSasbTopicsAsync:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"topics": [{"topic_code": "AB"}], "total": 1}
        route = respx_mock.get("/sasb-topics").mock(return_value=httpx.Response(200, json=body))
        resource = AsyncSasbTopicsResource(async_client)
        assert await resource.list() == body
        assert route.called

    async def test_list_with_industry(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sasb-topics", params={"industry": "FN-CB"}).mock(
            return_value=httpx.Response(200, json={"topics": [], "total": 0})
        )
        resource = AsyncSasbTopicsResource(async_client)
        await resource.list(industry="FN-CB")
        assert route.called

    async def test_iter_all_multi_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [{"topic_code": f"X{i:03d}"} for i in range(100)]
        respx_mock.get("/sasb-topics", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"topics": page1, "total": 102})
        )
        respx_mock.get("/sasb-topics", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200, json={"topics": [{"topic_code": "LAST"}], "total": 102}
            )
        )
        resource = AsyncSasbTopicsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert len(out) == 101
        assert out[-1] == {"topic_code": "LAST"}

    async def test_iter_all_empty_page_stops(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/sasb-topics", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(200, json={"topics": [], "total": 0})
        )
        resource = AsyncSasbTopicsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert out == []
