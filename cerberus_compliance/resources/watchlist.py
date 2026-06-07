"""Typed accessor for the Cerberus Compliance ``/watchlist`` resource.

A watchlist lets a caller register Chilean RUTs they want to monitor for
sanctions / adverse-media matches. The platform re-screens each watched
RUT on its own cadence and accumulates the hits it finds; the SDK exposes
the full CRUD lifecycle:

- :meth:`WatchlistResource.create` — start watching a RUT (idempotent per
  RUT; re-adding a watched RUT returns the existing entry, still ``201``).
- :meth:`WatchlistResource.list` — every entry for the calling key, newest
  first, in a ``{"entries": [...], "total": N}`` envelope (no pagination —
  the response always contains every entry, so ``total == len(entries)``).
- :meth:`get` — one entry plus the full list of known ``matches``.
- :meth:`delete` — stop watching a RUT (returns ``204`` / ``None``).

Key isolation
-------------
Every endpoint is scoped to the authenticating **API key** — one key only
ever sees its own entries, and a missing-or-foreign ``entry_id`` surfaces
as a :class:`~cerberus_compliance.errors.NotFoundError` (``404``), never a
``403``, to avoid cross-key enumeration. The whole family **requires a
real API key**: a JWT session (no ``api_key_id``) is rejected with
``403`` by the server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncWatchlistResource", "WatchlistResource"]


def _build_create_body(*, rut: str, label: str | None) -> dict[str, Any]:
    """Build the JSON body for ``POST /watchlist``.

    ``label`` is omitted when ``None`` so the wire payload mirrors the
    documented schema (the field is optional, not nullable). ``rut`` is
    sent verbatim; the server canonicalises it and validates length, so no
    client-side normalisation or length-capping happens here.
    """
    body: dict[str, Any] = {"rut": rut}
    if label is not None:
        body["label"] = label
    return body


class WatchlistResource(BaseResource):
    """Sync accessor for the ``/watchlist`` endpoint family."""

    _path_prefix = "/watchlist"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def create(self, *, rut: str, label: str | None = None) -> dict[str, Any]:
        """Start watching ``rut`` (idempotent per RUT).

        Issues ``POST /watchlist`` and returns the created — or, if the RUT
        was already watched, the pre-existing — entry as a
        ``WatchlistEntryRead`` dict. Always ``201``; re-adding a watched
        RUT never duplicates or errors.

        Args:
            rut: Chilean RUT to watch (e.g. ``"76.275.453-3"``). The server
                canonicalises it; a non-canonicalisable value surfaces as a
                :class:`~cerberus_compliance.errors.ValidationError`
                (``422``). Length is validated server-side (3-16 chars).
            label: Optional free-form label for the entry (max 255 chars,
                server-validated). Omitted from the wire payload when
                ``None``.
        """
        body = _build_create_body(rut=rut, label=label)
        return self._client._request("POST", self._path_prefix, json=body)

    def list(self) -> dict[str, Any]:
        """List every watchlist entry for the calling key.

        Issues ``GET /watchlist`` and returns the raw
        ``{"entries": [...], "total": N}`` envelope verbatim. There is no
        pagination: the response always contains every entry the key owns,
        ordered by ``created_at`` descending, so ``total == len(entries)``.
        """
        return self._client._request("GET", self._path_prefix)

    def get(self, entry_id: str) -> dict[str, Any]:
        """Fetch one entry plus its full match list.

        Issues ``GET /watchlist/{entry_id}`` and returns a
        ``WatchlistEntryDetail`` dict — the entry fields plus ``matches``
        (every known ``WatchlistMatch``, ordered by ``score`` descending,
        with ``match_count == len(matches)``).

        A missing or foreign ``entry_id`` raises
        :class:`~cerberus_compliance.errors.NotFoundError` (``404``); a
        malformed (non-UUID) id is rejected ``422`` by the server.
        """
        return self._get(entry_id)

    def delete(self, entry_id: str) -> None:
        """Stop watching the entry identified by ``entry_id``.

        Issues ``DELETE /watchlist/{entry_id}``; the server responds
        ``204`` with no body, so this returns ``None``. A missing or
        foreign ``entry_id`` raises
        :class:`~cerberus_compliance.errors.NotFoundError` (``404``).
        """
        path = f"{self._path_prefix}/{_encode_id(entry_id)}"
        self._client._request("DELETE", path)


class AsyncWatchlistResource(AsyncBaseResource):
    """Async mirror of :class:`WatchlistResource`."""

    _path_prefix = "/watchlist"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def create(self, *, rut: str, label: str | None = None) -> dict[str, Any]:
        """Async variant of :meth:`WatchlistResource.create`."""
        body = _build_create_body(rut=rut, label=label)
        return await self._client._request("POST", self._path_prefix, json=body)

    async def list(self) -> dict[str, Any]:
        """Async variant of :meth:`WatchlistResource.list`."""
        return await self._client._request("GET", self._path_prefix)

    async def get(self, entry_id: str) -> dict[str, Any]:
        """Async variant of :meth:`WatchlistResource.get`."""
        return await self._get(entry_id)

    async def delete(self, entry_id: str) -> None:
        """Async variant of :meth:`WatchlistResource.delete`."""
        path = f"{self._path_prefix}/{_encode_id(entry_id)}"
        await self._client._request("DELETE", path)
