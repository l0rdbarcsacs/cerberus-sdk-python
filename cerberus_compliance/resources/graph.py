"""Typed accessors for the Cerberus Compliance ``/graph`` resource.

The graph resource surfaces the materialized entity knowledge graph
(``graph_edges`` + ``graph_node_metrics``): ego-networks around a RUT or
group seed, shortest paths between two RUTs, per-node and batch
centrality, edge detail / transaction drill-downs, and a batch
lens-attribute fan-in. It also exposes the public anonymised centrality
distribution.

This module exposes the synchronous :class:`GraphResource` and its
asynchronous mirror :class:`AsyncGraphResource`; both delegate to the
shared base classes in :mod:`cerberus_compliance.resources._base`.

Every endpoint returns a single aggregate object (not a paginated list
envelope), so each method issues a direct ``_request`` and returns the
JSON body verbatim. Path segments (``rut``, ``edge_id``) are
percent-encoded with :func:`~cerberus_compliance.resources._base._encode_id`
so dotted RUT forms and ``../`` traversal attempts survive / are
neutralised on the wire. Server-side caps (e.g. the 200-RUT batch limit,
``limit`` ge/le bounds) are NOT validated client-side — they surface as
``422`` responses.
"""

from __future__ import annotations

from typing import Any, Literal

from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

__all__ = ["AsyncGraphResource", "GraphResource"]

# GraphNodeType enum values (lowercase Python enum value strings).
GraphNodeType = Literal["company", "person", "group"]

_PREFIX = "/graph"


class GraphResource(BaseResource):
    """Synchronous accessor for the ``/graph`` endpoint family."""

    _path_prefix = _PREFIX

    def ego_network(
        self,
        rut: str,
        *,
        depth: int | None = None,
        edge_types: str | None = None,
        active_only: bool | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return the ego-network around *rut* (``GET /graph/{rut}``).

        The ``rut`` path segment accepts any RUT format OR a bare
        ``group_id`` (e.g. ``"296"``): a known group id resolves as a
        GROUP seed first, otherwise the value is canonicalized as a RUT.
        Unparseable-and-not-a-group input returns ``422``; an empty graph
        returns ``200`` with ``edges=[]`` (never ``404``).

        Args:
            rut: RUT (any format) or a bare ``group_id`` seed.
            depth: Hop depth (server-validated ``ge=1, le=2``). Omit for
                the default of ``1``.
            edge_types: Comma-separated, case-insensitive edge-type filter
                (e.g. ``"DIRECTS,CONTROLS"``). Unknown tokens are dropped
                server-side. Omit for all types.
            active_only: When ``True``, only edges with ``valid_to`` NULL
                or ``>=`` today (UTC).
            limit: Cap returned edges (server-validated ``ge=1, le=2000``).
                Omit to return all; inspect ``total_edges`` / ``has_more``
                to detect truncation.

        Returns:
            ``{"rut", "group_id", "node_type", "depth", "edges",
            "total_edges", "has_more"}``.
        """
        params: dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        if edge_types is not None:
            params["edge_types"] = edge_types
        if active_only is not None:
            params["active_only"] = active_only
        if limit is not None:
            params["limit"] = limit
        path = f"{self._path_prefix}/{_encode_id(rut)}"
        return self._client._request("GET", path, params=params or None)

    def shortest_path(self, *, from_rut: str, to_rut: str) -> dict[str, Any]:
        """Return the shortest path between two RUTs (``GET /graph/path``).

        Shortest path via BFS over ``graph_edges`` (max depth 4). No path
        within the depth cap returns ``404``; unparseable RUTs return
        ``422``. The wire query aliases are literally ``from_rut`` /
        ``to_rut``.

        Args:
            from_rut: Source RUT, any format (canonicalized server-side).
            to_rut: Destination RUT, any format (canonicalized
                server-side).

        Returns:
            ``{"from_rut", "to_rut", "path", "hop_count"}`` where ``path``
            is the ordered list of edges and ``hop_count == len(path)``.
        """
        params: dict[str, Any] = {"from_rut": from_rut, "to_rut": to_rut}
        return self._client._request("GET", f"{self._path_prefix}/path", params=params)

    def node_centrality(
        self,
        rut: str,
        *,
        node_type: GraphNodeType | None = None,
    ) -> dict[str, Any]:
        """Return materialized centrality metrics for *rut*.

        Issues ``GET /graph/{rut}/centrality``, reading
        ``graph_node_metrics`` (populated by the ``graph_centrality_batch``
        job). A RUT that is not a node in the materialized graph returns
        ``404``; an unparseable RUT returns ``422``.

        Args:
            rut: RUT, any format.
            node_type: ``company`` / ``person`` / ``group`` to
                disambiguate a RUT that is both a company and a person.
                Omit to default to the company row on a collision.

        Returns:
            ``{"rut", "node_type", "degree", "weighted_degree",
            "pagerank", "pagerank_rank", "degree_rank", "total_nodes",
            "pagerank_percentile", "degree_percentile"}``.
        """
        params: dict[str, Any] = {}
        if node_type is not None:
            params["node_type"] = node_type
        path = f"{self._path_prefix}/{_encode_id(rut)}/centrality"
        return self._client._request("GET", path, params=params or None)

    def centrality_distribution(self) -> dict[str, Any]:
        """Return the public anonymised centrality distribution.

        Issues ``GET /graph/centrality/distribution``. This endpoint uses
        the ``entities:read`` scope (NOT ``graph:read``) and exposes only
        anonymised histograms — no names, RUTs, or per-named values. It
        always returns ``200`` (no ``404``).

        Returns:
            ``{"total_nodes", "total_edges", "degree_histogram",
            "pagerank_histogram", "degree_min", "degree_median",
            "degree_p90", "degree_max"}`` where each histogram bucket is
            ``{"lower", "upper", "count"}``.
        """
        return self._client._request("GET", f"{self._path_prefix}/centrality/distribution")

    def centrality_batch(self, ruts: list[str]) -> dict[str, Any]:
        """Batch centrality lookup (``POST /graph/centrality/batch``).

        Fan-in replacement for N single-RUT centrality lookups. RUTs are
        canonicalized + deduped server-side; the deduped set is capped at
        200 (``>200`` returns ``422``). Unparseable / unknown RUTs are
        silently omitted (no partial ``404`` / ``422``). The cap is
        enforced server-side and is NOT validated client-side.

        Args:
            ruts: RUTs in any format. Counts as ONE quota request.

        Returns:
            ``{"nodes", "requested", "resolved"}`` where each node has the
            same shape as :meth:`node_centrality`; ``requested`` is the
            distinct canonical RUT count and ``resolved`` the nodes
            returned (``<= requested``).
        """
        body: dict[str, Any] = {"ruts": ruts}
        return self._client._request("POST", f"{self._path_prefix}/centrality/batch", json=body)

    def edge_detail(self, edge_id: str) -> dict[str, Any]:
        """Return the detail bag for a persisted edge.

        Issues ``GET /graph/edge/{edge_id}/detail``. ``edge_id`` is a real
        persisted ``graph_edges`` UUID (NOT the synthetic aggregated
        ``TRANSACTS_IN`` id); a malformed UUID returns ``422`` and an
        unknown edge returns ``404``. ``detail_kind`` discriminates the
        shape (``interlocks`` / ``directs`` / ``other``).

        Args:
            edge_id: Persisted ``graph_edges`` UUID.

        Returns:
            ``{"id", "edge_type", "detail_kind", "src_rut", "dst_rut",
            "src_name", "dst_name", "shared_directors", "interlock_window",
            "directs", "metadata"}``.
        """
        path = f"{self._path_prefix}/edge/{_encode_id(edge_id)}/detail"
        return self._client._request("GET", path)

    def edge_transactions(
        self,
        edge_id: str,
        *,
        src_rut: str,
        dst_rut: str,
    ) -> dict[str, Any]:
        """Drill down into a synthetic aggregated ``TRANSACTS_IN`` edge.

        Issues ``GET /graph/edge/{edge_id}/transactions``. The aggregated
        edge is in-memory (not a ``graph_edges`` row), so the
        ``(src_rut, dst_rut)`` pair is passed as query params. As an
        anti-enumeration guard, ``edge_id`` is validated against the
        ``uuid5`` of the resolved person/company keys; any mismatch,
        unparseable RUT, or unresolvable person/company returns ``404``. A
        malformed UUID path param returns ``422``.

        ``TRANSACTS_IN`` is person -> emisor: ``src_rut`` is the PERSON,
        ``dst_rut`` is the EMISOR company.

        Args:
            edge_id: Synthetic aggregated edge UUID.
            src_rut: Source PERSON RUT, any format.
            dst_rut: Destination EMISOR company RUT, any format.

        Returns:
            ``{"src_rut", "dst_rut", "src_name", "dst_name", "tx_count",
            "transactions"}`` where ``tx_count == len(transactions)``.
        """
        params: dict[str, Any] = {"src_rut": src_rut, "dst_rut": dst_rut}
        path = f"{self._path_prefix}/edge/{_encode_id(edge_id)}/transactions"
        return self._client._request("GET", path, params=params)

    def nodes_attrs(self, ruts: list[str]) -> dict[str, Any]:
        """Batch lens-attribute fan-in (``POST /graph/nodes/attrs``).

        Replaces per-node ``GET /v1/kyb``. RUTs are canonicalized +
        deduped server-side; the deduped set is capped at 200 (``>200``
        returns ``422``). Unparseable / unknown RUTs are silently omitted
        (no partial ``404`` / ``422``). The cap is enforced server-side
        and is NOT validated client-side.

        The result is PII-safe: ``rating_band`` is the coarse band only
        (``investment_grade`` / ``speculative`` / ``default`` /
        ``unknown``), never the raw rating, and no ``persona_rut`` is ever
        returned.

        Args:
            ruts: RUTs in any format. Counts as ONE quota request.

        Returns:
            ``{"nodes", "requested", "resolved"}`` where each node is
            ``{"rut", "sector_label", "sanctioned", "active_sanctions_count",
            "board_pep_lite_count", "rating_band", "ticker"}``.
        """
        body: dict[str, Any] = {"ruts": ruts}
        return self._client._request("POST", f"{self._path_prefix}/nodes/attrs", json=body)


class AsyncGraphResource(AsyncBaseResource):
    """Asynchronous accessor for the ``/graph`` endpoint family."""

    _path_prefix = _PREFIX

    async def ego_network(
        self,
        rut: str,
        *,
        depth: int | None = None,
        edge_types: str | None = None,
        active_only: bool | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`GraphResource.ego_network`."""
        params: dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        if edge_types is not None:
            params["edge_types"] = edge_types
        if active_only is not None:
            params["active_only"] = active_only
        if limit is not None:
            params["limit"] = limit
        path = f"{self._path_prefix}/{_encode_id(rut)}"
        return await self._client._request("GET", path, params=params or None)

    async def shortest_path(self, *, from_rut: str, to_rut: str) -> dict[str, Any]:
        """Async variant of :meth:`GraphResource.shortest_path`."""
        params: dict[str, Any] = {"from_rut": from_rut, "to_rut": to_rut}
        return await self._client._request("GET", f"{self._path_prefix}/path", params=params)

    async def node_centrality(
        self,
        rut: str,
        *,
        node_type: GraphNodeType | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`GraphResource.node_centrality`."""
        params: dict[str, Any] = {}
        if node_type is not None:
            params["node_type"] = node_type
        path = f"{self._path_prefix}/{_encode_id(rut)}/centrality"
        return await self._client._request("GET", path, params=params or None)

    async def centrality_distribution(self) -> dict[str, Any]:
        """Async variant of :meth:`GraphResource.centrality_distribution`."""
        return await self._client._request("GET", f"{self._path_prefix}/centrality/distribution")

    async def centrality_batch(self, ruts: list[str]) -> dict[str, Any]:
        """Async variant of :meth:`GraphResource.centrality_batch`."""
        body: dict[str, Any] = {"ruts": ruts}
        return await self._client._request(
            "POST", f"{self._path_prefix}/centrality/batch", json=body
        )

    async def edge_detail(self, edge_id: str) -> dict[str, Any]:
        """Async variant of :meth:`GraphResource.edge_detail`."""
        path = f"{self._path_prefix}/edge/{_encode_id(edge_id)}/detail"
        return await self._client._request("GET", path)

    async def edge_transactions(
        self,
        edge_id: str,
        *,
        src_rut: str,
        dst_rut: str,
    ) -> dict[str, Any]:
        """Async variant of :meth:`GraphResource.edge_transactions`."""
        params: dict[str, Any] = {"src_rut": src_rut, "dst_rut": dst_rut}
        path = f"{self._path_prefix}/edge/{_encode_id(edge_id)}/transactions"
        return await self._client._request("GET", path, params=params)

    async def nodes_attrs(self, ruts: list[str]) -> dict[str, Any]:
        """Async variant of :meth:`GraphResource.nodes_attrs`."""
        body: dict[str, Any] = {"ruts": ruts}
        return await self._client._request("POST", f"{self._path_prefix}/nodes/attrs", json=body)
