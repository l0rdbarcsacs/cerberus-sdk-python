"""Typed accessors for the Cerberus Compliance ``/persons`` resource.

Persons are Chilean natural persons (``personas naturales``), identified
by their RUT. This module exposes the synchronous
:class:`PersonsResource` and its asynchronous mirror
:class:`AsyncPersonsResource`.

Only the ``/persons/{rut}/regulatory-profile`` endpoint is actually
exposed by the prod Cerberus Compliance API. The pre-v0.2.0
``/persons`` collection and ``/persons/{id}`` detail endpoints never
shipped, so :meth:`PersonsResource.list` / :meth:`PersonsResource.get`
are deprecated compatibility shims in v0.2.0 that emit a
:class:`DeprecationWarning` on construction and raise
:class:`NotImplementedError` when called. They will be removed in
v0.3.0 — see the CHANGELOG ``Deprecated`` subsection.

Migration paths for enumerating personas:

- :meth:`cerberus_compliance.resources.entities.EntitiesResource.directors`
  returns the directors of a given entity (natural persons tied to a
  legal entity via ``GET /v1/entities/{id}/directors``).
- :meth:`PersonsResource.regulatory_profile` accepts a known RUT
  directly and returns the full compliance profile.

The ``/persons/<rut>/regulatory-profile`` endpoint returns a single
object (not a ``{"data": [...]}`` envelope) describing the person's
compliance-risk signals — PEP status, sanctions score, watchlist hits,
etc. — and is returned verbatim to the caller.
"""

from __future__ import annotations

import builtins
import warnings
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncPersonsResource", "PersonsResource"]

_DEPRECATION_MSG = (
    "client.persons.list and client.persons.get are deprecated and will be removed "
    "in v0.3.0. The prod API does not expose /v1/persons or /v1/persons/{id}; only "
    "/v1/persons/{rut}/regulatory-profile is real. Use "
    "client.persons.regulatory_profile(rut) with a known RUT, or "
    "client.entities.directors(id) to enumerate personas tied to an entity."
)
_REMOVAL_MSG = (
    "/v1/persons[/...] is not a real API endpoint; use "
    "client.persons.regulatory_profile(rut) with a known RUT or "
    "client.entities.directors(id) to enumerate personas via an entity. "
    "Will be removed in v0.3.0."
)


class PersonsResource(BaseResource):
    """Synchronous accessor for the ``/persons`` endpoint family.

    Only :meth:`regulatory_profile` hits a real production endpoint.
    :meth:`list` and :meth:`get` are deprecated shims that raise
    :class:`NotImplementedError`; see the module docstring for the
    migration paths.
    """

    _path_prefix = "/persons"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)
        warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)

    def list(
        self,
        *,
        rut: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG)

    def get(self, id_: str) -> dict[str, Any]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
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
        """Deprecated: no-op. Raises :class:`NotImplementedError`.

        Pagination made sense when ``/persons`` was (believed to be) a
        listable collection. The prod API has no such endpoint, so the
        method is a compatibility shim that surfaces a clear error
        instead of silently hitting a 404.
        """
        raise NotImplementedError(_REMOVAL_MSG)


class AsyncPersonsResource(AsyncBaseResource):
    """Asynchronous accessor for the ``/persons`` endpoint family."""

    _path_prefix = "/persons"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)
        warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)

    async def list(
        self,
        *,
        rut: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG)

    async def get(self, id_: str) -> dict[str, Any]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`."""
        raise NotImplementedError(_REMOVAL_MSG)

    async def regulatory_profile(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`PersonsResource.regulatory_profile`."""
        return await self._client._request(
            "GET", f"{self._path_prefix}/{quote(id_, safe='')}/regulatory-profile"
        )

    def iter_all(self, **filters: Any) -> AsyncIterator[dict[str, Any]]:
        """Deprecated: no-op. Raises :class:`NotImplementedError`.

        Plain non-``async`` method so the raise fires immediately at
        call time, matching the sync mirror's semantics.
        """
        raise NotImplementedError(_REMOVAL_MSG)
