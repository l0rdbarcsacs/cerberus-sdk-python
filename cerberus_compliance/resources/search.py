"""Universal semantic search client for the Cerberus Compliance API.

Exposes ``POST /search`` — the CMF document semantic-search endpoint
backed by Qdrant + Bedrock Titan Embeddings. A single query string is
embedded server-side and matched against the full document corpus
(resoluciones, OPAs, TDC, Art.12/20, comunicaciones, dictámenes, ESG,
normativa, normativa-consulta).

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient
    from cerberus_compliance.resources.search import SearchFilters

    with CerberusClient() as client:
        results = client.search.search(
            query="NCG 461 sostenibilidad emisores",
            filters=SearchFilters(doc_types=["normativa", "comunicaciones"]),
            top_k=5,
        )
        for hit in results["hits"]:
            print(hit["score"], hit["title"])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = [
    "AsyncSearchClient",
    "SearchClient",
    "SearchFilters",
    "SearchHit",
    "SearchResponse",
]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SearchFilters(BaseModel):
    """Optional filters for the ``/search`` endpoint.

    All fields are optional — omit any you don't need.

    Attributes
    ----------
    doc_types:
        Restrict results to these document types. Accepted values include
        ``"resoluciones"``, ``"opas"``, ``"tdc"``, ``"art12"``,
        ``"art20"``, ``"comunicaciones"``, ``"dictamenes"``, ``"esg"``,
        ``"normativa"``, ``"normativa_consulta"``. ``None`` means all.
    from_date:
        ISO 8601 date string (``YYYY-MM-DD``). Only return documents
        published on or after this date.
    to_date:
        ISO 8601 date string. Only return documents published on or before
        this date.
    entity_rut:
        If provided, restrict results to documents related to this Chilean
        RUT (exact match on entity_rut metadata).
    """

    doc_types: list[str] | None = Field(default=None)
    from_date: str | None = Field(default=None)
    to_date: str | None = Field(default=None)
    entity_rut: str | None = Field(default=None)

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict, omitting ``None`` fields."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class SearchHit(BaseModel):
    """A single ranked result returned by the search endpoint."""

    id: str
    score: float
    doc_type: str
    title: str | None = None
    snippet: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Structured response from the ``POST /search`` endpoint."""

    query: str
    hits: list[SearchHit] = Field(default_factory=list)
    total: int = 0


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
                set by document type, date range, or entity RUT.
            top_k: Maximum number of hits to return (default 10).

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
