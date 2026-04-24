"""TDD tests for ``cerberus_compliance.resources.sanctions``.

Covers the public ``SanctionsResource`` / ``AsyncSanctionsResource``
surface: filter forwarding, the ``ONU`` -> ``UN`` alias normalisation,
single-item fetch, 404 error mapping, 429 retry, and cursor pagination
(sync + async).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource
from cerberus_compliance.resources.sanctions import (
    AsyncSanctionsResource,
    SanctionsResource,
)

# ---------------------------------------------------------------------------
# Static structural tests
# ---------------------------------------------------------------------------


def test_sync_path_prefix_is_sanctions() -> None:
    assert SanctionsResource._path_prefix == "/sanctions"


def test_async_path_prefix_is_sanctions() -> None:
    assert AsyncSanctionsResource._path_prefix == "/sanctions"


def test_sync_inherits_base_resource() -> None:
    assert issubclass(SanctionsResource, BaseResource)


def test_async_inherits_async_base_resource() -> None:
    assert issubclass(AsyncSanctionsResource, AsyncBaseResource)


# ---------------------------------------------------------------------------
# Sync behaviour
# ---------------------------------------------------------------------------


class TestSanctionsResource:
    def test_list_no_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "s1"}, {"id": "s2"}], "next": None},
            )
        )
        resource = SanctionsResource(sync_client)
        assert resource.list() == [{"id": "s1"}, {"id": "s2"}]
        assert route.called
        # No query parameters were appended.
        assert route.calls.last.request.url.query == b""

    def test_list_with_target_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions", params={"target_id": "ent_42"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "s1"}], "next": None})
        )
        resource = SanctionsResource(sync_client)
        assert resource.list(target_id="ent_42") == [{"id": "s1"}]
        assert route.called

    def test_list_with_source_and_active(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # httpx serialises `True` -> "true" via the str() codec it uses for
        # query params. Assert by inspecting the actual query string rather
        # than relying on respx subset-matching for booleans.
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "s9"}], "next": None})
        )
        resource = SanctionsResource(sync_client)
        out = resource.list(source="OFAC", active=True)
        assert out == [{"id": "s9"}]
        assert route.called

        params = dict(route.calls.last.request.url.params.multi_items())
        assert params.get("source") == "OFAC"
        # Accept either literal case that httpx might emit.
        assert params.get("active") in {"true", "True"}
        assert "target_id" not in params

    def test_list_onu_alias_translates_to_un(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Policy: normalise the locale alias "ONU" to the canonical "UN"
        # before the request leaves the SDK.
        route = respx_mock.get("/sanctions", params={"source": "UN"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "u1"}], "next": None})
        )
        resource = SanctionsResource(sync_client)
        out = resource.list(source="ONU")
        assert out == [{"id": "u1"}]
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params["source"] == "UN"

    def test_list_omits_none_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = SanctionsResource(sync_client)
        resource.list(source="OFAC")
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"source": "OFAC"}
        assert "target_id" not in params
        assert "active" not in params
        assert "limit" not in params

    def test_list_with_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions", params={"limit": "50"}).mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = SanctionsResource(sync_client)
        resource.list(limit=50)
        assert route.called

    def test_list_active_false_forwarded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = SanctionsResource(sync_client)
        resource.list(active=False)
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params.get("active") in {"false", "False"}

    def test_get_by_id(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        respx_mock.get("/sanctions/sanc_123").mock(
            return_value=httpx.Response(
                200,
                json={"id": "sanc_123", "source": "OFAC", "active": True},
            )
        )
        resource = SanctionsResource(sync_client)
        assert resource.get("sanc_123") == {
            "id": "sanc_123",
            "source": "OFAC",
            "active": True,
        }

    def test_get_404_raises(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/sanctions/missing").mock(
            return_value=httpx.Response(
                404,
                json=problem_json(status=404, title="Not Found"),
            )
        )
        resource = SanctionsResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc:
            resource.get("missing")
        assert exc.value.status == 404

    def test_get_429_retries_then_returns(
        self,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Avoid real sleeping while still exercising the retry branch.
        monkeypatch.setattr("time.sleep", lambda _s: None)
        respx_mock.get("/sanctions/sanc_1").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json={"id": "sanc_1"}),
            ]
        )
        resource = SanctionsResource(sync_client)
        assert resource.get("sanc_1") == {"id": "sanc_1"}

    def test_iter_all_two_pages(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Specific (cursor) route registered FIRST so respx dispatches it
        # before the catch-all for page 1.
        page2 = respx_mock.get("/sanctions", params={"cursor": "p2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        page1 = respx_mock.get("/sanctions", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "p2"})
        )
        resource = SanctionsResource(sync_client)
        out = list(resource.iter_all())
        assert out == [{"id": "a"}, {"id": "b"}]
        assert page1.called
        assert page2.called

    def test_iter_all_forwards_filters_each_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page2 = respx_mock.get("/sanctions", params={"active": "true", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        page1 = respx_mock.get("/sanctions", params={"active": "true"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "n2"})
        )
        resource = SanctionsResource(sync_client)
        out = list(resource.iter_all(active=True))
        assert out == [{"id": "a"}, {"id": "b"}]
        assert page1.called
        assert page2.called

    def test_iter_all_drops_none_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # `None`-valued kwargs must not bleed into the wire URL.
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "z"}], "next": None})
        )
        resource = SanctionsResource(sync_client)
        assert list(resource.iter_all(source=None, target_id=None, active=None)) == [{"id": "z"}]
        assert route.calls.last.request.url.query == b""


# ---------------------------------------------------------------------------
# Async behaviour
# ---------------------------------------------------------------------------


class TestAsyncSanctionsResource:
    async def test_list_no_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "s1"}], "next": None},
            )
        )
        resource = AsyncSanctionsResource(async_client)
        assert await resource.list() == [{"id": "s1"}]
        assert route.calls.last.request.url.query == b""

    async def test_list_with_target_id(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions", params={"target_id": "per_7"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncSanctionsResource(async_client)
        assert await resource.list(target_id="per_7") == [{"id": "x"}]
        assert route.called

    async def test_list_with_source_and_active(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = AsyncSanctionsResource(async_client)
        await resource.list(source="EU", active=True)
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params.get("source") == "EU"
        assert params.get("active") in {"true", "True"}

    async def test_list_onu_alias_translates_to_un(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions", params={"source": "UN"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "u1"}], "next": None})
        )
        resource = AsyncSanctionsResource(async_client)
        out = await resource.list(source="ONU")
        assert out == [{"id": "u1"}]
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params["source"] == "UN"

    async def test_list_omits_none_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        resource = AsyncSanctionsResource(async_client)
        await resource.list(source="CMF")
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"source": "CMF"}

    async def test_get_by_id(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/sanctions/s_99").mock(
            return_value=httpx.Response(200, json={"id": "s_99"})
        )
        resource = AsyncSanctionsResource(async_client)
        assert await resource.get("s_99") == {"id": "s_99"}

    async def test_get_404_raises(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        problem_json: Any,
    ) -> None:
        respx_mock.get("/sanctions/ghost").mock(
            return_value=httpx.Response(404, json=problem_json(status=404, title="Not Found"))
        )
        resource = AsyncSanctionsResource(async_client)
        with pytest.raises(CerberusAPIError) as exc:
            await resource.get("ghost")
        assert exc.value.status == 404

    async def test_get_429_retries_then_returns(
        self,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def fake_sleep(_s: float) -> None:
            return None

        monkeypatch.setattr("asyncio.sleep", fake_sleep)
        respx_mock.get("/sanctions/rl").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json={"id": "rl"}),
            ]
        )
        resource = AsyncSanctionsResource(async_client)
        assert await resource.get("rl") == {"id": "rl"}

    async def test_iter_all_two_pages(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/sanctions", params={"cursor": "p2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        respx_mock.get("/sanctions", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "p2"})
        )
        resource = AsyncSanctionsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            out.append(item)
        assert out == [{"id": "a"}, {"id": "b"}]

    async def test_iter_all_forwards_filters_each_page(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/sanctions", params={"active": "true", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        respx_mock.get("/sanctions", params={"active": "true"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "n2"})
        )
        resource = AsyncSanctionsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(active=True):
            out.append(item)
        assert out == [{"id": "a"}, {"id": "b"}]

    async def test_iter_all_onu_alias_normalises(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Normalisation is applied consistently by both ``list`` and
        # ``iter_all``, so the server always sees the canonical ``UN``.
        route = respx_mock.get("/sanctions", params={"source": "UN"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": None})
        )
        resource = AsyncSanctionsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(source="ONU"):
            out.append(item)
        assert out == [{"id": "x"}]
        assert route.called

    async def test_iter_all_drops_none_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/sanctions").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "z"}], "next": None})
        )
        resource = AsyncSanctionsResource(async_client)
        out: list[dict[str, Any]] = []
        async for item in resource.iter_all(source=None, target_id=None, active=None):
            out.append(item)
        assert out == [{"id": "z"}]
        assert route.calls.last.request.url.query == b""
