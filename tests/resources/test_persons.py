"""TDD tests for :mod:`cerberus_compliance.resources.persons`.

Covers :class:`PersonsResource` and :class:`AsyncPersonsResource`: the
``list`` / ``get`` / ``regulatory_profile`` / ``iter_all`` surface,
cursor pagination, filter forwarding, and propagation of API errors
(4xx / 429) up the call stack.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, RateLimitError
from cerberus_compliance.resources.persons import AsyncPersonsResource, PersonsResource
from cerberus_compliance.retry import RetryConfig

# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestSyncPersonsResource:
    def test_list_no_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons").mock(
            return_value=httpx.Response(
                200, json={"data": [{"id": "p1"}, {"id": "p2"}], "next": None}
            )
        )
        resource = PersonsResource(sync_client)
        assert resource.list() == [{"id": "p1"}, {"id": "p2"}]
        assert route.called

    def test_list_with_rut(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/persons", params={"rut": "7890123-4"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "7890123-4"}], "next": None})
        )
        resource = PersonsResource(sync_client)
        assert resource.list(rut="7890123-4") == [{"id": "7890123-4"}]
        assert route.called

    def test_list_with_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons", params={"limit": "50"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "p9"}], "next": None})
        )
        resource = PersonsResource(sync_client)
        assert resource.list(limit=50) == [{"id": "p9"}]
        assert route.called

    def test_list_with_both_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/persons", params={"rut": "7890123-4", "limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "pZ"}], "next": None})
        )
        resource = PersonsResource(sync_client)
        assert resource.list(rut="7890123-4", limit=10) == [{"id": "pZ"}]
        assert route.called

    def test_get_returns_person(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons/7890123-4").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "7890123-4",
                    "name": "Jose Ignacio Concha",
                    "nationality": "CL",
                },
            )
        )
        resource = PersonsResource(sync_client)
        assert resource.get("7890123-4") == {
            "id": "7890123-4",
            "name": "Jose Ignacio Concha",
            "nationality": "CL",
        }

    def test_regulatory_profile_returns_dict(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        profile = {
            "pep": True,
            "score": 42,
            "watchlists": ["OFAC"],
            "last_reviewed_at": "2026-04-01T12:00:00Z",
        }
        route = respx_mock.get("/persons/7890123-4/regulatory-profile").mock(
            return_value=httpx.Response(200, json=profile)
        )
        resource = PersonsResource(sync_client)
        assert resource.regulatory_profile("7890123-4") == profile
        assert route.called

    def test_iter_all_no_filters_paginates(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Specific (cursor) route registered FIRST so the dispatcher
        # hits it before the bare subset match.
        page2 = respx_mock.get("/persons", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "p2"}], "next": None})
        )
        page1 = respx_mock.get("/persons", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "p1"}], "next": "tok2"})
        )
        resource = PersonsResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"id": "p1"}, {"id": "p2"}]
        assert page1.called
        assert page2.called

    def test_iter_all_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page2 = respx_mock.get("/persons", params={"rut": "7890123-4", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        page1 = respx_mock.get("/persons", params={"rut": "7890123-4"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "n2"})
        )
        resource = PersonsResource(sync_client)
        items = list(resource.iter_all(rut="7890123-4"))
        assert items == [{"id": "a"}, {"id": "b"}]
        assert page1.called
        assert page2.called

    def test_get_propagates_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons/missing").mock(
            return_value=httpx.Response(
                404,
                json={
                    "type": "about:blank",
                    "title": "Not Found",
                    "status": 404,
                    "detail": "Person missing",
                },
            )
        )
        resource = PersonsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc_info:
            resource.get("missing")
        assert exc_info.value.status == 404

    def test_get_propagates_429_as_rate_limit_error(
        self, api_key: str, base_url: str, respx_mock: respx.MockRouter
    ) -> None:
        # Fresh client with no retries so the 429 surfaces without delay.
        client = CerberusClient(
            api_key=api_key,
            base_url=base_url,
            retry=RetryConfig(max_attempts=1, base_delay_ms=1),
        )
        try:
            respx_mock.get("/persons/rate-limited").mock(
                return_value=httpx.Response(
                    429,
                    headers={"retry-after": "1"},
                    json={"title": "Too Many Requests", "status": 429},
                )
            )
            resource = PersonsResource(client)
            with pytest.raises(RateLimitError):
                resource.get("rate-limited")
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncPersonsResource:
    async def test_async_list_returns_data(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "p0"}], "next": None})
        )
        resource = AsyncPersonsResource(async_client)
        assert await resource.list() == [{"id": "p0"}]

    async def test_async_get_returns_person(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons/7890123-4").mock(
            return_value=httpx.Response(200, json={"id": "7890123-4", "name": "Jane Roe"})
        )
        resource = AsyncPersonsResource(async_client)
        assert await resource.get("7890123-4") == {
            "id": "7890123-4",
            "name": "Jane Roe",
        }

    async def test_async_regulatory_profile_returns_dict(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        profile = {"pep": False, "score": 7, "watchlists": []}
        respx_mock.get("/persons/7890123-4/regulatory-profile").mock(
            return_value=httpx.Response(200, json=profile)
        )
        resource = AsyncPersonsResource(async_client)
        assert await resource.regulatory_profile("7890123-4") == profile

    async def test_async_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/persons", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "tok2"})
        )
        resource = AsyncPersonsResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]

    async def test_async_iter_all_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons", params={"rut": "7890123-4", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        respx_mock.get("/persons", params={"rut": "7890123-4"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "n2"})
        )
        resource = AsyncPersonsResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all(rut="7890123-4"):
            collected.append(item)
        assert collected == [{"id": "a"}, {"id": "b"}]

    async def test_async_list_with_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/persons", params={"rut": "7890123-4", "limit": "5"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "pZ"}], "next": None})
        )
        resource = AsyncPersonsResource(async_client)
        assert await resource.list(rut="7890123-4", limit=5) == [{"id": "pZ"}]
