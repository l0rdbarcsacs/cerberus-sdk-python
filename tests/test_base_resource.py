"""TDD tests for `cerberus_compliance.resources._base`.

A `BaseResource`/`AsyncBaseResource` provides ``_list``, ``_get``, and
``_iter_all`` helpers wired to a parent `(Async)CerberusClient._request`
call. Cursor pagination follows the ``next`` token from the response
envelope.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

# ---------------------------------------------------------------------------
# Sync subclass under test
# ---------------------------------------------------------------------------


class _Things(BaseResource):
    _path_prefix = "/things"

    def list(self, **params: Any) -> list[dict[str, Any]]:
        return self._list(params=params or None)

    def get(self, id_: str) -> dict[str, Any]:
        return self._get(id_)

    def iter_all(self, **params: Any) -> Iterator[dict[str, Any]]:
        return self._iter_all(params=params or None)


class _AsyncThings(AsyncBaseResource):
    _path_prefix = "/things"

    async def list(self, **params: Any) -> list[dict[str, Any]]:
        return await self._list(params=params or None)

    async def get(self, id_: str) -> dict[str, Any]:
        return await self._get(id_)

    def iter_all(self, **params: Any) -> AsyncIterator[dict[str, Any]]:
        return self._iter_all(params=params or None)


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestSyncBaseResource:
    def test_get_issues_correct_url(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things/abc").mock(
            return_value=httpx.Response(200, json={"id": "abc", "name": "n"})
        )
        things = _Things(sync_client)
        assert things.get("abc") == {"id": "abc", "name": "n"}

    def test_list_returns_data_array(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/things", params={"limit": "10"}).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "1"}, {"id": "2"}], "next": None, "page": {}},
            )
        )
        things = _Things(sync_client)
        items = things.list(limit=10)
        assert items == [{"id": "1"}, {"id": "2"}]
        assert route.called

    def test_list_no_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "1"}], "next": None})
        )
        things = _Things(sync_client)
        assert things.list() == [{"id": "1"}]

    def test_iter_all_paginates_two_pages(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Respx matches routes in registration order; `params={}` is a
        # subset-match that also matches any query — so register the
        # more specific (cursor=tok2) mock first.
        page2 = respx_mock.get("/things", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        page1 = respx_mock.get("/things", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "tok2"})
        )
        things = _Things(sync_client)
        items = list(things.iter_all())
        assert items == [{"id": 1}, {"id": 2}]
        assert page1.called
        assert page2.called

    def test_iter_all_forwards_extra_params_each_page(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Specific (both params) must be registered before the prefix
        # match so the route dispatcher hits it first.
        p2 = respx_mock.get("/things", params={"q": "rut", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        p1 = respx_mock.get("/things", params={"q": "rut"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "n2"})
        )
        things = _Things(sync_client)
        out = list(things.iter_all(q="rut"))
        assert out == [{"id": "a"}, {"id": "b"}]
        assert p1.called
        assert p2.called

    def test_iter_all_empty_no_next(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        things = _Things(sync_client)
        assert list(things.iter_all()) == []
        assert route.call_count == 1

    def test_iter_all_stops_on_empty_string_next(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}], "next": ""})
        )
        things = _Things(sync_client)
        assert list(things.iter_all()) == [{"id": "x"}]
        assert route.call_count == 1

    def test_iter_all_stops_on_missing_next_key(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "x"}]})
        )
        things = _Things(sync_client)
        assert list(things.iter_all()) == [{"id": "x"}]
        assert route.call_count == 1

    def test_list_returns_empty_when_data_not_list(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Defensive branch: server returns a non-list under "data".
        respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": "oops", "next": None})
        )
        things = _Things(sync_client)
        assert things.list() == []

    def test_iter_all_skips_non_dict_items(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "a"}, "garbage", 42, {"id": "b"}], "next": None},
            )
        )
        things = _Things(sync_client)
        assert list(things.iter_all()) == [{"id": "a"}, {"id": "b"}]

    def test_iter_all_handles_non_list_data(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": "not-a-list", "next": None})
        )
        things = _Things(sync_client)
        assert list(things.iter_all()) == []

    @pytest.mark.parametrize(
        "raw_id",
        [
            "../admin",
            "..%2Fadmin",
            "a/b",
            "weird id with spaces",
            "100%",
            "../../etc/passwd",
        ],
    )
    def test_get_percent_encodes_id(
        self,
        raw_id: str,
        sync_client: CerberusClient,
        respx_mock: respx.MockRouter,
    ) -> None:
        """`_get(id_)` must percent-encode the id and stay inside the path prefix.

        Regression test for the path-traversal gap surfaced by the P4 audit:
        ``f"{prefix}/{id_}"`` without encoding let ``"../admin"`` escape to
        ``GET /admin``, bypassing the sub-resource namespace entirely.
        """
        route = respx_mock.get(url__regex=r"^https://mock\.test/v1/things/.+").mock(
            return_value=httpx.Response(200, json={"id": "ok"})
        )
        things = _Things(sync_client)
        things.get(raw_id)

        assert route.called, "expected the encoded URL under /things/ to be hit"
        raw_path = route.calls.last.request.url.raw_path.decode("ascii")
        assert raw_path.startswith("/v1/things/"), f"id escaped the /things/ prefix: {raw_path!r}"
        suffix = raw_path[len("/v1/things/") :]
        assert "/" not in suffix, f"unencoded slash leaked into path suffix: {suffix!r}"


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncBaseResource:
    async def test_get(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things/abc").mock(return_value=httpx.Response(200, json={"id": "abc"}))
        things = _AsyncThings(async_client)
        assert await things.get("abc") == {"id": "abc"}

    async def test_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things", params={"limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "1"}], "next": None})
        )
        things = _AsyncThings(async_client)
        assert await things.list(limit=10) == [{"id": "1"}]

    async def test_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # More specific route first (see sync sibling for rationale).
        respx_mock.get("/things", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/things", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "tok2"})
        )
        things = _AsyncThings(async_client)
        out: list[dict[str, Any]] = []
        async for item in things.iter_all():
            out.append(item)
        assert out == [{"id": 1}, {"id": 2}]

    async def test_iter_all_forwards_params(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things", params={"q": "z", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        respx_mock.get("/things", params={"q": "z"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "n2"})
        )
        things = _AsyncThings(async_client)
        out: list[dict[str, Any]] = []
        async for item in things.iter_all(q="z"):
            out.append(item)
        assert out == [{"id": "a"}, {"id": "b"}]

    async def test_iter_all_empty(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": [], "next": None})
        )
        things = _AsyncThings(async_client)
        out: list[dict[str, Any]] = []
        async for item in things.iter_all():
            out.append(item)
        assert out == []
        assert route.call_count == 1

    async def test_list_returns_empty_when_data_not_list(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": 123, "next": None})
        )
        things = _AsyncThings(async_client)
        assert await things.list() == []

    async def test_iter_all_handles_non_list_data(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"data": "oops", "next": None})
        )
        things = _AsyncThings(async_client)
        out: list[dict[str, Any]] = []
        async for item in things.iter_all():
            out.append(item)
        assert out == []

    @pytest.mark.parametrize("raw_id", ["../admin", "a/b", "../../etc/passwd", "100%"])
    async def test_get_percent_encodes_id(
        self,
        raw_id: str,
        async_client: AsyncCerberusClient,
        respx_mock: respx.MockRouter,
    ) -> None:
        """Async mirror of the sync path-traversal guard."""
        route = respx_mock.get(url__regex=r"^https://mock\.test/v1/things/.+").mock(
            return_value=httpx.Response(200, json={"id": "ok"})
        )
        things = _AsyncThings(async_client)
        await things.get(raw_id)

        assert route.called
        raw_path = route.calls.last.request.url.raw_path.decode("ascii")
        assert raw_path.startswith("/v1/things/")
        suffix = raw_path[len("/v1/things/") :]
        assert "/" not in suffix, f"unencoded slash leaked into path suffix: {suffix!r}"


# ---------------------------------------------------------------------------
# Default _path_prefix sanity
# ---------------------------------------------------------------------------


def test_base_resource_default_prefix_is_empty() -> None:
    assert BaseResource._path_prefix == ""
    assert AsyncBaseResource._path_prefix == ""


def test_subclass_can_override_prefix() -> None:
    assert _Things._path_prefix == "/things"
    assert _AsyncThings._path_prefix == "/things"


def test_unused_pytest_import_silenced() -> None:
    # Touch pytest to keep ruff happy if no other test in this module references it.
    assert pytest.__version__


# ---------------------------------------------------------------------------
# Live-API envelope support: {"items": [...], "next_cursor": ...}
# ---------------------------------------------------------------------------


class TestLiveApiEnvelope:
    """The prod API returns ``{"items": ..., "next_cursor": ...}`` rather than
    the SDK-documented ``{"data": ..., "next": ...}``. Both shapes must flow
    through ``_list`` / ``_iter_all`` transparently.
    """

    def test_list_accepts_items_envelope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things").mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"id": "t1"}, {"id": "t2"}], "next_cursor": None},
            )
        )
        assert _Things(sync_client).list() == [{"id": "t1"}, {"id": "t2"}]

    def test_list_prefers_data_over_items_when_both_present(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """When both keys are present, ``data`` wins — it's the SDK's canonical
        contract and every unit fixture uses it. ``items`` is a real-API
        fallback only."""
        respx_mock.get("/things").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "canonical"}], "items": [{"id": "fallback"}]},
            )
        )
        assert _Things(sync_client).list() == [{"id": "canonical"}]

    def test_iter_all_paginates_with_next_cursor_envelope(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(200, json={"items": [{"id": "t2"}], "next_cursor": None})
        )
        respx_mock.get("/things", params={}).mock(
            return_value=httpx.Response(200, json={"items": [{"id": "t1"}], "next_cursor": "tok2"})
        )
        assert list(_Things(sync_client).iter_all()) == [{"id": "t1"}, {"id": "t2"}]

    async def test_async_list_accepts_items_envelope(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things").mock(
            return_value=httpx.Response(200, json={"items": [{"id": "t1"}], "next_cursor": None})
        )
        assert await _AsyncThings(async_client).list() == [{"id": "t1"}]

    async def test_async_iter_all_paginates_with_next_cursor_envelope(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/things", params={"cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"items": [{"id": "b"}], "next_cursor": None})
        )
        respx_mock.get("/things", params={}).mock(
            return_value=httpx.Response(200, json={"items": [{"id": "a"}], "next_cursor": "n2"})
        )
        collected: list[dict[str, Any]] = []
        async for item in _AsyncThings(async_client).iter_all():
            collected.append(item)
        assert collected == [{"id": "a"}, {"id": "b"}]
