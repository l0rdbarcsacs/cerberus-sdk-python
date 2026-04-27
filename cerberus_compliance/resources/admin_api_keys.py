"""Typed accessor for the Cerberus Compliance ``/admin/api-keys`` resource.

Exposes :meth:`AdminApiKeysResource.me` — a single ``GET /admin/api-keys/me``
call that returns non-secret metadata about the API key used to authenticate
the current request. Useful for SDK consumers who want to surface their
plan tier, remaining quota, or expiry date without having to expose the
secret key itself.

The endpoint never returns the raw key — only a short ``key_prefix``
identifier (``ck_live_4f2e…``) plus environment, tier, scopes, and
quota counters.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        info = client.admin_api_keys.me()
        print(info["tier"], info["quota"]["monthly_remaining"])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cerberus_compliance.resources._base import AsyncBaseResource, BaseResource

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AdminApiKeysResource", "AsyncAdminApiKeysResource"]


class AdminApiKeysResource(BaseResource):
    """Sync accessor for ``GET /admin/api-keys/me``.

    The endpoint exposes non-secret metadata for the calling key:
    ``key_prefix``, ``env``, ``tier``, ``scopes``, ``expires_at``,
    ``last_used_at``, plus a ``quota`` block with monthly counters and a
    ``daily_quota`` block with the per-day budget.
    """

    _path_prefix = "/admin/api-keys"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def me(self) -> dict[str, Any]:
        """Return non-secret metadata for the calling API key.

        Issues ``GET /admin/api-keys/me`` and returns the parsed JSON body
        verbatim.  The response is dict-shaped with at minimum the fields
        documented on the class; callers can index into ``quota`` /
        ``daily_quota`` directly without round-tripping through a model.
        """
        return self._client._request("GET", f"{self._path_prefix}/me")


class AsyncAdminApiKeysResource(AsyncBaseResource):
    """Async mirror of :class:`AdminApiKeysResource`."""

    _path_prefix = "/admin/api-keys"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def me(self) -> dict[str, Any]:
        """Async variant of :meth:`AdminApiKeysResource.me`."""
        return await self._client._request("GET", f"{self._path_prefix}/me")
