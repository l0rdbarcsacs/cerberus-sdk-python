"""Typed accessor for ``GET /regulatory-impact/{impact_id}``.

Un *regulatory impact* es la evaluación del efecto de una norma nueva sobre el
perfil regulatorio suscrito de la organización (sectores, facetas, RUTs). Este
recurso expone el detalle de una evaluación puntual por su id.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        impacto = client.regulatory_impact.get("a1b2c3d4-...")
        print(impacto["titulo"], impacto["severidad"])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource, _encode_id

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncRegulatoryImpactResource", "RegulatoryImpactResource"]


class RegulatoryImpactResource(BaseResource):
    """Sync accessor for ``GET /regulatory-impact/{impact_id}``."""

    _path_prefix = "/regulatory-impact"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def get(self, impact_id: str) -> dict[str, Any]:
        """Return one regulatory-impact evaluation by id.

        Args:
            impact_id: UUID de la evaluación (percent-encoded).

        Returns:
            El detalle de la evaluación de impacto regulatorio.
        """
        path = f"{self._path_prefix}/{_encode_id(impact_id)}"
        return self._client._request("GET", path)


class AsyncRegulatoryImpactResource(AsyncBaseResource):
    """Async mirror of :class:`RegulatoryImpactResource`."""

    _path_prefix = "/regulatory-impact"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def get(self, impact_id: str) -> dict[str, Any]:
        """Async variant of :meth:`RegulatoryImpactResource.get`."""
        path = f"{self._path_prefix}/{_encode_id(impact_id)}"
        return await self._client._request("GET", path)
