"""Typed accessor for the Cerberus Compliance ``/indicadores`` resource.

Indicadores are Chilean monetary, inflation and macro series sourced
from two upstreams and cached server-side:

* **CMF Indicadores API v3** (``api.cmfchile.cl/api-sbifv3/recursos_api/``)
  — six SBIF-published series: ``UF``, ``UTM``, ``USD``, ``EUR``,
  ``IPC``, ``TMC``.
* **Banco Central de Chile (BCCh)** — five BCentral-published macro
  series: ``TPM`` (Tasa Política Monetaria, daily), ``IMACEC``
  (Índice Mensual de Actividad Económica, monthly), ``IMACEC_MIN``
  (IMACEC minero), ``IPC_BCH`` (BCentral's IPC view), and ``PIB``
  (Producto Interno Bruto, quarterly).

==============  =============================================================
``name``        Description
==============  =============================================================
``UF``          Unidad de Fomento (inflation-indexed), CLP, from 1998-01-01.
``UTM``         Unidad Tributaria Mensual, CLP / month, from 1990-01-01.
``USD``         Observed USD/CLP (working-day semantics), from 1984-01-01.
``EUR``         Observed EUR/CLP (working-day semantics), from 1999-01-01.
``IPC``         Índice de Precios al Consumidor (monthly), from 2000-01-01.
``TMC``         Tasa Máxima Convencional, % annualised, from 1990-01-01.
``TPM``         Tasa Política Monetaria, % annualised (daily, BCCh).
``IMACEC``      Índice Mensual de Actividad Económica (monthly, BCCh).
``IMACEC_MIN``  IMACEC sector minero (monthly, BCCh).
``IPC_BCH``     IPC as published by BCCh (monthly).
``PIB``         Producto Interno Bruto, real terms (quarterly, BCCh).
==============  =============================================================

The :data:`SbifIndicatorName` and :data:`BCentralIndicatorName` aliases
are exposed for callers who want stricter typing on a per-source basis;
:data:`IndicatorName` is the union both methods accept on the wire.

All values are returned as **strings** with the exact upstream-published
precision — never ``float`` — so accounting / Decimal consumers do not
suffer silent binary-rounding drift.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        today = client.indicadores.get("UF")
        snap = client.indicadores.get("UF", date="2026-04-24")
        tpm = client.indicadores.get("TPM")
        series = client.indicadores.history(
            "UF", from_="2026-01-01", to="2026-04-30"
        )
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any, Literal
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = [
    "AsyncIndicadoresResource",
    "BCentralIndicatorName",
    "IndicadoresResource",
    "IndicatorName",
    "SbifIndicatorName",
]

SbifIndicatorName = Literal["UF", "UTM", "USD", "EUR", "IPC", "TMC"]
"""SBIF-published series available from the CMF Indicadores API v3.

Includes monetary indices (``UF``, ``UTM``), spot FX (``USD``, ``EUR``),
inflation (``IPC``) and the regulatory ceiling rate (``TMC``).
"""

BCentralIndicatorName = Literal["TPM", "IMACEC", "IMACEC_MIN", "IPC_BCH", "PIB"]
"""Banco Central de Chile macro series.

* ``TPM`` — Tasa Política Monetaria (daily, % annualised).
* ``IMACEC`` — Índice Mensual de Actividad Económica (monthly).
* ``IMACEC_MIN`` — IMACEC sector minero (monthly).
* ``IPC_BCH`` — IPC as published by BCCh (monthly).
* ``PIB`` — Producto Interno Bruto, real terms (quarterly).
"""

IndicatorName = Literal[
    "UF",
    "UTM",
    "USD",
    "EUR",
    "IPC",
    "TMC",
    "TPM",
    "IMACEC",
    "IMACEC_MIN",
    "IPC_BCH",
    "PIB",
]
"""Union of every indicator name accepted by :class:`IndicadoresResource`.

Equivalent to ``SbifIndicatorName | BCentralIndicatorName``; spelled
out as a flat ``Literal`` to keep mypy reveal-type output ergonomic.
"""


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty.

    Matches the convention used by every other SDK resource so callers can
    forward optional args through ``**kwargs`` without polluting the query
    string with ``"None"`` strings.
    """
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


def _validate_history_range(from_: str, to: str) -> tuple[str, str]:
    """Validate the ``YYYY-MM-DD`` range inputs and return them verbatim.

    The live API accepts ``?from=YYYY-MM-DD&to=YYYY-MM-DD`` query params
    on ``/v1/indicadores/{name}``. We delegate calendar validation to
    :meth:`datetime.date.fromisoformat` (cheap, stdlib, rejects
    ``"2026-13-01"`` and ``"2026-02-30"`` correctly) and let the server
    own the cross-field checks (``from <= to``, ≤ 365-day window).

    Returns the inputs unchanged so callers can forward them directly
    to ``params=``. Strings are kept as strings so the wire encoding is
    identical to what the user passed.

    Raises :class:`ValueError` when either input is not a parseable
    ``YYYY-MM-DD`` ISO date.
    """
    for label, value in (("from_", from_), ("to", to)):
        if not isinstance(value, str):
            raise ValueError(f"indicadores.history: {label} must be 'YYYY-MM-DD', got {value!r}")
        try:
            _date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"indicadores.history: {label} must be 'YYYY-MM-DD', got {value!r}"
            ) from exc
    return from_, to


def _extract_history_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the date/value series out of an ``IndicadorSeries`` envelope.

    The live ``/v1/indicadores/{name}?from=…&to=…`` response shape is::

        {
            "name": "UF",
            "source": "cmf_api_sbifv3",
            "items": [
                {"date": "2026-01-01", "value": "38989.15"},
                ...
            ],
            "total": N
        }

    Returns the ``items`` array unwrapped for ergonomics. Defensive:
    if the server (or a recorded mock) returns ``items: null`` or omits
    the key entirely, we yield an empty list instead of raising.
    """
    items = body.get("items")
    if not isinstance(items, list):
        return []
    return [v for v in items if isinstance(v, dict)]


class IndicadoresResource(BaseResource):
    """Sync accessor for the ``/indicadores`` endpoint family."""

    _path_prefix = "/indicadores"

    def get(self, name: str, date: str | None = None) -> dict[str, Any]:
        """Fetch the indicator value for a specific date.

        Args:
            name: Indicator code (``UF``, ``UTM``, ``USD``, ``EUR``,
                ``IPC``, ``TMC``). Case-insensitive on the server.
            date: Optional ``YYYY-MM-DD`` string. When omitted the
                endpoint returns the most-recently published value.

        Returns:
            The parsed JSON body. Shape::

                {
                    "name": "UF",
                    "date": "2026-04-24",
                    "value": "39421.73",
                    "currency": "CLP",
                    "unit": "CLP_per_UF",
                    "source": "cmf-api-sbifv3",
                    "fetched_at": "2026-04-24T13:45:00Z"
                }

        Raises:
            NotFoundError: Unknown ``name``, or no value for that date
                (e.g. FX on a Sunday).
            ValidationError: Malformed ``date``.
        """
        path = f"{self._path_prefix}/{quote(name, safe='')}"
        params = _clean_params({"date": date})
        return self._client._request("GET", path, params=params)

    def history(self, name: str, from_: str, to: str) -> list[dict[str, Any]]:
        """Fetch a historical range of indicator values.

        Issues ``GET /indicadores/{name}?from=YYYY-MM-DD&to=YYYY-MM-DD``
        (the live API contract — see ``backend/api/v1_public/indicadores.py``).

        Args:
            name: Indicator code (see :meth:`get`).
            from_: ``YYYY-MM-DD`` start date (inclusive).
            to: ``YYYY-MM-DD`` end date (inclusive).

        Returns:
            The ``items`` array from the server envelope, unwrapped for
            ergonomics — each element is
            ``{"date": "YYYY-MM-DD", "value": "..."}``.

        Raises:
            ValueError: Either date is not ``YYYY-MM-DD``.
            NotFoundError: Unknown ``name``.
            ValidationError: The server rejected the range (e.g.
                ``from > to`` or window > 365 days).
        """
        path = f"{self._path_prefix}/{quote(name, safe='')}"
        validated_from, validated_to = _validate_history_range(from_, to)
        body = self._client._request(
            "GET", path, params={"from": validated_from, "to": validated_to}
        )
        return _extract_history_items(body)


class AsyncIndicadoresResource(AsyncBaseResource):
    """Async mirror of :class:`IndicadoresResource`."""

    _path_prefix = "/indicadores"

    async def get(self, name: str, date: str | None = None) -> dict[str, Any]:
        """Async variant of :meth:`IndicadoresResource.get`."""
        path = f"{self._path_prefix}/{quote(name, safe='')}"
        params = _clean_params({"date": date})
        return await self._client._request("GET", path, params=params)

    async def history(self, name: str, from_: str, to: str) -> list[dict[str, Any]]:
        """Async variant of :meth:`IndicadoresResource.history`."""
        path = f"{self._path_prefix}/{quote(name, safe='')}"
        validated_from, validated_to = _validate_history_range(from_, to)
        body = await self._client._request(
            "GET", path, params={"from": validated_from, "to": validated_to}
        )
        return _extract_history_items(body)
