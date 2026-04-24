"""TDD tests for :mod:`cerberus_compliance.resources.material_events`.

Covers :class:`MaterialEventsResource` and its async mirror: list/get/iter_all
surface, datetime->ISO coercion on ``since`` / ``until`` filters, cursor
pagination forwarding, and propagation of API errors including 429 rate
limits.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, RateLimitError
from cerberus_compliance.resources.material_events import (
    AsyncMaterialEventsResource,
    MaterialEventsResource,
)
from cerberus_compliance.retry import RetryConfig

# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestSyncMaterialEventsResource:
    def test_list_no_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/material-events").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "evt1"}, {"id": "evt2"}], "next": None},
            )
        )
        resource = MaterialEventsResource(sync_client)
        assert resource.list() == [{"id": "evt1"}, {"id": "evt2"}]
        assert route.called

    def test_list_with_entity_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/material-events", params={"entity_id": "76123456-7"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "evt1"}], "next": None}
            )
        )
        resource = MaterialEventsResource(sync_client)
        assert resource.list(entity_id="76123456-7") == [{"id": "evt1"}]
        assert route.called

    def test_list_with_since_string(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/material-events", params={"since": "2026-01-01T00:00:00Z"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "evtA"}], "next": None}
            )
        )
        resource = MaterialEventsResource(sync_client)
        assert resource.list(since="2026-01-01T00:00:00Z") == [{"id": "evtA"}]
        assert route.called

    def test_list_with_since_datetime(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/material-events", params={"since": "2026-01-01T00:00:00+00:00"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "evtB"}], "next": None}
            )
        )
        resource = MaterialEventsResource(sync_client)
        result = resource.list(since=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert result == [{"id": "evtB"}]
        assert route.called

    def test_list_with_until_datetime(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/material-events", params={"until": "2026-04-01T00:00:00+00:00"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "evtC"}], "next": None}
            )
        )
        resource = MaterialEventsResource(sync_client)
        result = resource.list(until=datetime(2026, 4, 1, tzinfo=timezone.utc))
        assert result == [{"id": "evtC"}]
        assert route.called

    def test_list_with_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/material-events", params={"limit": "10"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "evtD"}], "next": None}
            )
        )
        resource = MaterialEventsResource(sync_client)
        assert resource.list(limit=10) == [{"id": "evtD"}]
        assert route.called

    def test_list_with_all_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/material-events",
            params={
                "entity_id": "76123456-7",
                "since": "2026-01-01T00:00:00+00:00",
                "until": "2026-04-01T00:00:00Z",
                "limit": "50",
            },
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "evtAll"}], "next": None}
            )
        )
        resource = MaterialEventsResource(sync_client)
        result = resource.list(
            entity_id="76123456-7",
            since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            until="2026-04-01T00:00:00Z",
            limit=50,
        )
        assert result == [{"id": "evtAll"}]
        assert route.called

    def test_get_returns_event(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/material-events/evt_abc").mock(
            return_value=httpx.Response(
                200, json={"id": "evt_abc", "headline": "Profit warning"}
            )
        )
        resource = MaterialEventsResource(sync_client)
        assert resource.get("evt_abc") == {
            "id": "evt_abc",
            "headline": "Profit warning",
        }

    def test_iter_all_no_filters_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Register the more specific (cursor) route FIRST — respx matches
        # params as a subset, so ``params={}`` would otherwise swallow the
        # cursor request.
        page2 = respx_mock.get(
            "/material-events", params={"cursor": "tok2"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "e2"}], "next": None}
            )
        )
        page1 = respx_mock.get("/material-events", params={}).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "e1"}], "next": "tok2"}
            )
        )
        resource = MaterialEventsResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"id": "e1"}, {"id": "e2"}]
        assert page1.called
        assert page2.called

    def test_iter_all_forwards_entity_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page2 = respx_mock.get(
            "/material-events",
            params={"entity_id": "76123456-7", "cursor": "n2"},
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "b"}], "next": None}
            )
        )
        page1 = respx_mock.get(
            "/material-events", params={"entity_id": "76123456-7"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "a"}], "next": "n2"}
            )
        )
        resource = MaterialEventsResource(sync_client)
        items = list(resource.iter_all(entity_id="76123456-7"))
        assert items == [{"id": "a"}, {"id": "b"}]
        assert page1.called
        assert page2.called

    def test_iter_all_coerces_datetime_filter(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        iso = "2026-01-01T00:00:00+00:00"
        route = respx_mock.get(
            "/material-events", params={"since": iso}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "only"}], "next": None}
            )
        )
        resource = MaterialEventsResource(sync_client)
        items = list(
            resource.iter_all(since=datetime(2026, 1, 1, tzinfo=timezone.utc))
        )
        assert items == [{"id": "only"}]
        assert route.called

    def test_get_propagates_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/material-events/missing").mock(
            return_value=httpx.Response(
                404,
                json={
                    "type": "about:blank",
                    "title": "Not Found",
                    "status": 404,
                    "detail": "event missing",
                },
            )
        )
        resource = MaterialEventsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc_info:
            resource.get("missing")
        assert exc_info.value.status == 404

    def test_get_propagates_429_as_rate_limit_error(
        self, api_key: str, base_url: str, respx_mock: respx.MockRouter
    ) -> None:
        client = CerberusClient(
            api_key=api_key,
            base_url=base_url,
            timeout=2.0,
            retry=RetryConfig(max_attempts=1, base_delay_ms=1),
        )
        try:
            respx_mock.get("/material-events/rate-limited").mock(
                return_value=httpx.Response(
                    429,
                    headers={"retry-after": "1"},
                    json={"title": "Too Many Requests", "status": 429},
                )
            )
            resource = MaterialEventsResource(client)
            with pytest.raises(RateLimitError):
                resource.get("rate-limited")
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncMaterialEventsResource:
    async def test_async_list_returns_data(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/material-events", params={"entity_id": "76123456-7"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "e1"}], "next": None}
            )
        )
        resource = AsyncMaterialEventsResource(async_client)
        assert await resource.list(entity_id="76123456-7") == [{"id": "e1"}]

    async def test_async_list_coerces_datetime(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/material-events",
            params={"since": "2026-01-01T00:00:00+00:00"},
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "iso"}], "next": None}
            )
        )
        resource = AsyncMaterialEventsResource(async_client)
        result = await resource.list(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        assert result == [{"id": "iso"}]

    async def test_async_list_with_until_and_limit(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/material-events",
            params={"until": "2026-04-01T00:00:00Z", "limit": "3"},
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "ul"}], "next": None}
            )
        )
        resource = AsyncMaterialEventsResource(async_client)
        result = await resource.list(until="2026-04-01T00:00:00Z", limit=3)
        assert result == [{"id": "ul"}]

    async def test_async_get_returns_event(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/material-events/evt_xyz").mock(
            return_value=httpx.Response(200, json={"id": "evt_xyz"})
        )
        resource = AsyncMaterialEventsResource(async_client)
        assert await resource.get("evt_xyz") == {"id": "evt_xyz"}

    async def test_async_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/material-events", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": 2}], "next": None}
            )
        )
        respx_mock.get("/material-events", params={}).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": 1}], "next": "tok2"}
            )
        )
        resource = AsyncMaterialEventsResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]

    async def test_async_iter_all_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(
            "/material-events",
            params={"entity_id": "76123456-7", "cursor": "n2"},
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "b"}], "next": None}
            )
        )
        respx_mock.get(
            "/material-events", params={"entity_id": "76123456-7"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "a"}], "next": "n2"}
            )
        )
        resource = AsyncMaterialEventsResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all(entity_id="76123456-7"):
            collected.append(item)
        assert collected == [{"id": "a"}, {"id": "b"}]

    async def test_async_iter_all_coerces_datetime_filter(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        iso = "2026-01-01T00:00:00+00:00"
        respx_mock.get(
            "/material-events", params={"since": iso, "cursor": "c2"}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "p2"}], "next": None}
            )
        )
        respx_mock.get(
            "/material-events", params={"since": iso}
        ).mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "p1"}], "next": "c2"}
            )
        )
        resource = AsyncMaterialEventsResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all(
            since=datetime(2026, 1, 1, tzinfo=timezone.utc)
        ):
            collected.append(item)
        assert collected == [{"id": "p1"}, {"id": "p2"}]
