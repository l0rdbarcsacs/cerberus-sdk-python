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
