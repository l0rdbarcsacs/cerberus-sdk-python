"""Typed accessor for the Cerberus Compliance ``/exports`` resource.

Exports drive a job-queue lifecycle for bulk extraction of any indexed
resource family (entities, sanctions, hechos, esg, regulations, rpsf,
indicadores) into CSV or Parquet.  A typical flow is::

    POST /exports/{resource}    -> 202 + {"export_id": ..., "status": "queued"}
    GET  /exports/{export_id}   -> poll until status in {"ready", "failed", "expired"}
    GET  download_url           -> presigned S3 URL valid until expires_at

The SDK exposes one method per HTTP step (:meth:`create`, :meth:`get`,
:meth:`delete`, :meth:`list`) plus a :meth:`wait` convenience that
implements the polling loop with a configurable interval and timeout.

Example
-------
.. code-block:: python

    from cerberus_compliance import CerberusClient

    with CerberusClient() as client:
        job = client.exports.create("entities", format="csv", filters={"region": "RM"})
        ready = client.exports.wait(job["export_id"])
        print(ready["download_url"])
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Literal

from cerberus_compliance.errors import CerberusAPIError
from cerberus_compliance.resources._base import (
    AsyncBaseResource,
    BaseResource,
    _encode_id,
)

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = [
    "AsyncExportsResource",
    "ExportFormat",
    "ExportResource",
    "ExportsResource",
]

ExportResource = Literal[
    "entities",
    "sanctions",
    "hechos",
    "esg",
    "regulations",
    "rpsf",
    "indicadores",
]
ExportFormat = Literal["csv", "parquet"]

# Statuses that mean "polling can stop". ``ready`` is success; the others
# are terminal failure modes and surface as ``CerberusAPIError`` to the caller
# of :meth:`wait`.
_TERMINAL_STATUSES: frozenset[str] = frozenset({"ready", "failed", "expired"})
_FAILURE_STATUSES: frozenset[str] = frozenset({"failed", "expired"})


def _build_create_body(
    *,
    format_: ExportFormat,
    filters: dict[str, Any] | None,
    fields: list[str] | None,
) -> dict[str, Any]:
    """Build the JSON body for ``POST /exports/{resource}``.

    Drops ``None``-valued top-level keys so the wire payload stays
    minimal, and lets the server apply its own defaults.
    """
    body: dict[str, Any] = {"format": format_}
    if filters:
        body["filters"] = filters
    if fields:
        body["fields"] = fields
    return body


def _wait_failure(body: dict[str, Any], export_id: str) -> CerberusAPIError:
    """Build the ``CerberusAPIError`` raised when an export terminates badly.

    The response body is forwarded verbatim into the ``problem`` dict so
    callers can inspect ``failure_reason`` and ``rows_exported`` without
    a second HTTP round-trip.
    """
    status = body.get("status", "failed")
    return CerberusAPIError(
        status=409,
        problem={
            "title": "Export terminated",
            "detail": f"export {export_id} ended with status={status}",
            "status": 409,
            **body,
        },
    )


def _wait_timeout(export_id: str, timeout: float) -> CerberusAPIError:
    """Build the ``CerberusAPIError`` raised when polling exceeds ``timeout``."""
    return CerberusAPIError(
        status=408,
        problem={
            "title": "Export wait timed out",
            "detail": f"export {export_id} did not become ready within {timeout:.1f}s",
            "status": 408,
        },
    )


class ExportsResource(BaseResource):
    """Sync accessor for the ``/exports`` endpoint family.

    Wraps the bulk-export job queue: create, poll, cancel, list, and wait.
    """

    _path_prefix = "/exports"

    def __init__(self, client: CerberusClient) -> None:
        super().__init__(client)

    def create(
        self,
        resource: ExportResource,
        *,
        format: ExportFormat = "csv",
        filters: dict[str, Any] | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Queue a new export job for ``resource`` and return the queued envelope.

        ``POST /exports/{resource}`` returns ``202 Accepted`` with the
        body ``{"export_id": ..., "status": "queued", "expires_at": ...,
        "created_at": ...}``.  The caller typically passes ``export_id``
        to :meth:`wait` or :meth:`get`.

        Args:
            resource: Which resource family to export.  See
                :data:`ExportResource` for the closed enumeration.
            format: ``"csv"`` (default) or ``"parquet"``.
            filters: Optional resource-specific filters forwarded into the
                worker.  Schema mirrors the resource's own ``list`` filters.
            fields: Optional column subset.  ``None`` means "all default
                columns".
        """
        path = f"{self._path_prefix}/{_encode_id(resource)}"
        body = _build_create_body(format_=format, filters=filters, fields=fields)
        return self._client._request("POST", path, json=body)

    def get(self, export_id: str) -> dict[str, Any]:
        """Poll the current state of an export job.

        Returns the full envelope; once ``status == "ready"`` the body
        contains ``download_url`` plus byte/row counts.
        """
        return self._get(export_id)

    def delete(self, export_id: str) -> None:
        """Cancel a pending export or evict a completed one.

        ``DELETE /exports/{export_id}`` returns ``204 No Content``; this
        method returns ``None`` on success.
        """
        path = f"{self._path_prefix}/{_encode_id(export_id)}"
        self._client._request("DELETE", path)

    def list(self, *, limit: int = 50) -> dict[str, Any]:
        """List recent exports for the calling org.

        Returns the raw envelope (``{"data": [...], ...}``) so callers can
        inspect counts/cursors without an opinionated re-shape.
        """
        return self._client._request("GET", self._path_prefix, params={"limit": limit})

    def wait(
        self,
        export_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Block until ``export_id`` reaches a terminal state.

        Polls :meth:`get` every ``poll_interval`` seconds.  Returns the
        final body when ``status == "ready"``; raises
        :class:`~cerberus_compliance.errors.CerberusAPIError` when the job
        ends in ``"failed"`` / ``"expired"`` or when ``timeout`` elapses
        before the job reaches a terminal state.

        Args:
            export_id: The id returned by :meth:`create`.
            poll_interval: Seconds between successive ``GET`` calls.
            timeout: Total seconds to wait before raising.

        Returns:
            The terminal-state body — guaranteed to have ``status == "ready"``.
        """
        deadline = time.monotonic() + timeout
        while True:
            body = self.get(export_id)
            status = body.get("status")
            if status in _TERMINAL_STATUSES:
                if status in _FAILURE_STATUSES:
                    raise _wait_failure(body, export_id)
                return body
            if time.monotonic() >= deadline:
                raise _wait_timeout(export_id, timeout)
            time.sleep(poll_interval)


class AsyncExportsResource(AsyncBaseResource):
    """Async mirror of :class:`ExportsResource`."""

    _path_prefix = "/exports"

    def __init__(self, client: AsyncCerberusClient) -> None:
        super().__init__(client)

    async def create(
        self,
        resource: ExportResource,
        *,
        format: ExportFormat = "csv",
        filters: dict[str, Any] | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Async variant of :meth:`ExportsResource.create`."""
        path = f"{self._path_prefix}/{_encode_id(resource)}"
        body = _build_create_body(format_=format, filters=filters, fields=fields)
        return await self._client._request("POST", path, json=body)

    async def get(self, export_id: str) -> dict[str, Any]:
        """Async variant of :meth:`ExportsResource.get`."""
        return await self._get(export_id)

    async def delete(self, export_id: str) -> None:
        """Async variant of :meth:`ExportsResource.delete`."""
        path = f"{self._path_prefix}/{_encode_id(export_id)}"
        await self._client._request("DELETE", path)

    async def list(self, *, limit: int = 50) -> dict[str, Any]:
        """Async variant of :meth:`ExportsResource.list`."""
        return await self._client._request("GET", self._path_prefix, params={"limit": limit})

    async def wait(
        self,
        export_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Async variant of :meth:`ExportsResource.wait`.

        Uses :func:`asyncio.sleep` between polls so the event loop stays
        free.  We stick to ``asyncio`` rather than a Trio-compatible
        sleep because the rest of the async SDK is already coupled to
        ``asyncio`` (see ``client._request`` retry loop).
        """
        deadline = time.monotonic() + timeout
        while True:
            body = await self.get(export_id)
            status = body.get("status")
            if status in _TERMINAL_STATUSES:
                if status in _FAILURE_STATUSES:
                    raise _wait_failure(body, export_id)
                return body
            if time.monotonic() >= deadline:
                raise _wait_timeout(export_id, timeout)
            await asyncio.sleep(poll_interval)
