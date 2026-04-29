"""Typed accessor for the Cerberus Compliance ``/resolve`` universal resolver.

Exposes :meth:`ResolveResource.resolve` — a single ``GET /resolve`` call that
takes a free-form query, RUT, or name and returns the canonical entity or
person that matches, plus a confidence score and the inference method used
(exact match, RUT extraction, fuzzy name search, or LLM reasoning).

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        hit = client.resolve.resolve(query="banco de chile s.a.")
        print(hit["kind"], hit["entity_id"], hit["confidence"])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncResolveResource", "ResolveResource"]


def _build_params(
    *,
    query: str | None,
    rut: str | None,
    name: str | None,
) -> dict[str, str]:
    params: dict[str, str] = {}
    if query is not None:
        params["query"] = query
    if rut is not None:
        params["rut"] = rut
    if name is not None:
        params["name"] = name
    if not params:
        raise ValueError("resolve() requires at least one of: query, rut, name")
    return params


class ResolveResource(BaseResource):
    """Sync accessor for ``GET /resolve`` — universal CMF resolver.

    Returns ``{kind, entity_id, persona_id, extracted_rut, extracted_name,
    confidence, method, llm_reasoning}``. ``kind`` is one of
    ``entity | persona | placeholder``.
    """

    _path_prefix = "/resolve"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def resolve(
        self,
        *,
        query: str | None = None,
        rut: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a free-form query / RUT / name to a canonical entity or person.

        Pass at least one of ``query``, ``rut``, or ``name``. The server uses
        the most specific signal available: exact RUT match first, then
        deterministic RUT extraction from text, then fuzzy name search, then
        an LLM reasoning fallback for ambiguous strings.
        """
        params = _build_params(query=query, rut=rut, name=name)
        return self._client._request("GET", self._path_prefix, params=params)


class AsyncResolveResource(AsyncBaseResource):
    """Async mirror of :class:`ResolveResource`."""

    _path_prefix = "/resolve"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def resolve(
        self,
        *,
        query: str | None = None,
        rut: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`ResolveResource.resolve`."""
        params = _build_params(query=query, rut=rut, name=name)
        return await self._client._request("GET", self._path_prefix, params=params)
