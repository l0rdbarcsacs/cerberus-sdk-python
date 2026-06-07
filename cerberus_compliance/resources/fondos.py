"""Typed accessor for the Cerberus Compliance ``/fondos`` resource.

Fondos records expose aggregated CMF mutual-fund metrics (BPR fondos
mutuos): one row per ``(fund x serie x periodo)`` carrying the fund's
RUN code, name, share series, reporting period, cadence, currency, net
asset value (``patrimonio``), return (``rentabilidad``), number of
participants (``n_participes``), and unit value (``valor_cuota``).

This is public, aggregated CMF data — no ``Ley 21.719`` boolean-only
guardrail applies. Monetary / ratio fields (``patrimonio``,
``rentabilidad``, ``valor_cuota``) arrive as decimal-bearing strings and
MUST be parsed as :class:`decimal.Decimal`, never ``float`` (Cerberus
rule); ``n_participes`` is an integer.

Both surfaces are cursor-paginated. :meth:`FondosResource.list`
enumerates the whole collection (``periodo`` DESC); :meth:`get`
narrows to a single RUN (``periodo`` DESC, then ``serie`` ASC) and
raises :class:`~cerberus_compliance.errors.NotFoundError` when the RUN
has no metrics (first page empty and no cursor supplied).

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        page = client.fondos.list(periodicidad="mensual", limit=50)
        for fund in client.fondos.iter_all(periodicidad="mensual"):
            ...
        series = client.fondos.get("9022-0")
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal

from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

__all__ = ["AsyncFondosResource", "FondosPeriodicidad", "FondosResource"]

FondosPeriodicidad = Literal["mensual", "diaria"]
"""Reporting cadence filter for :meth:`FondosResource.list` / :meth:`get`.

``"mensual"`` selects month-granular reports (``periodo`` formatted
``YYYY-MM``); ``"diaria"`` selects daily reports (``YYYY-MM-DD``). This
is a *best-effort* filter, not a strict enum: an unrecognised value does
not raise ``422`` — the server returns an empty page instead.
"""


def _build_list_params(
    *,
    periodicidad: FondosPeriodicidad | None,
    periodo: str | None,
    cursor: str | None,
    limit: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/fondos`` query string, dropping ``None`` values.

    Returns ``None`` when no parameter is set so the wire URL stays
    minimal.
    """
    raw: dict[str, Any] = {
        "periodicidad": periodicidad,
        "periodo": periodo,
        "cursor": cursor,
        "limit": limit,
    }
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


def _build_get_params(
    *,
    periodicidad: FondosPeriodicidad | None,
    cursor: str | None,
    limit: int | None,
) -> dict[str, Any] | None:
    """Assemble the ``/fondos/{run}`` query string, dropping ``None`` values."""
    raw: dict[str, Any] = {
        "periodicidad": periodicidad,
        "cursor": cursor,
        "limit": limit,
    }
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class FondosResource(BaseResource):
    """Sync accessor for the ``/fondos`` endpoint family.

    :meth:`list` enumerates every fund metric; :meth:`get` narrows to a
    single fund by its CMF RUN code. Both are cursor-paginated;
    :meth:`iter_all` walks the whole ``list`` collection transparently.
    """

    _path_prefix = "/fondos"

    def list(
        self,
        *,
        periodicidad: FondosPeriodicidad | None = None,
        periodo: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """List fund metrics (``GET /fondos``), ``periodo`` DESC.

        Args:
            periodicidad: Optional cadence filter (``"mensual"`` |
                ``"diaria"``). Best-effort — an invalid value yields an
                empty page rather than a ``422``.
            periodo: Exact reporting-period match (``"YYYY-MM"`` for
                monthly, ``"YYYY-MM-DD"`` for daily). Equality, not a
                range.
            cursor: Opaque pagination cursor from a prior page's
                ``next_cursor`` / ``prev_cursor``. Treated as an opaque
                string; a malformed / expired cursor raises ``400``.
            limit: Page size (server enforces ``1 <= limit <= 200``).

        Returns:
            The page's ``FundMetrics`` rows. Decimal-bearing fields are
            returned verbatim as strings — parse with
            :class:`decimal.Decimal`.
        """
        return self._list(
            params=_build_list_params(
                periodicidad=periodicidad,
                periodo=periodo,
                cursor=cursor,
                limit=limit,
            )
        )

    def get(
        self,
        run: str,
        *,
        periodicidad: FondosPeriodicidad | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Fetch fund metrics for a single RUN (``GET /fondos/{run}``).

        Ordered ``periodo`` DESC then ``serie`` ASC. The ``run`` (e.g.
        ``"9022-0"``) is percent-encoded to prevent path traversal.

        Raises :class:`~cerberus_compliance.errors.NotFoundError` when
        the RUN has no metrics (the API returns ``404`` only when the
        first page is empty *and* no ``cursor`` was supplied).

        Args:
            run: CMF RUN code of the fund (string, may contain a hyphen).
            periodicidad: Optional cadence filter; an invalid value
                yields an empty page (returned ``200`` before the
                ``404`` check, so it never raises not-found).
            cursor: Opaque pagination cursor; malformed / expired
                raises ``400``.
            limit: Page size (server enforces ``1 <= limit <= 200``).

        Returns:
            The page's ``FundMetrics`` rows for this RUN.
        """
        path = f"{self._path_prefix}/{_encode_id(run)}"
        body = self._client._request(
            "GET",
            path,
            params=_build_get_params(
                periodicidad=periodicidad,
                cursor=cursor,
                limit=limit,
            ),
        )
        return self._extract_items(body)

    def iter_all(
        self,
        *,
        periodicidad: FondosPeriodicidad | None = None,
        periodo: str | None = None,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through every fund metric matching the filters.

        Walks the ``GET /fondos`` collection page by page. ``cursor`` is
        managed internally and must not be supplied here.
        """
        return self._iter_all(
            params=_build_list_params(
                periodicidad=periodicidad,
                periodo=periodo,
                cursor=None,
                limit=limit,
            )
        )


class AsyncFondosResource(AsyncBaseResource):
    """Async mirror of :class:`FondosResource`."""

    _path_prefix = "/fondos"

    async def list(
        self,
        *,
        periodicidad: FondosPeriodicidad | None = None,
        periodo: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`FondosResource.list`."""
        return await self._list(
            params=_build_list_params(
                periodicidad=periodicidad,
                periodo=periodo,
                cursor=cursor,
                limit=limit,
            )
        )

    async def get(
        self,
        run: str,
        *,
        periodicidad: FondosPeriodicidad | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Async variant of :meth:`FondosResource.get`."""
        path = f"{self._path_prefix}/{_encode_id(run)}"
        body = await self._client._request(
            "GET",
            path,
            params=_build_get_params(
                periodicidad=periodicidad,
                cursor=cursor,
                limit=limit,
            ),
        )
        return self._extract_items(body)

    def iter_all(
        self,
        *,
        periodicidad: FondosPeriodicidad | None = None,
        periodo: str | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`FondosResource.iter_all`."""
        return self._iter_all(
            params=_build_list_params(
                periodicidad=periodicidad,
                periodo=periodo,
                cursor=None,
                limit=limit,
            )
        )
