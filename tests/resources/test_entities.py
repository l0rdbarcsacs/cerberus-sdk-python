"""TDD tests for :mod:`cerberus_compliance.resources.entities`.

Covers :class:`EntitiesResource` and :class:`AsyncEntitiesResource`: the
``list`` / ``get`` / ``material_events`` / ``sanctions`` / ``directors``
/ ``regulations`` / ``iter_all`` surface, defensive envelope handling on
the nested-list endpoints, and propagation of API errors.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import CerberusAPIError, RateLimitError
from cerberus_compliance.resources.entities import AsyncEntitiesResource, EntitiesResource
from cerberus_compliance.retry import RetryConfig

# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestSyncEntitiesResource:
    def test_list_no_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "e1"}, {"id": "e2"}], "next": None},
            )
        )
        resource = EntitiesResource(sync_client)
        assert resource.list() == [{"id": "e1"}, {"id": "e2"}]
        assert route.called

    def test_list_with_rut(self, sync_client: CerberusClient, respx_mock: respx.MockRouter) -> None:
        route = respx_mock.get("/entities", params={"rut": "76123456-7"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "e1"}], "next": None})
        )
        resource = EntitiesResource(sync_client)
        assert resource.list(rut="76123456-7") == [{"id": "e1"}]
        assert route.called

    def test_list_with_limit(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities", params={"limit": "25"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "e9"}], "next": None})
        )
        resource = EntitiesResource(sync_client)
        assert resource.list(limit=25) == [{"id": "e9"}]
        assert route.called

    def test_list_with_all_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities", params={"rut": "76123456-7", "limit": "10"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "eZ"}], "next": None})
        )
        resource = EntitiesResource(sync_client)
        assert resource.list(rut="76123456-7", limit=10) == [{"id": "eZ"}]
        assert route.called

    def test_get_returns_entity(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7").mock(
            return_value=httpx.Response(200, json={"id": "76123456-7", "name": "Acme SpA"})
        )
        resource = EntitiesResource(sync_client)
        assert resource.get("76123456-7") == {"id": "76123456-7", "name": "Acme SpA"}

    def test_material_events_happy_path(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/material-events").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "me1"}, {"id": "me2"}]},
            )
        )
        resource = EntitiesResource(sync_client)
        assert resource.material_events("76123456-7") == [{"id": "me1"}, {"id": "me2"}]

    def test_material_events_missing_data_returns_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/material-events").mock(
            return_value=httpx.Response(200, json={})
        )
        resource = EntitiesResource(sync_client)
        assert resource.material_events("76123456-7") == []

    def test_material_events_data_not_list_returns_empty(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/material-events").mock(
            return_value=httpx.Response(200, json={"data": "oops"})
        )
        resource = EntitiesResource(sync_client)
        assert resource.material_events("76123456-7") == []

    def test_material_events_drops_non_dict_items(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/material-events").mock(
            return_value=httpx.Response(200, json={"data": [{"ok": 1}, "bad", 42]})
        )
        resource = EntitiesResource(sync_client)
        assert resource.material_events("76123456-7") == [{"ok": 1}]

    def test_sanctions_happy_path_hits_by_entity_endpoint(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """G2: sanctions(id_) must hit /sanctions/by-entity/{id_}, NOT
        /entities/{id}/sanctions. The old path was fictional — see CHANGELOG v0.2.0.
        """
        route = respx_mock.get("/sanctions/by-entity/76123456-7").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "s1"}]})
        )
        resource = EntitiesResource(sync_client)
        assert resource.sanctions("76123456-7") == [{"id": "s1"}]
        assert route.called
        # Sanity: the old path must NOT be the one hit.
        assert "/entities/76123456-7/sanctions" not in str(route.calls.last.request.url.path)

    def test_directors_happy_path(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/directors").mock(
            return_value=httpx.Response(200, json={"data": [{"name": "Jane"}, {"name": "John"}]})
        )
        resource = EntitiesResource(sync_client)
        assert resource.directors("76123456-7") == [
            {"name": "Jane"},
            {"name": "John"},
        ]

    def test_regulations_happy_path(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/regulations").mock(
            return_value=httpx.Response(200, json={"data": [{"code": "CMF-001"}]})
        )
        resource = EntitiesResource(sync_client)
        assert resource.regulations("76123456-7") == [{"code": "CMF-001"}]

    def test_iter_all_no_filters_paginates_two_pages(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        # Specific (cursor) route registered FIRST so the dispatcher hits
        # it before the bare subset match.
        page2 = respx_mock.get("/entities", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "e2"}], "next": None})
        )
        page1 = respx_mock.get("/entities", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "e1"}], "next": "tok2"})
        )
        resource = EntitiesResource(sync_client)
        items = list(resource.iter_all())
        assert items == [{"id": "e1"}, {"id": "e2"}]
        assert page1.called
        assert page2.called

    def test_iter_all_forwards_filters(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        page2 = respx_mock.get("/entities", params={"rut": "76123456-7", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        page1 = respx_mock.get("/entities", params={"rut": "76123456-7"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "n2"})
        )
        resource = EntitiesResource(sync_client)
        items = list(resource.iter_all(rut="76123456-7"))
        assert items == [{"id": "a"}, {"id": "b"}]
        assert page1.called
        assert page2.called

    def test_get_propagates_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/missing").mock(
            return_value=httpx.Response(
                404,
                json={
                    "type": "about:blank",
                    "title": "Not Found",
                    "status": 404,
                    "detail": "Entity missing",
                },
            )
        )
        resource = EntitiesResource(sync_client)
        with pytest.raises(CerberusAPIError) as exc_info:
            resource.get("missing")
        assert exc_info.value.status == 404

    def test_get_propagates_429(
        self, api_key: str, base_url: str, respx_mock: respx.MockRouter
    ) -> None:
        # One-off client with no retries so the 429 surfaces without delay.
        client = CerberusClient(
            api_key=api_key,
            base_url=base_url,
            timeout=2.0,
            retry=RetryConfig(max_attempts=1, base_delay_ms=1),
        )
        try:
            respx_mock.get("/entities/rate-limited").mock(
                return_value=httpx.Response(
                    429,
                    headers={"retry-after": "1"},
                    json={"title": "Too Many Requests", "status": 429},
                )
            )
            resource = EntitiesResource(client)
            with pytest.raises(RateLimitError):
                resource.get("rate-limited")
        finally:
            client.close()

    # ------------------------------------------------------------------
    # Path-traversal hardening (OWASP A01)
    # ------------------------------------------------------------------

    def test_path_traversal_id_is_percent_encoded(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """User-supplied id_ containing '../' must be percent-encoded, not traversed.

        Post-G2 fix the target path is now /sanctions/by-entity/{id}; the id
        segment must still be percent-encoded to avoid traversal.
        """
        route = respx_mock.get("/sanctions/by-entity/..%2Fadmin").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        resource = EntitiesResource(sync_client)
        result = resource.sanctions("../admin")
        assert result == []
        assert route.called

    # ------------------------------------------------------------------
    # G12 — by_rut
    # ------------------------------------------------------------------

    def test_by_rut_dotted_form(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """by_rut must percent-encode the RUT so dots survive round-trip."""
        route = respx_mock.get("/entities/by-rut/96.505.760-9").mock(
            return_value=httpx.Response(
                200,
                json={"id": "ent_1", "rut": "96.505.760-9", "legal_name": "Falabella"},
            )
        )
        resource = EntitiesResource(sync_client)
        result = resource.by_rut("96.505.760-9")
        assert result == {"id": "ent_1", "rut": "96.505.760-9", "legal_name": "Falabella"}
        assert route.called

    def test_by_rut_plain_form(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/by-rut/96505760-9").mock(
            return_value=httpx.Response(200, json={"id": "ent_1"})
        )
        resource = EntitiesResource(sync_client)
        assert resource.by_rut("96505760-9") == {"id": "ent_1"}
        assert route.called

    def test_by_rut_path_traversal_hardened(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/by-rut/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = EntitiesResource(sync_client)
        from cerberus_compliance.errors import NotFoundError

        with pytest.raises(NotFoundError):
            resource.by_rut("../admin")
        assert route.called

    # ------------------------------------------------------------------
    # G13 — ownership
    # ------------------------------------------------------------------

    def test_ownership_returns_aggregate(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/ent_1/ownership").mock(
            return_value=httpx.Response(
                200,
                json={
                    "entity_id": "ent_1",
                    "shareholders": [{"name": "Holding X", "pct": 55.0}],
                    "ubo_chain": [{"depth": 1, "name": "Foo"}],
                },
            )
        )
        resource = EntitiesResource(sync_client)
        result = resource.ownership("ent_1")
        assert result["entity_id"] == "ent_1"
        assert len(result["shareholders"]) == 1
        assert route.called

    def test_ownership_percent_encodes_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/entities/..%2Fadmin/ownership").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = EntitiesResource(sync_client)
        from cerberus_compliance.errors import NotFoundError

        with pytest.raises(NotFoundError):
            resource.ownership("../admin")
        assert route.called


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncEntitiesResource:
    async def test_async_list_returns_data(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities", params={"rut": "76123456-7"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "e1"}], "next": None})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.list(rut="76123456-7") == [{"id": "e1"}]

    async def test_async_list_with_all_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities", params={"rut": "76123456-7", "limit": "5"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "eZ"}], "next": None})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.list(rut="76123456-7", limit=5) == [{"id": "eZ"}]

    async def test_async_list_no_params(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "e0"}], "next": None})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.list() == [{"id": "e0"}]

    async def test_async_get_returns_entity(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7").mock(
            return_value=httpx.Response(200, json={"id": "76123456-7"})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.get("76123456-7") == {"id": "76123456-7"}

    async def test_async_material_events_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/material-events").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "me1"}]})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.material_events("76123456-7") == [{"id": "me1"}]

    async def test_async_material_events_missing_data_returns_empty(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/material-events").mock(
            return_value=httpx.Response(200, json={})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.material_events("76123456-7") == []

    async def test_async_sanctions_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/sanctions/by-entity/76123456-7").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "s1"}, "skip-me", 99]})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.sanctions("76123456-7") == [{"id": "s1"}]

    async def test_async_directors_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/directors").mock(
            return_value=httpx.Response(200, json={"data": [{"name": "Jane"}]})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.directors("76123456-7") == [{"name": "Jane"}]

    async def test_async_regulations_happy_path(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/76123456-7/regulations").mock(
            return_value=httpx.Response(200, json={"data": "not-a-list"})
        )
        resource = AsyncEntitiesResource(async_client)
        assert await resource.regulations("76123456-7") == []

    async def test_async_iter_all_paginates(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities", params={"cursor": "tok2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 2}], "next": None})
        )
        respx_mock.get("/entities", params={}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": 1}], "next": "tok2"})
        )
        resource = AsyncEntitiesResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all():
            collected.append(item)
        assert collected == [{"id": 1}, {"id": 2}]

    async def test_async_iter_all_forwards_filters(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities", params={"rut": "76123456-7", "cursor": "n2"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "b"}], "next": None})
        )
        respx_mock.get("/entities", params={"rut": "76123456-7"}).mock(
            return_value=httpx.Response(200, json={"data": [{"id": "a"}], "next": "n2"})
        )
        resource = AsyncEntitiesResource(async_client)
        collected: list[dict[str, Any]] = []
        async for item in resource.iter_all(rut="76123456-7"):
            collected.append(item)
        assert collected == [{"id": "a"}, {"id": "b"}]

    # ------------------------------------------------------------------
    # Path-traversal hardening (OWASP A01)
    # ------------------------------------------------------------------

    async def test_path_traversal_id_is_percent_encoded(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        """User-supplied id_ containing '../' must be percent-encoded, not traversed."""
        route = respx_mock.get("/entities/..%2Fadmin/material-events").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        resource = AsyncEntitiesResource(async_client)
        result = await resource.material_events("../admin")
        assert result == []
        assert route.called

    # ------------------------------------------------------------------
    # G12/G13 — async by_rut + ownership mirrors
    # ------------------------------------------------------------------

    async def test_async_by_rut(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/by-rut/96.505.760-9").mock(
            return_value=httpx.Response(200, json={"id": "ent_1", "rut": "96.505.760-9"})
        )
        resource = AsyncEntitiesResource(async_client)
        result = await resource.by_rut("96.505.760-9")
        assert result == {"id": "ent_1", "rut": "96.505.760-9"}

    async def test_async_ownership(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/entities/ent_1/ownership").mock(
            return_value=httpx.Response(200, json={"entity_id": "ent_1", "shareholders": []})
        )
        resource = AsyncEntitiesResource(async_client)
        result = await resource.ownership("ent_1")
        assert result["entity_id"] == "ent_1"
