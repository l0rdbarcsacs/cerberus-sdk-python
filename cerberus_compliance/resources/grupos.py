"""Typed accessor for the Cerberus Compliance ``/grupos/{rut}`` resource.

The ``grupos`` surface exposes the corporate-group structure of a
Chilean legal entity as registered with the CMF under Ley 18.045
(art. 96+, *grupos empresariales*). Given any RUT — the controller's
or that of any member — the API returns the *entire* group: the group
identifier, its controller (when registered), the effective date, and
the ordered list of members.

Unlike most other resources this surface is entity-centric (keyed on
RUT) rather than a paginated collection. There is exactly one method,
:meth:`GruposResource.get_by_rut` (``GET /grupos/{rut}``), which returns
the full :class:`GroupGraph` object; there is no listing, no pagination,
no query string and no request body.

The RUT input is universal: any Chilean RUT in any format (with dots,
canonical ``NNNNNNNN-D`` or without the check digit) is canonicalised
server-side before a case-insensitive match; foreign or synthetic
identifiers that do not parse as a RUT are used verbatim. A ``404``
(RFC 7807 ``ProblemDetail``) is returned when the RUT belongs to no
registered group, surfacing as
:class:`cerberus_compliance.errors.NotFoundError`.

This endpoint is privacy-guardrailed: it returns *structure only*
(group, controller, members with RUT, name, role and the
``es_controlador`` flag) — never PEP or risk scoring.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        group = client.grupos.get_by_rut("96505760-9")
        for member in group["miembros"]:
            print(member["nombre"], member["es_controlador"])
"""

from __future__ import annotations

from typing import Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

__all__ = ["AsyncGruposResource", "GruposResource"]


class GruposResource(BaseResource):
    """Sync accessor for the ``/grupos`` endpoint family.

    The sole method is :meth:`get_by_rut` (``GET /grupos/{rut}``), which
    returns the full corporate-group structure for the group that the
    given RUT belongs to. Requires the ``entities:read`` scope.
    """

    _path_prefix = "/grupos"

    def get_by_rut(self, rut: str) -> dict[str, Any]:
        """Fetch the corporate group that ``rut`` belongs to.

        Issues ``GET /grupos/{rut}``. The ``rut`` may be the controller's
        RUT or that of any member; the response is always the entire
        group. It is percent-encoded with :func:`_encode_id` so callers
        can pass raw identifiers without risking path traversal.

        Args:
            rut: Any Chilean RUT (with dots, canonical ``NNNNNNNN-D`` or
                without check digit) or a foreign/synthetic identifier.
                Forwarded as a single path segment.

        Returns:
            The :class:`GroupGraph` object::

                {
                    "grupo_id": str,
                    "grupo": str,
                    "controlador": {"rut": str | None, "nombre": str} | None,
                    "fecha_vigencia": str | None,
                    "miembros": [
                        {
                            "rut": str,
                            "nombre": str,
                            "role": str | None,
                            "es_controlador": bool,
                        },
                        ...
                    ],
                }

            Members are ordered with controllers first, then by name.

        Raises:
            cerberus_compliance.errors.NotFoundError: When ``rut``
                belongs to no registered group (``404``).
        """
        path = f"{self._path_prefix}/{_encode_id(rut)}"
        return self._client._request("GET", path)


class AsyncGruposResource(AsyncBaseResource):
    """Async mirror of :class:`GruposResource`."""

    _path_prefix = "/grupos"

    async def get_by_rut(self, rut: str) -> dict[str, Any]:
        """Async variant of :meth:`GruposResource.get_by_rut`."""
        path = f"{self._path_prefix}/{_encode_id(rut)}"
        return await self._client._request("GET", path)
