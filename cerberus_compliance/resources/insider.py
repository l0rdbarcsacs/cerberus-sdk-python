"""Typed accessor for the Cerberus Compliance ``/insider`` resource.

The insider surface consolidates Artículo 12 (Ley 18.045) trading
activity around a single Chilean RUT. A RUT may resolve to either an
*insider* (a natural person — ``subject_type='persona'``) whose trades
against various issuers are summarised in ``emisores[]``, or to an
*issuer* (``subject_type='emisor'``) whose insiders are summarised in
``insiders[]``. A well-formed RUT with no Art.12 activity returns an
HTTP 200 envelope with ``has_activity=false`` and
``subject_type='unknown'`` (so callers can distinguish "no data" from a
bad RUT, which yields HTTP 422).

Unlike most resources this surface is entity-centric (keyed on a single
RUT) rather than a paginated collection: there is exactly one method,
:meth:`get_profile` (``GET /insider/{rut_or_persona}/profile``). It has
no query parameters, no request body, and no pagination.

All monetary fields (``total_monto_clp`` / ``total_monto_uf`` and their
per-emisor, per-instrument, and per-direction equivalents) are
``Decimal | null`` on the wire — decode them as :class:`decimal.Decimal`,
never ``float``, per the Cerberus financial-value rule. Every payload
carries a mandatory ``disclaimer`` (Ley 21.719 activity/concentration
framing); surface it, do not strip it.

Requires the ``art12:read`` scope.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        profile = client.insider.get_profile("12.345.678-5")
        if profile["has_activity"]:
            print(profile["subject_type"], profile["total_transactions"])
"""

from __future__ import annotations

from typing import Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

__all__ = ["AsyncInsiderResource", "InsiderResource", "InsiderSubjectType"]

InsiderSubjectType = Literal["persona", "emisor", "unknown"]
"""Resolved subject type for a :meth:`InsiderResource.get_profile` lookup.

``"persona"`` — the RUT is an insider; ``emisores[]`` is populated and
``insiders[]`` is empty. ``"emisor"`` — the RUT is an issuer;
``insiders[]`` is populated and ``emisores[]`` is empty. ``"unknown"`` —
the RUT is well-formed but has no Art.12 activity (HTTP 200,
``has_activity=false``).
"""


class InsiderResource(BaseResource):
    """Sync accessor for the ``/insider`` endpoint family.

    The sole method is :meth:`get_profile`
    (``GET /insider/{rut_or_persona}/profile``), which returns the full
    Art.12 activity dossier for a single RUT.
    """

    _path_prefix = "/insider"

    def get_profile(self, rut_or_persona: str) -> dict[str, Any]:
        """Fetch the Art.12 activity profile for a single RUT.

        Issues ``GET /insider/{rut_or_persona}/profile``.

        Args:
            rut_or_persona: Any Chilean RUT format — dotted
                (``"12.345.678-5"``), canonical (``"12345678-5"``), or
                DV-less body (``"12345678"``). The server normalises it
                to canonical ``NNNNNNNN-D`` before lookup. The segment is
                percent-encoded to prevent path traversal.

        Returns:
            The full insider/issuer dossier. Key fields:
            ``query_rut`` (str), ``subject_type``
            (``"persona" | "emisor" | "unknown"``), ``nombre``
            (``str | null``), ``has_activity`` (bool),
            ``total_transactions`` (int), ``total_monto_clp`` /
            ``total_monto_uf`` (``Decimal | null``),
            ``distinct_emisor_count`` (int), ``emisores`` (list),
            ``distinct_insider_count`` (int), ``insiders`` (list), and a
            mandatory ``disclaimer`` (str).

        Raises:
            CerberusAPIError: For documented error responses — 401
                (missing/invalid key), 403 (insufficient scope), 422
                (non-parseable RUT), 429 (quota or rate-limit exceeded).
                A well-formed RUT with no activity returns HTTP 200, not
                an error.
        """
        path = f"{self._path_prefix}/{_encode_id(rut_or_persona)}/profile"
        return self._client._request("GET", path)


class AsyncInsiderResource(AsyncBaseResource):
    """Async mirror of :class:`InsiderResource`."""

    _path_prefix = "/insider"

    async def get_profile(self, rut_or_persona: str) -> dict[str, Any]:
        """Async variant of :meth:`InsiderResource.get_profile`."""
        path = f"{self._path_prefix}/{_encode_id(rut_or_persona)}/profile"
        return await self._client._request("GET", path)
