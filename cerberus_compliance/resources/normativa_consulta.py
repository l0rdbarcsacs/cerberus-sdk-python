"""Typed accessor for ``/normativa-consulta`` — CMF rulemaking consultations.

Exposes open and recently-closed CMF regulatory consultations, ingested from
``institucional/legislacion_normativa/normativa_tramite.php`` (open) and
``normativa_tramite_cerrada.php`` (closed). The backend ingestor polls both
surfaces every 2 hours to detect new consultations and status transitions.

Typical uses:

* **Early-warning regulatory signal.** A new consultation in the entity's
  ``mercado`` is a leading indicator of a normative obligation 30-90 days
  out.
* **Compliance calendar.** Closed consultations with a publication date tell
  you when the final NCG / Circular ships and obligation dates start to run.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        open_ = client.normativa_consulta.list(estado="abierta", limit=10)
        for c in open_:
            print(c["cmf_consulta_id"], c["titulo"], c["fecha_cierre"])
"""

from __future__ import annotations

from typing import Any, Literal

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

__all__ = [
    "AsyncNormativaConsultaResource",
    "NormativaConsultaEstado",
    "NormativaConsultaResource",
]

NormativaConsultaEstado = Literal["abierta", "cerrada"]
"""Consultation status — the server rejects any other value with ``422``.

We encode the enum on the Python surface as a :class:`typing.Literal` so
strict ``mypy`` callers get an inline completion hint and accidental
typos (``"abiertos"``, ``"open"``) fail at type-check time instead of
runtime.
"""


def _clean_params(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Drop ``None`` values; return ``None`` when the dict is empty."""
    cleaned = {k: v for k, v in raw.items() if v is not None}
    return cleaned or None


class NormativaConsultaResource(BaseResource):
    """Sync accessor for the ``/normativa-consulta`` endpoint."""

    _path_prefix = "/normativa-consulta"

    def list(
        self,
        estado: NormativaConsultaEstado = "abierta",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List regulatory consultations matching the filter.

        Args:
            estado: ``"abierta"`` (default) for open consultations or
                ``"cerrada"`` for recently-closed ones.
            limit: Page size, 1-200. Defaults to 100 (note: the server
                default is 50; the SDK overrides to 100 as a sensible
                default for calendar-style callers).
            offset: Not currently honoured by the server (cursor-paginated),
                but accepted for forward compatibility. When non-zero the
                SDK forwards it verbatim; any server-side rejection
                propagates as :class:`ValidationError`.

        Returns:
            The list of consultation rows unwrapped from the paginated
            envelope (either ``{"items": [...]}`` or ``{"data": [...]}``
            — :meth:`BaseResource._list` handles both). Example row::

                {
                    "id": "e5c1c6ee-9b6a-4a31-bf82-2f2b1e46b2a1",
                    "cmf_consulta_id": "CTA-2026-017",
                    "titulo": "Consulta pública NCG ...",
                    "fecha_apertura": "2026-04-12",
                    "fecha_cierre": "2026-05-12",
                    "estado": "abierta",
                    "mercado_label": "Seguros",
                    "source_url": "https://www.cmfchile.cl/...",
                    "updated_at": "2026-04-24T10:05:00Z"
                }
        """
        params = _clean_params({"estado": estado, "limit": limit, "offset": offset or None})
        return self._list(params=params)


class AsyncNormativaConsultaResource(AsyncBaseResource):
    """Async mirror of :class:`NormativaConsultaResource`."""

    _path_prefix = "/normativa-consulta"

    async def list(
        self,
        estado: NormativaConsultaEstado = "abierta",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Async variant of :meth:`NormativaConsultaResource.list`."""
        params = _clean_params({"estado": estado, "limit": limit, "offset": offset or None})
        return await self._list(params=params)
