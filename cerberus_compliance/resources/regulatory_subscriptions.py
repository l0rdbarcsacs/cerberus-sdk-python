"""Typed accessor for ``/regulatory-subscriptions`` (GET + PUT).

El *perfil de suscripción regulatoria* de la organización declara qué sectores
CIIU, materias, facetas legales, fuentes y RUTs le interesan; el motor de
impacto regulatorio lo usa para filtrar qué normas nuevas notificar.

* ``GET /regulatory-subscriptions`` → el perfil actual.
* ``PUT /regulatory-subscriptions`` → reemplaza el perfil (upsert completo).

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        actual = client.regulatory_subscriptions.get()
        client.regulatory_subscriptions.update(
            sectores_ciiu=["64", "65"], facetas=["proteccion_datos"]
        )
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = [
    "AsyncRegulatorySubscriptionsResource",
    "RegulatorySubscriptionsResource",
]


def _build_body(
    *,
    sectores_ciiu: Sequence[str] | None,
    materias: Sequence[str] | None,
    facetas: Sequence[str] | None,
    fuentes: Sequence[str] | None,
    ruts: Sequence[str] | None,
) -> dict[str, Any]:
    """Assemble the PUT body, dropping ``None`` fields (partial upsert)."""
    body: dict[str, Any] = {}
    if sectores_ciiu is not None:
        body["sectores_ciiu"] = list(sectores_ciiu)
    if materias is not None:
        body["materias"] = list(materias)
    if facetas is not None:
        body["facetas"] = list(facetas)
    if fuentes is not None:
        body["fuentes"] = list(fuentes)
    if ruts is not None:
        body["ruts"] = list(ruts)
    return body


class RegulatorySubscriptionsResource(BaseResource):
    """Sync accessor for ``/regulatory-subscriptions`` (GET + PUT)."""

    _path_prefix = "/regulatory-subscriptions"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def get(self) -> dict[str, Any]:
        """Return the organization's current regulatory-subscription profile.

        Returns:
            ``{"sectores_ciiu": [...], "secciones_rollup": [...],
            "materias": [...], "facetas": [...], "fuentes": [...],
            "ruts": [...]}``.
        """
        return self._client._request("GET", self._path_prefix)

    def update(
        self,
        *,
        sectores_ciiu: Sequence[str] | None = None,
        materias: Sequence[str] | None = None,
        facetas: Sequence[str] | None = None,
        fuentes: Sequence[str] | None = None,
        ruts: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Replace the subscription profile (``PUT /regulatory-subscriptions``).

        Cada lista provista reemplaza la correspondiente; las omitidas quedan
        sin tocar (upsert parcial). Returns the updated profile.
        """
        body = _build_body(
            sectores_ciiu=sectores_ciiu,
            materias=materias,
            facetas=facetas,
            fuentes=fuentes,
            ruts=ruts,
        )
        return self._client._request("PUT", self._path_prefix, json=body)


class AsyncRegulatorySubscriptionsResource(AsyncBaseResource):
    """Async mirror of :class:`RegulatorySubscriptionsResource`."""

    _path_prefix = "/regulatory-subscriptions"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def get(self) -> dict[str, Any]:
        """Async variant of :meth:`RegulatorySubscriptionsResource.get`."""
        return await self._client._request("GET", self._path_prefix)

    async def update(
        self,
        *,
        sectores_ciiu: Sequence[str] | None = None,
        materias: Sequence[str] | None = None,
        facetas: Sequence[str] | None = None,
        fuentes: Sequence[str] | None = None,
        ruts: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`RegulatorySubscriptionsResource.update`."""
        body = _build_body(
            sectores_ciiu=sectores_ciiu,
            materias=materias,
            facetas=facetas,
            fuentes=fuentes,
            ruts=ruts,
        )
        return await self._client._request("PUT", self._path_prefix, json=body)
