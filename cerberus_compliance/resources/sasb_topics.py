"""Typed accessor for the Cerberus Compliance ``/sasb-topics`` resource.

SASB topics are the SASB-Standards Industry Disclosure Topics — a fixed
catalogue of material ESG dimensions classified by industry (e.g. *Air
Quality* for ``EM-CM`` Cement, *Data Privacy* for ``TC-IM`` Internet
Media). The Cerberus API ships the catalogue as a static reference table
with offset-style pagination (``limit`` / ``offset``) and an optional
``industry`` filter that narrows on the SASB industry code.

The list-style envelope here is *not* the cursor-paginated shape used by
the rest of the SDK; the server returns ``{"topics": [...], "total": N}``
directly. We surface the raw envelope on :meth:`list` and offer
:meth:`iter_all` as an offset-based convenience for the very small
catalogue (~80 topics) without exposing offsets to the caller.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        topics = client.sasb_topics.list(industry="EM-CM")
        for t in client.sasb_topics.iter_all():
            print(t["topic_code"], t["topic_name"])
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncSasbTopicsResource", "SasbTopicsResource"]


def _build_params(
    *,
    industry: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any] | None:
    """Assemble the SASB query-string dict, dropping ``None`` values.

    Returns ``None`` when every filter is unset so the request URL stays
    a bare ``/sasb-topics`` without trailing ``?``.
    """
    params: dict[str, Any] = {}
    if industry is not None:
        params["industry"] = industry
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params or None


def _extract_topics(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the ``topics`` array out of the SASB envelope, defensively."""
    payload = body.get("topics")
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


class SasbTopicsResource(BaseResource):
    """Sync accessor for ``GET /sasb-topics``.

    The list endpoint returns ``{"topics": [...], "total": int}``;
    pagination is offset-based rather than cursor-based.
    """

    _path_prefix = "/sasb-topics"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def list(
        self,
        *,
        industry: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List SASB topics, optionally filtered by industry.

        Args:
            industry: SASB industry code (e.g. ``"EM-CM"`` for Cement).
            limit: Maximum number of topics on this page.
            offset: Number of topics to skip from the start.

        Returns:
            ``{"topics": [...], "total": int}`` — the raw envelope.
        """
        params = _build_params(industry=industry, limit=limit, offset=offset)
        return self._client._request("GET", self._path_prefix, params=params)

    def iter_all(self, *, industry: str | None = None) -> Iterator[dict[str, Any]]:
        """Yield every topic across all pages, paginating by offset.

        Uses a fixed page size of 100 and increments ``offset`` until the
        server returns an empty page. Yields each topic dict.
        """
        page_size = 100
        offset = 0
        while True:
            body = self.list(industry=industry, limit=page_size, offset=offset)
            topics = _extract_topics(body)
            if not topics:
                return
            yield from topics
            if len(topics) < page_size:
                return
            offset += page_size


class AsyncSasbTopicsResource(AsyncBaseResource):
    """Async mirror of :class:`SasbTopicsResource`."""

    _path_prefix = "/sasb-topics"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def list(
        self,
        *,
        industry: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`SasbTopicsResource.list`."""
        params = _build_params(industry=industry, limit=limit, offset=offset)
        return await self._client._request("GET", self._path_prefix, params=params)

    async def iter_all(self, *, industry: str | None = None) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`SasbTopicsResource.iter_all`."""
        page_size = 100
        offset = 0
        while True:
            body = await self.list(industry=industry, limit=page_size, offset=offset)
            topics = _extract_topics(body)
            if not topics:
                return
            for topic in topics:
                yield topic
            if len(topics) < page_size:
                return
            offset += page_size
