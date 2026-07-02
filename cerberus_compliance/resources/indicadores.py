"""Typed accessor for the Cerberus Compliance ``/indicadores`` resource.

Indicadores are Chilean monetary, inflation and macro time series from
the Banco Central de Chile (BCCh) statistical database (~25k series),
cached server-side. The canonical, addressable handle for a series is
its BCCh ``series_id`` — a dotted code such as ``F073.UFF.PRE.Z.D``
(Unidad de fomento) — which travels verbatim in the URL path. Every
response carries ``title_es``, the human-readable Spanish label for
the series.

Discovery is done through ``GET /indicadores/buscar``: the Cerberus
copilot translates natural language into a ``series_id``; SDK users
pass a known ``series_id`` directly or discover one via ``buscar``.

All values are returned as **strings** with the exact upstream-published
precision — never ``float`` — so accounting / Decimal consumers do not
suffer silent binary-rounding drift.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        uf = client.indicadores.get("F073.UFF.PRE.Z.D")
        snap = client.indicadores.get("F073.UFF.PRE.Z.D", date="2026-04-24")
        series = client.indicadores.history(
            "F073.UFF.PRE.Z.D", from_="2026-01-01", to="2026-04-30"
        )
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date as _date
from typing import Any
from urllib.parse import quote

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = [
    "AsyncIndicadoresResource",
    "IndicadoresResource",
]


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty.

    Matches the convention used by every other SDK resource so callers can
    forward optional args through ``**kwargs`` without polluting the query
    string with ``"None"`` strings.
    """
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


def _validate_history_range(
    from_: str, to: str, *, context: str = "indicadores.history"
) -> tuple[str, str]:
    """Validate the ``YYYY-MM-DD`` range inputs and return them verbatim.

    The live API accepts ``?from=YYYY-MM-DD&to=YYYY-MM-DD`` query params
    on ``/v1/indicadores/{series_id}`` (and ``/v1/indicadores/compare``).
    We delegate calendar validation to
    :meth:`datetime.date.fromisoformat` (cheap, stdlib, rejects
    ``"2026-13-01"`` and ``"2026-02-30"`` correctly) and let the server
    own the cross-field checks (``from <= to``, ≤ 365-day window).

    Returns the inputs unchanged so callers can forward them directly
    to ``params=``. Strings are kept as strings so the wire encoding is
    identical to what the user passed. ``context`` labels the raising
    SDK method in the error message.

    Raises :class:`ValueError` when either input is not a parseable
    ``YYYY-MM-DD`` ISO date.
    """
    for label, value in (("from_", from_), ("to", to)):
        if not isinstance(value, str):
            raise ValueError(f"{context}: {label} must be 'YYYY-MM-DD', got {value!r}")
        try:
            _date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{context}: {label} must be 'YYYY-MM-DD', got {value!r}") from exc
    return from_, to


def _validate_compare_inputs(series_ids: Sequence[str], from_: str, to: str) -> dict[str, str]:
    """Build the validated query params for ``GET /indicadores/compare``.

    ``series_ids`` must be a real sequence of ``series_id`` strings — a
    bare ``str`` is rejected because comma-joining it would silently
    explode into one-character "ids" on the wire. Cardinality (2 to 6
    series) is enforced server-side (422 → :class:`ValidationError`)
    so this guard stays minimal and forward-compatible.
    """
    if isinstance(series_ids, str):
        raise ValueError(
            "indicadores.compare: series_ids must be a sequence of series_id "
            f"strings (e.g. ['F073.UFF.PRE.Z.D', ...]), got the bare string {series_ids!r}"
        )
    validated_from, validated_to = _validate_history_range(from_, to, context="indicadores.compare")
    return {
        "names": ",".join(series_ids),
        "from": validated_from,
        "to": validated_to,
    }


def _extract_compare_series(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the per-indicator series list out of a compare envelope.

    The live ``/v1/indicadores/compare`` response shape is::

        {
            "series": [
                {
                    "name": "F073.UFF.PRE.Z.D",
                    "title_es": "Unidad de fomento (UF)",
                    "source": "bcentral_api",
                    "items": [{"date": "2026-05-01", "value": "40133.5"}, ...]
                },
                ...
            ]
        }

    Returns the ``series`` array unwrapped for ergonomics. Defensive:
    ``series: null`` or a missing key yields an empty list, matching
    the :func:`_extract_history_items` convention.
    """
    series = body.get("series")
    if not isinstance(series, list):
        return []
    return [s for s in series if isinstance(s, dict)]


def _extract_history_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the date/value series out of an ``IndicadorSeries`` envelope.

    The live ``/v1/indicadores/{series_id}?from=…&to=…`` response shape is::

        {
            "name": "F073.UFF.PRE.Z.D",
            "title_es": "Unidad de fomento (UF)",
            "source": "bcentral_api",
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

    def compare(self, series_ids: Sequence[str], *, from_: str, to: str) -> list[dict[str, Any]]:
        """Compare 2-6 indicator series over a shared date range.

        Wraps ``GET /v1/indicadores/compare?names=a,b&from=…&to=…`` —
        the ``series_id`` handles travel comma-joined in the ``names``
        query param (the live wire name; the values are BCCh
        ``series_id`` codes, case-sensitive).

        Args:
            series_ids: Sequence of 2 to 6 ``series_id`` strings (e.g.
                ``["F073.UFF.PRE.Z.D", "F073.TCO.PRE.Z.D"]``). A bare
                ``str`` is rejected client-side; cardinality is
                validated server-side (422).
            from_: ``YYYY-MM-DD`` start date (inclusive).
            to: ``YYYY-MM-DD`` end date (inclusive).

        Returns:
            The ``series`` array from the server envelope, unwrapped
            for ergonomics — one element per requested indicator:
            ``{"name", "title_es", "source", "items": [{"date",
            "value"}, ...]}``. ``value`` is an exact-precision string,
            never ``float``.

        Raises:
            ValueError: ``series_ids`` is a bare string, or either
                date is not ``YYYY-MM-DD``.
            ValidationError: The server rejected the request (fewer
                than 2 / more than 6 series, ``from > to``, …).
            NotFoundError: An unknown ``series_id`` in the set.
        """
        params = _validate_compare_inputs(series_ids, from_, to)
        body = self._client._request("GET", f"{self._path_prefix}/compare", params=params)
        return _extract_compare_series(body)

    def get(self, series_id: str, date: str | None = None) -> dict[str, Any]:
        """Fetch the indicator value for a specific date.

        Args:
            series_id: Indicator ``series_id`` (BCCh code, e.g.
                ``F073.UFF.PRE.Z.D``; or the special ``tmc``). The dotted
                code travels verbatim in the URL path. Discover one via
                the ``buscar`` endpoint.
            date: Optional ``YYYY-MM-DD`` string. When omitted the
                endpoint returns the most-recently published value.

        Returns:
            The parsed JSON body. Shape::

                {
                    "name": "F073.UFF.PRE.Z.D",
                    "date": "2026-04-24",
                    "value": "39421.73",
                    "source": "bcentral_api",
                    "title_es": "Unidad de fomento (UF)"
                }

            ``value`` is an exact-precision string (never ``float``);
            ``title_es`` is the human-readable label for the series.

        Raises:
            NotFoundError: Unknown ``series_id``, or no value for that
                date (e.g. FX on a Sunday).
            ValidationError: Malformed ``date``.
        """
        path = f"{self._path_prefix}/{quote(series_id, safe='')}"
        params = _clean_params({"date": date})
        return self._client._request("GET", path, params=params)

    def history(self, series_id: str, from_: str, to: str) -> list[dict[str, Any]]:
        """Fetch a historical range of indicator values.

        Issues ``GET /indicadores/{series_id}?from=YYYY-MM-DD&to=YYYY-MM-DD``
        (the live API contract — see ``backend/api/v1_public/indicadores.py``).

        Args:
            series_id: Indicator ``series_id`` (BCCh code, e.g.
                ``F073.UFF.PRE.Z.D``; or the special ``tmc``).
            from_: ``YYYY-MM-DD`` start date (inclusive).
            to: ``YYYY-MM-DD`` end date (inclusive).

        Returns:
            The ``items`` array from the server envelope, unwrapped for
            ergonomics — each element is
            ``{"date": "YYYY-MM-DD", "value": "..."}`` (``value`` is an
            exact-precision string, never ``float``).

        Raises:
            ValueError: Either date is not ``YYYY-MM-DD``.
            NotFoundError: Unknown ``series_id``.
            ValidationError: The server rejected the range (e.g.
                ``from > to`` or window > 365 days).
        """
        path = f"{self._path_prefix}/{quote(series_id, safe='')}"
        validated_from, validated_to = _validate_history_range(from_, to)
        body = self._client._request(
            "GET", path, params={"from": validated_from, "to": validated_to}
        )
        return _extract_history_items(body)

    def forecast(self, series_id: str, *, horizon: int | None = None) -> dict[str, Any]:
        """Fetch a probabilistic forecast for an indicator series.

        Issues ``GET /indicadores/{series_id}/forecast?horizon=N``. The
        forecast is produced server-side by a TimesFM foundation model over
        up to the latest 1024 observations of the series.

        Args:
            series_id: Indicator ``series_id`` (BCCh code, e.g.
                ``F073.UFF.PRE.Z.D``; or the special ``tmc``). An unknown
                ``series_id`` yields a 404.
            horizon: Number of forecast steps requested. The server validates
                ``1 <= horizon <= 256`` (FastAPI ``ge``/``le`` — out of range
                returns 422) and additionally **clamps** the horizon per-series
                according to its cadence and available history (e.g. quarterly
                series are capped at 4), so the ``horizon`` echoed back in the
                response may be smaller than the one requested. Omit for the
                server default (``6``). No client-side cap is applied.

        Returns:
            The parsed JSON body. Shape (``IndicadorForecast``)::

                {
                    "name": "F073.UFF.PRE.Z.D",
                    "title_es": "Unidad de fomento (UF)",
                    "source": "bcentral_api",
                    "model": "timesfm-1.0-200m",
                    "horizon": 6,
                    "context_points": 1024,
                    "interval_pct": 80,
                    "interval_method": "calibrated-quantiles",
                    "points": [
                        {"step": 1, "point": "...", "lower": "...", "upper": "..."},
                        ...
                    ],
                    "disclaimer": "Model forecast, not advice..."
                }

            ``point``/``lower``/``upper`` are exact-precision strings (Decimal
            on the wire), never ``float`` — parse with :class:`decimal.Decimal`
            to avoid binary-rounding drift.

        Raises:
            NotFoundError: Unknown ``series_id``, or the series has no
                historical data in the database to forecast from.
            ValidationError: ``horizon`` outside ``[1, 256]`` (server 422).
            APIStatusError: The optional TimesFM model is not provisioned /
                failed to load — the server returns ``503`` with detail
                ``"forecast model not provisioned"`` and a ``Retry-After``
                header. Treat this as transient capacity absence (never a
                fabricated forecast) and respect ``Retry-After``.
        """
        path = f"{self._path_prefix}/{quote(series_id, safe='')}/forecast"
        params = _clean_params({"horizon": horizon})
        return self._client._request("GET", path, params=params)

    def buscar(
        self,
        *,
        q: str | None = None,
        frequency: str | None = None,
        family: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Discover series over the ~25k-series BCCh catalogue.

        Wraps ``GET /v1/indicadores/buscar`` — the discovery surface for
        the Banco Central de Chile statistical database cached
        server-side. Macro-only data; no PII travels on this endpoint.

        Args:
            q: Keyword filter, matched ``ilike`` against ``title_es`` /
                ``title_en``.
            frequency: One of ``DAILY`` / ``MONTHLY`` / ``QUARTERLY`` /
                ``ANNUAL``.
            family: First segment of the ``series_id`` (e.g. ``F019``).
            limit: Page size (server default applies when omitted).
            offset: Pagination offset.

        All parameters are keyword-only and optional — searching by
        frequency/family alone (no ``q``) is valid.

        ``limit``/``offset`` are validated **server-side** (the API
        declares ``1 <= limit <= 100`` and ``offset >= 0``); out-of-range
        values are rejected with a clean 422 naming the offending param
        (e.g. ``limit=-1`` → ``"Input should be greater than or equal
        to 1"``), surfaced as :class:`ValidationError`. No client-side
        clamping is applied — the server error is authoritative.

        Returns:
            The list of matching items, unwrapped from the server
            envelope for ergonomics — each element is
            ``{"series_id", "title_es", "frequency", "source",
            "tracked", "has_forecast"}``. The server ranks ``tracked``
            series first. Pass a resulting ``series_id`` to
            :meth:`get` / :meth:`forecast`.

        Raises:
            ValidationError: ``limit``/``offset`` out of range, or an
                unknown ``frequency`` value (server 422).
        """
        path = f"{self._path_prefix}/buscar"
        params = _clean_params(
            {"q": q, "frequency": frequency, "family": family, "limit": limit, "offset": offset}
        )
        body = self._client._request("GET", path, params=params)
        return self._extract_items(body)

    # NOTE: ``list`` is deliberately the LAST method of the class — once
    # defined, the name shadows the ``list`` builtin for every later
    # annotation in this class body under mypy --strict.
    def list(self) -> list[dict[str, Any]]:
        """List the catalog of featured (``tracked``) macro indicators.

        Wraps ``GET /v1/indicadores`` — one item per tracked series in
        the server catalog, each carrying coverage metadata. The
        endpoint takes no parameters (the featured catalog is small);
        use :meth:`buscar` to search the full ~25k-series BCCh
        catalogue.

        Returns:
            The list of catalog items, unwrapped from the server
            envelope for ergonomics — each element is
            ``{"name", "title_es", "source", "frequency", "min_date",
            "max_date", "latest_value", "latest_date", "has_forecast"}``.
            ``name`` is the canonical ``series_id``; ``latest_value`` is
            an exact-precision string (never ``float``). Pass ``name``
            to :meth:`get` / :meth:`history` / :meth:`forecast`.
        """
        body = self._client._request("GET", self._path_prefix)
        return self._extract_items(body)


class AsyncIndicadoresResource(AsyncBaseResource):
    """Async mirror of :class:`IndicadoresResource`."""

    _path_prefix = "/indicadores"

    async def compare(
        self, series_ids: Sequence[str], *, from_: str, to: str
    ) -> list[dict[str, Any]]:
        """Async variant of :meth:`IndicadoresResource.compare`."""
        params = _validate_compare_inputs(series_ids, from_, to)
        body = await self._client._request("GET", f"{self._path_prefix}/compare", params=params)
        return _extract_compare_series(body)

    async def get(self, series_id: str, date: str | None = None) -> dict[str, Any]:
        """Async variant of :meth:`IndicadoresResource.get`."""
        path = f"{self._path_prefix}/{quote(series_id, safe='')}"
        params = _clean_params({"date": date})
        return await self._client._request("GET", path, params=params)

    async def history(self, series_id: str, from_: str, to: str) -> list[dict[str, Any]]:
        """Async variant of :meth:`IndicadoresResource.history`."""
        path = f"{self._path_prefix}/{quote(series_id, safe='')}"
        validated_from, validated_to = _validate_history_range(from_, to)
        body = await self._client._request(
            "GET", path, params={"from": validated_from, "to": validated_to}
        )
        return _extract_history_items(body)

    async def forecast(self, series_id: str, *, horizon: int | None = None) -> dict[str, Any]:
        """Async variant of :meth:`IndicadoresResource.forecast`."""
        path = f"{self._path_prefix}/{quote(series_id, safe='')}/forecast"
        params = _clean_params({"horizon": horizon})
        return await self._client._request("GET", path, params=params)

    async def buscar(
        self,
        *,
        q: str | None = None,
        frequency: str | None = None,
        family: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Async variant of :meth:`IndicadoresResource.buscar`."""
        path = f"{self._path_prefix}/buscar"
        params = _clean_params(
            {"q": q, "frequency": frequency, "family": family, "limit": limit, "offset": offset}
        )
        body = await self._client._request("GET", path, params=params)
        return self._extract_items(body)

    # NOTE: ``list`` is deliberately the LAST method of the class — once
    # defined, the name shadows the ``list`` builtin for every later
    # annotation in this class body under mypy --strict.
    async def list(self) -> list[dict[str, Any]]:
        """Async variant of :meth:`IndicadoresResource.list`."""
        body = await self._client._request("GET", self._path_prefix)
        return self._extract_items(body)
