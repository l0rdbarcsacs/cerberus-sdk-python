"""Sanctions sub-resource.

Lists and retrieves sanction hits against an entity or natural person.
Supported issuing authorities (``source``) include OFAC, UN, EU, and the
Chilean CMF. ``ONU`` is accepted as a Spanish-locale alias for ``UN`` and
is normalised on the wire so the server only ever sees canonical values.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncSanctionsResource", "SanctionSource", "SanctionsResource"]

SanctionSource = Literal["OFAC", "EU", "UN", "ONU", "CMF"]


def _build_params(
    *,
    target_id: str | None,
    source: SanctionSource | None,
    active: bool | None,
    limit: int | None,
) -> dict[str, Any]:
    """Assemble the query-string dict, dropping ``None`` values.

    Also normalises the ``ONU`` locale alias to the canonical ``UN`` so
    the backend receives a single stable value regardless of caller
    preference.
    """
    params: dict[str, Any] = {}
    if target_id is not None:
        params["target_id"] = target_id
    if source is not None:
        params["source"] = "UN" if source == "ONU" else source
    if active is not None:
        params["active"] = active
    if limit is not None:
        params["limit"] = limit
    return params


def _normalise_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Drop ``None``-valued kwargs and apply the ``ONU`` -> ``UN`` alias.

    The ``None`` filter is always stripped so callers can pass optional
    kwargs through ``**filters`` without polluting the wire URL with
    ``?source=`` and similar empty values.
    """
    normalised = {k: v for k, v in filters.items() if v is not None}
    if normalised.get("source") == "ONU":
        normalised["source"] = "UN"
    return normalised


class SanctionsResource(BaseResource):
    """Synchronous accessor for ``/sanctions``.

    Filters are passed as query parameters; ``None`` values are omitted.
    The ``source`` filter accepts ``"ONU"`` as a locale alias and
    normalises it to ``"UN"`` before the request is sent.
    """

    _path_prefix = "/sanctions"

    def list(
        self,
        *,
        target_id: str | None = None,
        source: SanctionSource | None = None,
        active: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List sanction hits matching the supplied filters.

        Returns the ``data`` array from the API envelope. Any ``None``
        filter is dropped so the wire URL stays minimal.
        """
        params = _build_params(target_id=target_id, source=source, active=active, limit=limit)
        return self._list(params=params or None)

    def get(self, id_: str) -> dict[str, Any]:
        """Fetch a single sanction record by its identifier."""
        return self._get(id_)

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Iterate every matching sanction across all pages.

        Applies the same ``ONU`` -> ``UN`` normalisation as :meth:`list`
        so every paged request carries the canonical source value.
        """
        params = _normalise_filters(filters)
        return self._iter_all(params=params or None)

    def cross_reference(
        self,
        *,
        rut: str | None = None,
        name: str | None = None,
        threshold: float = 0.92,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Match a person or entity against every supported sanctions list.

        Issues ``GET /sanctions/cross-reference``. The server checks
        OFAC SDN, the UN Consolidated list, the EU/UK lists, and CMF
        internal sanctions, returning fuzzy matches above
        ``threshold``.

        At least one of ``rut`` or ``name`` must be supplied; passing
        both narrows the candidate set on the server side.

        Args:
            rut: Optional Chilean RUT to match against.
            name: Optional legal name to match against.
            threshold: Minimum match score (0.0-1.0). Defaults to
                ``0.92`` to match the prod API default.
            limit: Maximum matches to return. Defaults to ``50``.

        Returns:
            ``{"query": {...}, "matches": [{"source": str, "name": str,
            "type": str, "programs": [str], "score": float, ...}],
            "total": int, "threshold": float}``.

        Raises:
            ValueError: When neither ``rut`` nor ``name`` is supplied.
        """
        if rut is None and name is None:
            raise ValueError("cross_reference requires at least one of rut or name")
        params: dict[str, Any] = {"threshold": threshold, "limit": limit}
        if rut is not None:
            params["rut"] = rut
        if name is not None:
            params["name"] = name
        return self._client._request("GET", f"{self._path_prefix}/cross-reference", params=params)


class AsyncSanctionsResource(AsyncBaseResource):
    """Asynchronous accessor for ``/sanctions``.

    Mirrors :class:`SanctionsResource`; :meth:`iter_all` returns an
    :class:`~collections.abc.AsyncIterator` rather than a coroutine.
    """

    _path_prefix = "/sanctions"

    async def list(
        self,
        *,
        target_id: str | None = None,
        source: SanctionSource | None = None,
        active: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Async variant of :meth:`SanctionsResource.list`."""
        params = _build_params(target_id=target_id, source=source, active=active, limit=limit)
        return await self._list(params=params or None)

    async def get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`SanctionsResource.get`."""
        return await self._get(id_)

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`SanctionsResource.iter_all`.

        Returns an async iterator directly (not a coroutine) so it can
        be consumed with ``async for`` without an extra ``await``.
        """
        params = _normalise_filters(filters)
        return self._iter_all(params=params or None)

    async def cross_reference(
        self,
        *,
        rut: str | None = None,
        name: str | None = None,
        threshold: float = 0.92,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Async variant of :meth:`SanctionsResource.cross_reference`."""
        if rut is None and name is None:
            raise ValueError("cross_reference requires at least one of rut or name")
        params: dict[str, Any] = {"threshold": threshold, "limit": limit}
        if rut is not None:
            params["rut"] = rut
        if name is not None:
            params["name"] = name
        return await self._client._request(
            "GET", f"{self._path_prefix}/cross-reference", params=params
        )
