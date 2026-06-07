"""Tests for ``cerberus_compliance.resources.ran``."""

from __future__ import annotations

import datetime
from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.ran import (
    AsyncRANResource,
    RANResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


class TestRANMeta:
    def test_sync_prefix(self) -> None:
        assert RANResource._path_prefix == "/ran"

    def test_async_prefix(self) -> None:
        assert AsyncRANResource._path_prefix == "/ran"

    def test_sync_subclass(self) -> None:
        assert issubclass(RANResource, BaseResource)

    def test_async_subclass(self) -> None:
        assert issubclass(AsyncRANResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestRANSync:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "chapter_number": "1-13",
                    "chapter_title": "Clasificación de gestión y solvencia",
                    "content_md5": "abc123",
                    "documento_url": "https://cmf/ran/1-13.pdf",
                    "effective_at": None,
                    "first_seen_at": "2026-01-01T00:00:00Z",
                    "last_seen_at": "2026-06-01T00:00:00Z",
                }
            ],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/ran").mock(return_value=httpx.Response(200, json=body))
        resource = RANResource(sync_client)
        result = resource.list()
        assert result == body
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_list_with_q(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/ran", params={"q": "liquidez"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = RANResource(sync_client)
        result = resource.list(q="liquidez")
        assert result == {"items": [], "total": 0, "limit": 20, "offset": 0}
        assert route.called

    def test_list_with_date_range(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ran", params={"desde": "2026-01-01", "hasta": "2026-06-01"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = RANResource(sync_client)
        resource.list(desde=datetime.date(2026, 1, 1), hasta=datetime.date(2026, 6, 1))
        assert route.called

    def test_list_datetime_is_truncated_to_date(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A datetime (subclass of date) must be normalised to YYYY-MM-DD,
        # not serialised with a time component.
        route = respx_mock.get("/ran", params={"desde": "2026-03-15"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = RANResource(sync_client)
        resource.list(desde=datetime.datetime(2026, 3, 15, 13, 45, 0))
        assert route.called

    def test_list_with_limit_and_offset(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ran", params={"limit": "5", "offset": "10"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 5, "offset": 10}
            )
        )
        resource = RANResource(sync_client)
        resource.list(limit=5, offset=10)
        assert route.called

    def test_list_drops_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ran").mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = RANResource(sync_client)
        resource.list(desde=None, hasta=None, q=None, limit=None, offset=None)
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_iter_all_single_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # One page, fewer items than the SDK's page size (100) — must stop
        # after the first request without issuing a second.
        route = respx_mock.get("/ran", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"chapter_number": "1-1"}, {"chapter_number": "1-2"}],
                    "total": 2,
                    "limit": 100,
                    "offset": 0,
                },
            )
        )
        resource = RANResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"chapter_number": "1-1"}, {"chapter_number": "1-2"}]
        assert route.call_count == 1

    def test_iter_all_multi_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Two pages: a full first page, partial second page; iter_all
        # must walk both before stopping.
        page1 = [{"chapter_number": f"C{i:03d}"} for i in range(100)]
        respx_mock.get("/ran", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/ran", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"chapter_number": "TAIL"}],
                    "total": 101,
                    "limit": 100,
                    "offset": 100,
                },
            )
        )
        resource = RANResource(sync_client)
        items = list(resource.iter_all())
        assert len(items) == 101
        assert items[-1] == {"chapter_number": "TAIL"}

    def test_iter_all_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/ran",
            params={
                "desde": "2026-01-01",
                "q": "capital",
                "limit": "100",
                "offset": "0",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = RANResource(sync_client)
        assert list(resource.iter_all(desde=datetime.date(2026, 1, 1), q="capital")) == []
        assert route.called

    def test_iter_all_empty_first_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ran", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = RANResource(sync_client)
        assert list(resource.iter_all()) == []
        assert route.call_count == 1

    def test_iter_all_malformed_items_stops(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # A non-list ``items`` payload is treated as "no rows": iter_all
        # yields nothing and stops after the first request.
        route = respx_mock.get("/ran", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": None, "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = RANResource(sync_client)
        assert list(resource.iter_all()) == []
        assert route.call_count == 1

    def test_list_500_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Avoid sleeping during retry budget exhaustion.
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/ran").mock(
            return_value=httpx.Response(500, json=problem_json(status=500, title="Server Error"))
        )
        resource = RANResource(sync_client)
        with pytest.raises(CerberusAPIError):
            resource.list()


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestRANAsync:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "items": [{"chapter_number": "1-1"}],
            "total": 1,
            "limit": 20,
            "offset": 0,
        }
        route = respx_mock.get("/ran").mock(return_value=httpx.Response(200, json=body))
        resource = AsyncRANResource(async_client)
        assert await resource.list() == body
        assert route.called

    async def test_list_with_date_range(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ran", params={"desde": "2026-02-01", "hasta": "2026-03-01"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 0}
            )
        )
        resource = AsyncRANResource(async_client)
        await resource.list(desde=datetime.date(2026, 2, 1), hasta=datetime.date(2026, 3, 1))
        assert route.called

    async def test_list_with_q_and_offset(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/ran", params={"q": "riesgo", "offset": "20"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 20, "offset": 20}
            )
        )
        resource = AsyncRANResource(async_client)
        await resource.list(q="riesgo", offset=20)
        assert route.called

    async def test_iter_all_multi_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page1 = [{"chapter_number": f"X{i:03d}"} for i in range(100)]
        respx_mock.get("/ran", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": page1, "total": 101, "limit": 100, "offset": 0}
            )
        )
        respx_mock.get("/ran", params={"limit": "100", "offset": "100"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"chapter_number": "LAST"}],
                    "total": 101,
                    "limit": 100,
                    "offset": 100,
                },
            )
        )
        resource = AsyncRANResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert len(out) == 101
        assert out[-1] == {"chapter_number": "LAST"}

    async def test_iter_all_empty_page_stops(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/ran", params={"limit": "100", "offset": "0"}).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncRANResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert out == []

    async def test_iter_all_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/ran", params={"hasta": "2026-06-01", "limit": "100", "offset": "0"}
        ).mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
            )
        )
        resource = AsyncRANResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(hasta=datetime.date(2026, 6, 1)):
            out.append(item)
        assert out == []
        assert route.called
