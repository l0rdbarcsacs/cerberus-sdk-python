"""TDD tests for ``cerberus_compliance.resources.regulations``.

The ``regulations`` resource lists and fetches regulatory-compliance
applicability records — which laws/norms bind which entity under which
framework (Chilean Ley 21.521, Ley 21.719, NCG 514, plus international
SOX / MiFID). It is a thin, strictly-typed adapter over the shared
``BaseResource`` / ``AsyncBaseResource`` helpers.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.regulations import (
    AsyncRegulationsResource,
    RegulationsResource,
)

# ---------------------------------------------------------------------------
# Meta / typing sanity
# ---------------------------------------------------------------------------


class TestRegulationsResourceMeta:
    def test_sync_path_prefix(self) -> None:
        assert RegulationsResource._path_prefix == "/regulations"

    def test_async_path_prefix(self) -> None:
        assert AsyncRegulationsResource._path_prefix == "/regulations"

    def test_sync_subclass_of_base(self) -> None:
        assert issubclass(RegulationsResource, BaseResource)

    def test_async_subclass_of_base(self) -> None:
        assert issubclass(AsyncRegulationsResource, AsyncBaseResource)

    def test_sync_constructor_binds_client(self, sync_client: CerberusClient) -> None:
        resource = RegulationsResource(sync_client)
        assert resource._client is sync_client

    def test_async_constructor_binds_client(self, async_client: AsyncCerberusClient) -> None:
        resource = AsyncRegulationsResource(async_client)
        assert resource._client is async_client


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestRegulationsResource:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "reg_1", "framework": "Ley21521"},
                        {"id": "reg_2", "framework": "NCG514"},
                    ],
                    "next": None,
                    "page": {},
                },
            )
        )
        resource = RegulationsResource(sync_client)
        items = resource.list()
        assert items == [
            {"id": "reg_1", "framework": "Ley21521"},
            {"id": "reg_2", "framework": "NCG514"},
        ]
        assert route.called
        assert route.calls.last.request.url.params.get("entity_id") is None
        assert route.calls.last.request.url.params.get("framework") is None

    def test_list_filters_entity_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations", params={"entity_id": "ent_1"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_1"}], "next": None},
            )
        )
        resource = RegulationsResource(sync_client)
        items = resource.list(entity_id="ent_1")
        assert items == [{"id": "reg_1"}]
        assert route.called

    def test_list_filters_framework(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations", params={"framework": "Ley21521"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_1", "framework": "Ley21521"}], "next": None},
            )
        )
        resource = RegulationsResource(sync_client)
        items = resource.list(framework="Ley21521")
        assert items == [{"id": "reg_1", "framework": "Ley21521"}]
        assert route.called

    def test_list_filters_both(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/regulations",
            params={"entity_id": "ent_1", "framework": "Ley21719"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_3"}], "next": None},
            )
        )
        resource = RegulationsResource(sync_client)
        items = resource.list(entity_id="ent_1", framework="Ley21719")
        assert items == [{"id": "reg_3"}]
        assert route.called

    def test_list_omits_none(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations", params={"framework": "NCG514"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_9"}], "next": None},
            )
        )
        resource = RegulationsResource(sync_client)
        items = resource.list(framework="NCG514")
        assert items == [{"id": "reg_9"}]
        # Explicitly verify that `entity_id` was NOT sent when None.
        sent_url = route.calls.last.request.url
        assert "entity_id" not in sent_url.params
        assert "limit" not in sent_url.params
        assert sent_url.params.get("framework") == "NCG514"

    def test_list_forwards_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations", params={"limit": "50"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_1"}], "next": None},
            )
        )
        resource = RegulationsResource(sync_client)
        items = resource.list(limit=50)
        assert items == [{"id": "reg_1"}]
        assert route.called

    def test_get_by_id(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        body = {
            "id": "reg_42",
            "entity_id": "ent_1",
            "framework": "SOX",
            "status": "applicable",
        }
        respx_mock.get("/regulations/reg_42").mock(return_value=httpx.Response(200, json=body))
        resource = RegulationsResource(sync_client)
        assert resource.get("reg_42") == body

    def test_get_404_raises_cerberus_api_error(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/regulations/missing").mock(
            return_value=httpx.Response(
                404,
                json=problem_json(
                    status=404,
                    title="Not Found",
                    detail="Regulation 'missing' not found",
                ),
                headers={"Content-Type": "application/problem+json"},
            )
        )
        resource = RegulationsResource(sync_client)
        with pytest.raises(CerberusAPIError) as excinfo:
            resource.get("missing")
        assert excinfo.value.status == 404

    def test_iter_all_two_pages_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Register the cursor-specific route FIRST so respx matches it
        # before the more generic "framework only" route (subset-match).
        page2 = respx_mock.get(
            "/regulations",
            params={"framework": "SOX", "cursor": "cur2"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_b"}], "next": None},
            )
        )
        page1 = respx_mock.get(
            "/regulations",
            params={"framework": "SOX"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_a"}], "next": "cur2"},
            )
        )
        resource = RegulationsResource(sync_client)
        out = list(resource.iter_all(framework="SOX"))
        assert out == [{"id": "reg_a"}, {"id": "reg_b"}]
        assert page1.called
        assert page2.called

    def test_iter_all_stops_on_null_next(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_only"}], "next": None},
            )
        )
        resource = RegulationsResource(sync_client)
        assert list(resource.iter_all()) == [{"id": "reg_only"}]
        assert route.call_count == 1

    def test_iter_all_stops_on_missing_next_key(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_only"}]},
            )
        )
        resource = RegulationsResource(sync_client)
        assert list(resource.iter_all()) == [{"id": "reg_only"}]
        assert route.call_count == 1


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncRegulationsResource:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "reg_1"},
                        {"id": "reg_2"},
                    ],
                    "next": None,
                },
            )
        )
        resource = AsyncRegulationsResource(async_client)
        items = await resource.list()
        assert items == [{"id": "reg_1"}, {"id": "reg_2"}]
        assert route.called

    async def test_list_filters_entity_id(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations", params={"entity_id": "ent_1"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_1"}], "next": None},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        items = await resource.list(entity_id="ent_1")
        assert items == [{"id": "reg_1"}]
        assert route.called

    async def test_list_filters_framework(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations", params={"framework": "Ley21521"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_1"}], "next": None},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        items = await resource.list(framework="Ley21521")
        assert items == [{"id": "reg_1"}]
        assert route.called

    async def test_list_filters_both(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/regulations",
            params={"entity_id": "ent_1", "framework": "Ley21719"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_3"}], "next": None},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        items = await resource.list(entity_id="ent_1", framework="Ley21719")
        assert items == [{"id": "reg_3"}]
        assert route.called

    async def test_list_omits_none(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations", params={"framework": "NCG514"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_9"}], "next": None},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        items = await resource.list(framework="NCG514")
        assert items == [{"id": "reg_9"}]
        sent_url = route.calls.last.request.url
        assert "entity_id" not in sent_url.params
        assert "limit" not in sent_url.params

    async def test_list_forwards_limit(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations", params={"limit": "25"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_1"}], "next": None},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        items = await resource.list(limit=25)
        assert items == [{"id": "reg_1"}]
        assert route.called

    async def test_get_by_id(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {"id": "reg_42", "framework": "MiFID"}
        respx_mock.get("/regulations/reg_42").mock(return_value=httpx.Response(200, json=body))
        resource = AsyncRegulationsResource(async_client)
        assert await resource.get("reg_42") == body

    async def test_get_404_raises_cerberus_api_error(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/regulations/missing").mock(
            return_value=httpx.Response(
                404,
                json=problem_json(
                    status=404,
                    title="Not Found",
                    detail="Regulation 'missing' not found",
                ),
                headers={"Content-Type": "application/problem+json"},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        with pytest.raises(CerberusAPIError) as excinfo:
            await resource.get("missing")
        assert excinfo.value.status == 404

    async def test_iter_all_two_pages_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Cursor-specific route FIRST (see sync sibling for rationale).
        respx_mock.get(
            "/regulations",
            params={"framework": "SOX", "cursor": "cur2"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_b"}], "next": None},
            )
        )
        respx_mock.get(
            "/regulations",
            params={"framework": "SOX"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_a"}], "next": "cur2"},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(framework="SOX"):
            out.append(item)
        assert out == [{"id": "reg_a"}, {"id": "reg_b"}]

    async def test_iter_all_stops_on_null_next(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_only"}], "next": None},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert out == [{"id": "reg_only"}]
        assert route.call_count == 1

    async def test_iter_all_stops_on_missing_next_key(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/regulations").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "reg_only"}]},
            )
        )
        resource = AsyncRegulationsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert out == [{"id": "reg_only"}]
        assert route.call_count == 1
