"""Universal semantic search client for the Cerberus Compliance API.

Exposes ``POST /search`` — the CMF document semantic-search endpoint
backed by Qdrant + Bedrock Titan Embeddings. A single query string is
embedded server-side and matched against the full document corpus
(resoluciones, OPAs, TDC, Art.12/20, comunicaciones, dictámenes, ESG,
normativa, normativa-consulta, hechos esenciales, RAN capítulos).

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient
    from cerberus_compliance.resources.search import (
        SearchDateRange,
        SearchFilters,
    )

    with CerberusClient() as client:
        results = client.search.search(
            query="NCG 461 sostenibilidad emisores",
            filters=SearchFilters(
                tipo_documento=["normativa", "comunicacion"],
                date_range=SearchDateRange(from_="2024-01-01"),
            ),
            top_k=5,
        )
        for hit in results.hits:
            print(hit.score, hit.source_table, hit.tipo_documento)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = [
    "AsyncSearchClient",
    "SearchClient",
    "SearchDateRange",
    "SearchFilters",
    "SearchHit",
    "SearchResponse",
]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SearchDateRange(BaseModel):
    """Optional ``[from, to]`` window for the ``date_range`` filter.

    Attributes
    ----------
    from_:
        ISO date (``YYYY-MM-DD``) — inclusive lower bound on
        ``publicacion_at``. ``None`` means "earliest available".
        Aliased to the wire field ``from`` because it clashes with the
        Python keyword.
    to:
        ISO date (``YYYY-MM-DD``) — inclusive upper bound. ``None``
        means "latest available".
    """

    from_: str | date | None = Field(default=None, alias="from")
    to: str | date | None = None

    model_config = ConfigDict(populate_by_name=True)


class SearchFilters(BaseModel):
    """Filter bag for ``POST /search``.

    Mirrors the server-side schema in
    ``backend/schemas/cmf_public.py::SearchFilters``. All fields are
    optional — omit any you don't need.

    Attributes
    ----------
    tipo_documento:
        Restrict to these document categories. Examples:
        ``"resolucion"``, ``"opa"``, ``"tdc"``, ``"art12_transaccion"``,
        ``"art20_participacion"``, ``"comunicacion"``, ``"dictamen"``,
        ``"esg_disclosure"``, ``"normativa"``, ``"hecho_esencial"``,
        ``"ran_capitulo"``.
    marco_regulatorio:
        Match any of the supplied regulatory frameworks tagged on the
        document (e.g. ``"ley_18045"``, ``"ncg_461"``, ``"otro"``).
    tipo_entidad_target:
        Match any of the target-entity classifications (e.g.
        ``"emisor"``, ``"banco"``, ``"administradora_general_fondos"``,
        ``"otro"``).
    materias:
        Match any of the topic tags (e.g. ``"gobierno_corporativo"``,
        ``"sanciones"``, ``"esg"``, ``"otro"``).
    entity_rut:
        Restrict to documents whose ``entity_rut`` payload matches this
        Chilean RUT exactly (e.g. ``"96.505.760-9"``).
    date_range:
        Inclusive window over the ``publicacion_at`` field — see
        :class:`SearchDateRange`.
    """

    tipo_documento: list[str] | None = None
    marco_regulatorio: list[str] | None = None
    tipo_entidad_target: list[str] | None = None
    materias: list[str] | None = None
    entity_rut: str | None = None
    date_range: SearchDateRange | None = None

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict, omitting ``None`` fields.

        ``date_range`` is serialised by-alias so the ``from_`` Python
        field round-trips to the wire field ``from`` (matching the
        server's :pyclass:`SearchDateRange`).
        """
        # ``model_dump(exclude_none=True, by_alias=True)`` would also
        # alias top-level fields (none of which need it), so we keep the
        # explicit shape and only apply by_alias inside date_range.
        out: dict[str, Any] = {}
        if self.tipo_documento is not None:
            out["tipo_documento"] = list(self.tipo_documento)
        if self.marco_regulatorio is not None:
            out["marco_regulatorio"] = list(self.marco_regulatorio)
        if self.tipo_entidad_target is not None:
            out["tipo_entidad_target"] = list(self.tipo_entidad_target)
        if self.materias is not None:
            out["materias"] = list(self.materias)
        if self.entity_rut is not None:
            out["entity_rut"] = self.entity_rut
        if self.date_range is not None:
            dr_raw = self.date_range.model_dump(by_alias=True, exclude_none=True, mode="json")
            if dr_raw:
                out["date_range"] = dr_raw
        return out


class SearchHit(BaseModel):
    """A single ranked result returned by the search endpoint.

    Mirrors ``backend/schemas/cmf_public.py::SearchHit``. The
    :attr:`payload` dict carries the SQL-hydrated source-row contents;
    its keys vary by :attr:`source_table` (e.g. ``cmf_resoluciones``
    rows expose ``cmf_resolucion_id``, ``fecha_resolucion``, etc.).
    """

    score: float
    source_table: str
    source_row_id: UUID
    tipo_documento: str
    marco_regulatorio: list[str] = Field(default_factory=list)
    tipo_entidad_target: list[str] = Field(default_factory=list)
    materias: list[str] = Field(default_factory=list)
    entity_rut: str | None = None
    publicacion_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Structured response from ``POST /search``.

    Attributes
    ----------
    query:
        The original query string echoed back by the server.
    hits:
        Ranked list of :class:`SearchHit` — already trimmed to ``top_k``
        and filtered above the server's score threshold.
    total_searched:
        Total number of documents the embedder searched against (the
        size of the candidate corpus *before* score filtering, useful
        for telemetry / SLO dashboards).
    """

    query: str
    hits: list[SearchHit] = Field(default_factory=list)
    total_searched: int = 0


# ---------------------------------------------------------------------------
# Resource classes
# ---------------------------------------------------------------------------

_SEARCH_PATH = "/search"


class SearchClient:
    """Sync client for the ``POST /search`` endpoint.

    Wired into :class:`~cerberus_compliance.client.CerberusClient` as
    ``client.search``.
    """

    def __init__(self, client: CerberusClient) -> None:
        self._client = client

    def search(
        self,
        *,
        query: str,
        filters: SearchFilters | None = None,
        top_k: int = 10,
    ) -> SearchResponse:
        """Perform a semantic search across all CMF document types.

        Args:
            query: Free-text search string (embedded server-side via
                Bedrock Titan Embeddings).
            filters: Optional :class:`SearchFilters` to narrow the result
                set by document type, taxonomy tags, entity RUT, or
                publication date range.
            top_k: Maximum number of hits to return (1-40, default 10).

        Returns:
            :class:`SearchResponse` containing the ranked hit list.

        Raises:
            :class:`~cerberus_compliance.errors.CerberusAPIError`: On any
                non-2xx response.
        """
        body: dict[str, Any] = {"query": query, "top_k": top_k}
        if filters is not None:
            filter_dict = filters.to_api_dict()
            if filter_dict:
                body["filters"] = filter_dict

        raw = self._client._request("POST", _SEARCH_PATH, json=body)
        return SearchResponse.model_validate(raw)


class AsyncSearchClient:
    """Async mirror of :class:`SearchClient`.

    Wired into :class:`~cerberus_compliance.client.AsyncCerberusClient`
    as ``client.search``.
    """

    def __init__(self, client: AsyncCerberusClient) -> None:
        self._client = client

    async def search(
        self,
        *,
        query: str,
        filters: SearchFilters | None = None,
        top_k: int = 10,
    ) -> SearchResponse:
        """Async variant of :meth:`SearchClient.search`."""
        body: dict[str, Any] = {"query": query, "top_k": top_k}
        if filters is not None:
            filter_dict = filters.to_api_dict()
            if filter_dict:
                body["filters"] = filter_dict

        raw = await self._client._request("POST", _SEARCH_PATH, json=body)
        return SearchResponse.model_validate(raw)
