"""TDD tests for :mod:`cerberus_compliance.resources.graph`.

Covers :class:`GraphResource` and :class:`AsyncGraphResource`: the
``ego_network`` / ``shortest_path`` / ``node_centrality`` /
``centrality_distribution`` / ``centrality_batch`` / ``edge_detail`` /
``edge_transactions`` / ``nodes_attrs`` surface — route + query/body
correctness, path-segment percent-encoding, and propagation of API
errors (404 not-found, 422 validation).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from cerberus_compliance.client import AsyncCerberusClient, CerberusClient
from cerberus_compliance.errors import NotFoundError, ValidationError
from cerberus_compliance.resources.graph import AsyncGraphResource, GraphResource

# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestSyncGraphResource:
    # ------------------------------------------------------------------
    # ego_network — GET /graph/{rut}
    # ------------------------------------------------------------------

    def test_ego_network_no_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/graph/76123456-7").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "76123456-7",
                    "group_id": None,
                    "node_type": "company",
                    "depth": 1,
                    "edges": [],
                    "total_edges": 0,
                    "has_more": False,
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.ego_network("76123456-7")
        assert out["rut"] == "76123456-7"
        assert out["edges"] == []
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_ego_network_all_params(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/graph/76123456-7",
            params={
                "depth": "2",
                "edge_types": "DIRECTS,CONTROLS",
                "active_only": "true",
                "limit": "500",
            },
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "76123456-7",
                    "group_id": None,
                    "node_type": "company",
                    "depth": 2,
                    "edges": [{"id": "e1"}],
                    "total_edges": 1,
                    "has_more": False,
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.ego_network(
            "76123456-7",
            depth=2,
            edge_types="DIRECTS,CONTROLS",
            active_only=True,
            limit=500,
        )
        assert out["total_edges"] == 1
        assert route.called

    def test_ego_network_group_seed(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/graph/296").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": None,
                    "group_id": "296",
                    "node_type": "group",
                    "depth": 1,
                    "edges": [],
                    "total_edges": 0,
                    "has_more": False,
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.ego_network("296")
        assert out["group_id"] == "296"
        assert out["node_type"] == "group"

    def test_ego_network_percent_encodes_rut(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/graph/..%2Fadmin").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = GraphResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.ego_network("../admin")
        assert route.called

    def test_ego_network_unparseable_raises_422(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/graph/not-a-rut").mock(
            return_value=httpx.Response(
                422,
                json={"title": "Unprocessable Entity", "status": 422},
            )
        )
        resource = GraphResource(sync_client)
        with pytest.raises(ValidationError) as exc_info:
            resource.ego_network("not-a-rut")
        assert exc_info.value.status == 422

    # ------------------------------------------------------------------
    # shortest_path — GET /graph/path
    # ------------------------------------------------------------------

    def test_shortest_path_happy(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/graph/path",
            params={"from_rut": "76123456-7", "to_rut": "96505760-9"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "from_rut": "76123456-7",
                    "to_rut": "96505760-9",
                    "path": [{"id": "e1"}, {"id": "e2"}],
                    "hop_count": 2,
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.shortest_path(from_rut="76123456-7", to_rut="96505760-9")
        assert out["hop_count"] == 2
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"from_rut": "76123456-7", "to_rut": "96505760-9"}

    def test_shortest_path_no_path_raises_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/graph/path").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = GraphResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.shortest_path(from_rut="76123456-7", to_rut="99999999-9")

    # ------------------------------------------------------------------
    # node_centrality — GET /graph/{rut}/centrality
    # ------------------------------------------------------------------

    def test_node_centrality_no_node_type(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/graph/76123456-7/centrality").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "76123456-7",
                    "node_type": "company",
                    "degree": 12,
                    "weighted_degree": 30.5,
                    "pagerank": 0.0123,
                    "pagerank_rank": 42,
                    "degree_rank": 17,
                    "total_nodes": 1000,
                    "pagerank_percentile": 95.8,
                    "degree_percentile": 98.3,
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.node_centrality("76123456-7")
        assert out["degree"] == 12
        assert route.called
        assert route.calls.last.request.url.query == b""

    def test_node_centrality_with_node_type(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/graph/76123456-7/centrality",
            params={"node_type": "person"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "76123456-7",
                    "node_type": "person",
                    "degree": 3,
                    "weighted_degree": 3.0,
                    "pagerank": 0.0001,
                    "pagerank_rank": 900,
                    "degree_rank": 800,
                    "total_nodes": 1000,
                    "pagerank_percentile": 10.0,
                    "degree_percentile": 20.0,
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.node_centrality("76123456-7", node_type="person")
        assert out["node_type"] == "person"
        assert route.called

    def test_node_centrality_not_a_node_raises_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/graph/76123456-7/centrality").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = GraphResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.node_centrality("76123456-7")

    # ------------------------------------------------------------------
    # centrality_distribution — GET /graph/centrality/distribution
    # ------------------------------------------------------------------

    def test_centrality_distribution(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "total_nodes": 1000,
            "total_edges": 5000,
            "degree_histogram": [{"lower": 0.0, "upper": 5.0, "count": 800}],
            "pagerank_histogram": [{"lower": 0.0, "upper": 0.1, "count": 990}],
            "degree_min": 1,
            "degree_median": 4.0,
            "degree_p90": 12.0,
            "degree_max": 250,
        }
        route = respx_mock.get("/graph/centrality/distribution").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = GraphResource(sync_client)
        out = resource.centrality_distribution()
        assert out == body
        assert route.called

    # ------------------------------------------------------------------
    # centrality_batch — POST /graph/centrality/batch
    # ------------------------------------------------------------------

    def test_centrality_batch_posts_ruts_body(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/graph/centrality/batch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "nodes": [{"rut": "76123456-7", "degree": 5}],
                    "requested": 2,
                    "resolved": 1,
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.centrality_batch(["76123456-7", "96505760-9"])
        assert out["requested"] == 2
        assert out["resolved"] == 1
        assert route.called
        import json as _json

        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"ruts": ["76123456-7", "96505760-9"]}

    def test_centrality_batch_over_cap_raises_422(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/graph/centrality/batch").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = GraphResource(sync_client)
        with pytest.raises(ValidationError):
            resource.centrality_batch([f"7612345{i}-7" for i in range(201)])

    # ------------------------------------------------------------------
    # edge_detail — GET /graph/edge/{edge_id}/detail
    # ------------------------------------------------------------------

    def test_edge_detail_happy(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        edge_id = "11111111-1111-1111-1111-111111111111"
        route = respx_mock.get(f"/graph/edge/{edge_id}/detail").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": edge_id,
                    "edge_type": "INTERLOCKS_WITH",
                    "detail_kind": "interlocks",
                    "src_rut": "76123456-7",
                    "dst_rut": "96505760-9",
                    "src_name": "Acme",
                    "dst_name": "Falabella",
                    "shared_directors": [
                        {
                            "persona_nombre": "Jane Doe",
                            "cargo_src": "Director",
                            "cargo_dst": "Director",
                            "vigente": True,
                            "desde": "2020-01-01",
                            "hasta": None,
                        }
                    ],
                    "interlock_window": {"desde": "2020-01-01", "hasta": None},
                    "directs": None,
                    "metadata": {},
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.edge_detail(edge_id)
        assert out["detail_kind"] == "interlocks"
        assert out["shared_directors"][0]["persona_nombre"] == "Jane Doe"
        assert route.called

    def test_edge_detail_not_found_raises_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        edge_id = "22222222-2222-2222-2222-222222222222"
        respx_mock.get(f"/graph/edge/{edge_id}/detail").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = GraphResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.edge_detail(edge_id)

    def test_edge_detail_percent_encodes_edge_id(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/graph/edge/..%2Fadmin/detail").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = GraphResource(sync_client)
        with pytest.raises(ValidationError):
            resource.edge_detail("../admin")
        assert route.called

    # ------------------------------------------------------------------
    # edge_transactions — GET /graph/edge/{edge_id}/transactions
    # ------------------------------------------------------------------

    def test_edge_transactions_happy(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        edge_id = "33333333-3333-3333-3333-333333333333"
        route = respx_mock.get(
            f"/graph/edge/{edge_id}/transactions",
            params={"src_rut": "12345678-5", "dst_rut": "96505760-9"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "src_rut": "12345678-5",
                    "dst_rut": "96505760-9",
                    "src_name": "Jane Doe",
                    "dst_name": "Falabella",
                    "tx_count": 1,
                    "transactions": [
                        {"fecha": "2026-01-15", "tipo_operacion": "compra", "monto_clp": 1000.0}
                    ],
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.edge_transactions(edge_id, src_rut="12345678-5", dst_rut="96505760-9")
        assert out["tx_count"] == 1
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"src_rut": "12345678-5", "dst_rut": "96505760-9"}

    def test_edge_transactions_mismatch_raises_404(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        edge_id = "44444444-4444-4444-4444-444444444444"
        respx_mock.get(f"/graph/edge/{edge_id}/transactions").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = GraphResource(sync_client)
        with pytest.raises(NotFoundError):
            resource.edge_transactions(edge_id, src_rut="12345678-5", dst_rut="96505760-9")

    # ------------------------------------------------------------------
    # nodes_attrs — POST /graph/nodes/attrs
    # ------------------------------------------------------------------

    def test_nodes_attrs_posts_ruts_body(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/graph/nodes/attrs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "nodes": [
                        {
                            "rut": "76123456-7",
                            "sector_label": "Retail",
                            "sanctioned": False,
                            "active_sanctions_count": 0,
                            "board_pep_lite_count": 1,
                            "rating_band": "investment_grade",
                            "ticker": "FALAB",
                        }
                    ],
                    "requested": 1,
                    "resolved": 1,
                },
            )
        )
        resource = GraphResource(sync_client)
        out = resource.nodes_attrs(["76123456-7"])
        assert out["nodes"][0]["rating_band"] == "investment_grade"
        assert route.called
        import json as _json

        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"ruts": ["76123456-7"]}

    def test_nodes_attrs_over_cap_raises_422(
        self, sync_client: CerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/graph/nodes/attrs").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = GraphResource(sync_client)
        with pytest.raises(ValidationError):
            resource.nodes_attrs([f"7612345{i}-7" for i in range(201)])


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncGraphResource:
    async def test_ego_network_no_params(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/graph/76123456-7").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "76123456-7",
                    "group_id": None,
                    "node_type": "company",
                    "depth": 1,
                    "edges": [],
                    "total_edges": 0,
                    "has_more": False,
                },
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.ego_network("76123456-7")
        assert out["rut"] == "76123456-7"
        assert route.calls.last.request.url.query == b""

    async def test_ego_network_all_params(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/graph/76123456-7",
            params={
                "depth": "2",
                "edge_types": "CONTROLS",
                "active_only": "false",
                "limit": "10",
            },
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "76123456-7",
                    "group_id": None,
                    "node_type": "company",
                    "depth": 2,
                    "edges": [],
                    "total_edges": 0,
                    "has_more": False,
                },
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.ego_network(
            "76123456-7",
            depth=2,
            edge_types="CONTROLS",
            active_only=False,
            limit=10,
        )
        assert out["depth"] == 2
        assert route.called

    async def test_ego_network_unparseable_raises_422(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/graph/not-a-rut").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = AsyncGraphResource(async_client)
        with pytest.raises(ValidationError):
            await resource.ego_network("not-a-rut")

    async def test_shortest_path_happy(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/graph/path",
            params={"from_rut": "76123456-7", "to_rut": "96505760-9"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "from_rut": "76123456-7",
                    "to_rut": "96505760-9",
                    "path": [{"id": "e1"}],
                    "hop_count": 1,
                },
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.shortest_path(from_rut="76123456-7", to_rut="96505760-9")
        assert out["hop_count"] == 1
        assert route.called

    async def test_shortest_path_no_path_raises_404(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get("/graph/path").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncGraphResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.shortest_path(from_rut="76123456-7", to_rut="99999999-9")

    async def test_node_centrality_no_node_type(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get("/graph/76123456-7/centrality").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "76123456-7",
                    "node_type": "company",
                    "degree": 12,
                    "weighted_degree": 30.5,
                    "pagerank": 0.0123,
                    "pagerank_rank": 42,
                    "degree_rank": 17,
                    "total_nodes": 1000,
                    "pagerank_percentile": 95.8,
                    "degree_percentile": 98.3,
                },
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.node_centrality("76123456-7")
        assert out["degree"] == 12
        assert route.calls.last.request.url.query == b""

    async def test_node_centrality_with_node_type(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.get(
            "/graph/76123456-7/centrality",
            params={"node_type": "group"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "rut": "76123456-7",
                    "node_type": "group",
                    "degree": 1,
                    "weighted_degree": 1.0,
                    "pagerank": 0.0,
                    "pagerank_rank": 1,
                    "degree_rank": 1,
                    "total_nodes": 1,
                    "pagerank_percentile": 100.0,
                    "degree_percentile": 100.0,
                },
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.node_centrality("76123456-7", node_type="group")
        assert out["node_type"] == "group"
        assert route.called

    async def test_centrality_distribution(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        body = {
            "total_nodes": 0,
            "total_edges": 0,
            "degree_histogram": [],
            "pagerank_histogram": [],
            "degree_min": 0,
            "degree_median": 0.0,
            "degree_p90": 0.0,
            "degree_max": 0,
        }
        respx_mock.get("/graph/centrality/distribution").mock(
            return_value=httpx.Response(200, json=body)
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.centrality_distribution()
        assert out == body

    async def test_centrality_batch_posts_ruts_body(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/graph/centrality/batch").mock(
            return_value=httpx.Response(
                200,
                json={"nodes": [], "requested": 1, "resolved": 0},
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.centrality_batch(["76123456-7"])
        assert out["resolved"] == 0
        import json as _json

        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"ruts": ["76123456-7"]}

    async def test_centrality_batch_over_cap_raises_422(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/graph/centrality/batch").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = AsyncGraphResource(async_client)
        with pytest.raises(ValidationError):
            await resource.centrality_batch([f"7612345{i}-7" for i in range(201)])

    async def test_edge_detail_happy(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        edge_id = "55555555-5555-5555-5555-555555555555"
        respx_mock.get(f"/graph/edge/{edge_id}/detail").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": edge_id,
                    "edge_type": "DIRECTS",
                    "detail_kind": "directs",
                    "src_rut": "12345678-5",
                    "dst_rut": "96505760-9",
                    "src_name": "Jane",
                    "dst_name": "Falabella",
                    "shared_directors": [],
                    "interlock_window": None,
                    "directs": {
                        "cargo": "Presidente",
                        "fecha_inicio": "2021-01-01",
                        "fecha_fin": None,
                    },
                    "metadata": {},
                },
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.edge_detail(edge_id)
        assert out["detail_kind"] == "directs"
        assert out["directs"]["cargo"] == "Presidente"

    async def test_edge_detail_not_found_raises_404(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        edge_id = "66666666-6666-6666-6666-666666666666"
        respx_mock.get(f"/graph/edge/{edge_id}/detail").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncGraphResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.edge_detail(edge_id)

    async def test_edge_transactions_happy(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        edge_id = "77777777-7777-7777-7777-777777777777"
        route = respx_mock.get(
            f"/graph/edge/{edge_id}/transactions",
            params={"src_rut": "12345678-5", "dst_rut": "96505760-9"},
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "src_rut": "12345678-5",
                    "dst_rut": "96505760-9",
                    "src_name": "Jane",
                    "dst_name": "Falabella",
                    "tx_count": 0,
                    "transactions": [],
                },
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.edge_transactions(edge_id, src_rut="12345678-5", dst_rut="96505760-9")
        assert out["tx_count"] == 0
        assert route.called
        params = dict(route.calls.last.request.url.params.multi_items())
        assert params == {"src_rut": "12345678-5", "dst_rut": "96505760-9"}

    async def test_edge_transactions_mismatch_raises_404(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        edge_id = "88888888-8888-8888-8888-888888888888"
        respx_mock.get(f"/graph/edge/{edge_id}/transactions").mock(
            return_value=httpx.Response(404, json={"title": "Not Found", "status": 404})
        )
        resource = AsyncGraphResource(async_client)
        with pytest.raises(NotFoundError):
            await resource.edge_transactions(edge_id, src_rut="12345678-5", dst_rut="96505760-9")

    async def test_nodes_attrs_posts_ruts_body(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        route = respx_mock.post("/graph/nodes/attrs").mock(
            return_value=httpx.Response(
                200,
                json={"nodes": [], "requested": 2, "resolved": 0},
            )
        )
        resource = AsyncGraphResource(async_client)
        out = await resource.nodes_attrs(["76123456-7", "96505760-9"])
        assert out["requested"] == 2
        import json as _json

        sent = _json.loads(route.calls.last.request.content)
        assert sent == {"ruts": ["76123456-7", "96505760-9"]}

    async def test_nodes_attrs_over_cap_raises_422(
        self, async_client: AsyncCerberusClient, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.post("/graph/nodes/attrs").mock(
            return_value=httpx.Response(422, json={"title": "Unprocessable", "status": 422})
        )
        resource = AsyncGraphResource(async_client)
        with pytest.raises(ValidationError):
            await resource.nodes_attrs([f"7612345{i}-7" for i in range(201)])
