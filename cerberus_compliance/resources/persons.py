"""Typed accessors for the Cerberus Compliance ``/persons`` resource.

Persons are Chilean natural persons (``personas naturales``), identified
by their RUT. This module exposes the synchronous
:class:`PersonsResource` and its asynchronous mirror
:class:`AsyncPersonsResource`.

Two real prod endpoints are wrapped here:

- ``GET /v1/persons`` — paginated listing with PEP-lite filters
  (``pep``, ``cargo``, ``entity_kind``). Returned envelope is
  ``{"persons": [...], "next_cursor": str|None, "has_more": bool}``;
  :meth:`PersonsResource.list` returns it verbatim and
  :meth:`PersonsResource.iter_all` walks the cursor protocol so callers
  can stream every PEP without manually wiring pagination.
- ``GET /v1/persons/{rut}/regulatory-profile`` — single-document
  compliance profile (PEP status, sanctions score, watchlist hits,
  etc.) returned verbatim.

The legacy ``GET /v1/persons/{id}`` detail endpoint never shipped on
the prod API, so :meth:`PersonsResource.get` is preserved as a
deprecation shim that emits a :class:`DeprecationWarning` *on first
call* (not on construction) and raises :class:`NotImplementedError`.
Callers should use :meth:`regulatory_profile` with a known RUT, or
:meth:`cerberus_compliance.resources.entities.EntitiesResource.directors`
to enumerate personas tied to a legal entity. The shim will be removed
in a future minor release — see the CHANGELOG ``Deprecated``
subsection.

The ``/persons/<rut>/regulatory-profile`` endpoint returns a single
object (not a ``{"data": [...]}`` envelope) describing the person's
compliance-risk signals, and is returned verbatim to the caller.
"""

from __future__ import annotations

import warnings
from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = ["AsyncPersonsResource", "PersonEntityKind", "PersonsResource"]

PersonEntityKind = Literal["banco", "emisor", "aseguradora", "agf", "corredor_bolsa"]
"""Allowed values for the ``entity_kind`` filter on :meth:`PersonsResource.list`.

Mirrors the canonical entity-kind taxonomy used by the prod API. Kept
as a public ``Literal`` alias so downstream typed callers can refer to
it without importing the literal-string union inline.
"""

_DEPRECATION_MSG = (
    "client.persons.get is deprecated and will be removed in a future "
    "minor release. The prod API does not expose /v1/persons/{id}; only "
    "/v1/persons/{rut}/regulatory-profile is real. Use "
    "client.persons.regulatory_profile(rut) with a known RUT, or "
    "client.entities.directors(id) to enumerate personas tied to an entity."
)
_REMOVAL_MSG = (
    "/v1/persons/{id} is not a real API endpoint; use "
    "client.persons.regulatory_profile(rut) with a known RUT or "
    "client.entities.directors(id) to enumerate personas via an entity."
)


def _warn_deprecated_call(name: str) -> None:
    """Emit the standard per-call :class:`DeprecationWarning` for the shim.

    Factored into a helper so every deprecated method in both the sync
    and async shims uses the exact same message + stacklevel — keeping
    the user-visible warning text stable for downstream filter rules.
    """
    warnings.warn(
        _DEPRECATION_MSG + f" (hit via client.persons.{name})",
        DeprecationWarning,
        stacklevel=3,
    )


def _build_list_params(
    *,
    pep: bool | None,
    cargo: str | None,
    entity_kind: PersonEntityKind | None,
    cursor: str | None,
    limit: int | None,
) -> dict[str, Any]:
    """Assemble the ``/persons`` query string, dropping ``None`` values.

    ``pep`` is serialised explicitly as the lower-case strings ``"true"``
    / ``"false"`` rather than relying on httpx's bool coercion, so the
    wire URL is stable across httpx releases (some versions emit
    ``"True"`` / ``"False"``).
    """
    params: dict[str, Any] = {}
    if pep is not None:
        params["pep"] = "true" if pep else "false"
    if cargo is not None:
        params["cargo"] = cargo
    if entity_kind is not None:
        params["entity_kind"] = entity_kind
    if cursor is not None:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit
    return params


class PersonsResource(BaseResource):
    """Synchronous accessor for the ``/persons`` endpoint family.

    :meth:`list` / :meth:`iter_all` wrap ``GET /v1/persons`` (paginated
    PEP-lite filtering); :meth:`regulatory_profile` wraps
    ``GET /v1/persons/{rut}/regulatory-profile``. :meth:`get` is a
    deprecated shim that raises :class:`NotImplementedError`.
    """

    _path_prefix = "/persons"

    def list(
        self,
        *,
        pep: bool | None = None,
        cargo: str | None = None,
        entity_kind: PersonEntityKind | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return one page of natural persons matching the filters.

        Issues ``GET /v1/persons`` with whichever filter kwargs are
        non-``None``. Returns the response envelope verbatim so callers
        can read ``persons``, ``next_cursor`` and ``has_more`` without
        another helper.

        Args:
            pep: When ``True``, only return PEPs; ``False`` excludes
                them; ``None`` (default) imposes no filter.
            cargo: Optional ``cargo`` (role/title) substring to filter
                on.
            entity_kind: Optional kind of legal entity the person is
                tied to (``banco``, ``emisor``, ``aseguradora``,
                ``agf``, ``corredor_bolsa``).
            cursor: Pagination cursor returned by a previous call's
                ``next_cursor``. Omit on the first call.
            limit: Max persons to return on this page; the server picks
                a sensible default when omitted.

        Returns:
            ``{"persons": [...], "next_cursor": str|None,
            "has_more": bool}``.
        """
        params = _build_list_params(
            pep=pep,
            cargo=cargo,
            entity_kind=entity_kind,
            cursor=cursor,
            limit=limit,
        )
        return self._client._request("GET", self._path_prefix, params=params or None)

    def get(self, id_: str) -> dict[str, Any]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`.

        The prod API has no ``/v1/persons/{id}`` detail endpoint; this
        shim emits a :class:`DeprecationWarning` then raises so callers
        running under ``-W error::DeprecationWarning`` see the warning
        path rather than a naked :class:`NotImplementedError`.
        """
        _warn_deprecated_call("get")
        raise NotImplementedError(_REMOVAL_MSG)

    def regulatory_profile(self, id_: str) -> dict[str, Any]:
        """Return the full compliance profile for a person.

        Issues ``GET /persons/<id_>/regulatory-profile``. The endpoint
        returns a single object (not a list envelope), so the parsed
        body is returned as-is.
        """
        return self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/regulatory-profile"
        )

    def iter_all(self, **filters: Any) -> Iterator[dict[str, Any]]:
        """Iterate every matching person, transparently paginating.

        Forwards ``**filters`` (``pep``, ``cargo``, ``entity_kind``,
        ``limit``) to every page request. The first page is fetched
        without a cursor; subsequent pages forward the
        ``next_cursor`` token. Iteration stops as soon as ``has_more``
        is falsy or no ``next_cursor`` is returned.
        """
        cursor: str | None = filters.pop("cursor", None)
        while True:
            page = self.list(cursor=cursor, **filters)
            persons = page.get("persons")
            if isinstance(persons, list):
                for person in persons:
                    if isinstance(person, dict):
                        yield person
            if not page.get("has_more"):
                return
            next_cursor = page.get("next_cursor")
            if not isinstance(next_cursor, str) or next_cursor == "":
                return
            cursor = next_cursor


class AsyncPersonsResource(AsyncBaseResource):
    """Asynchronous accessor for the ``/persons`` endpoint family."""

    _path_prefix = "/persons"

    async def list(
        self,
        *,
        pep: bool | None = None,
        cargo: str | None = None,
        entity_kind: PersonEntityKind | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`PersonsResource.list`."""
        params = _build_list_params(
            pep=pep,
            cargo=cargo,
            entity_kind=entity_kind,
            cursor=cursor,
            limit=limit,
        )
        return await self._client._request("GET", self._path_prefix, params=params or None)

    async def get(self, id_: str) -> dict[str, Any]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        _warn_deprecated_call("get")
        raise NotImplementedError(_REMOVAL_MSG)

    async def regulatory_profile(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`PersonsResource.regulatory_profile`."""
        return await self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/regulatory-profile"
        )

    async def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`PersonsResource.iter_all`.

        Implemented as an ``async`` generator so callers consume it via
        ``async for`` directly — matches the pagination idiom used by
        every other paginated async resource in the SDK.
        """
        cursor: str | None = filters.pop("cursor", None)
        while True:
            page = await self.list(cursor=cursor, **filters)
            persons = page.get("persons")
            if isinstance(persons, list):
                for person in persons:
                    if isinstance(person, dict):
                        yield person
            if not page.get("has_more"):
                return
            next_cursor = page.get("next_cursor")
            if not isinstance(next_cursor, str) or next_cursor == "":
                return
            cursor = next_cursor
