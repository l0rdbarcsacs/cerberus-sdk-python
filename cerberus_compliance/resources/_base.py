"""Base classes for sub-resource modules.

Concrete resource modules (``entities``, ``persons``, ...) subclass
:class:`BaseResource` (sync) or :class:`AsyncBaseResource` (async) and
expose typed accessors that delegate to ``_get`` / ``_list`` /
``_iter_all``. The cursor-pagination protocol is documented on
:meth:`BaseResource._iter_all`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import quote

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncBaseResource", "BaseResource"]


def _encode_id(id_: str) -> str:
    """Percent-encode a path segment so ``"../admin"`` cannot escape the prefix.

    `safe=""` ensures that ``/`` and ``%`` are also encoded — the caller is
    always a single path segment, never a pre-built path.
    """
    return quote(id_, safe="")


class BaseResource:
    """Base class for sync sub-resources.

    Subclasses set :attr:`_path_prefix` (e.g. ``"/entities"``) and call
    :meth:`_list` / :meth:`_get` / :meth:`_iter_all` to interact with
    the parent client.
    """

    _path_prefix: ClassVar[str] = ""

    def __init__(self, client: CerberusClient) -> None:
        self._client = client

    def _list(self, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Issue ``GET <prefix>?params`` and return the ``data`` array.

        The response envelope is expected to look like::

            {"data": [...], "next": "<cursor>"|null, "page": {...}}
        """
        body = self._client._request("GET", self._path_prefix, params=params)
        data = body.get("data", [])
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _get(self, id_: str) -> dict[str, Any]:
        """Issue ``GET <prefix>/<id>`` and return the JSON body.

        The ``id_`` is percent-encoded with :func:`_encode_id` so callers
        can pass raw identifiers without risking path traversal.
        """
        path = f"{self._path_prefix}/{_encode_id(id_)}"
        return self._client._request("GET", path)

    def _iter_all(self, *, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """Cursor-paginate through all pages, yielding one item at a time.

        Forwards all original ``params`` on every request, plus the
        cursor as ``?cursor=<token>`` once the first page returns one.
        Pagination stops as soon as the response ``next`` field is
        absent, ``None``, or an empty string.
        """
        base_params: dict[str, Any] = dict(params or {})
        cursor: str | None = None

        while True:
            page_params: dict[str, Any] = dict(base_params)
            if cursor is not None:
                page_params["cursor"] = cursor

            response = self._client._request("GET", self._path_prefix, params=page_params or None)

            data = response.get("data", [])
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        yield item

            next_token = response.get("next")
            if not isinstance(next_token, str) or next_token == "":
                return
            cursor = next_token


class AsyncBaseResource:
    """Base class for async sub-resources.

    Mirror of :class:`BaseResource`; methods are awaitable and
    :meth:`_iter_all` returns an :class:`AsyncIterator`.
    """

    _path_prefix: ClassVar[str] = ""

    def __init__(self, client: AsyncCerberusClient) -> None:
        self._client = client

    async def _list(self, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Async variant of :meth:`BaseResource._list`."""
        body = await self._client._request("GET", self._path_prefix, params=params)
        data = body.get("data", [])
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    async def _get(self, id_: str) -> dict[str, Any]:
        """Async variant of :meth:`BaseResource._get`."""
        path = f"{self._path_prefix}/{_encode_id(id_)}"
        return await self._client._request("GET", path)

    async def _iter_all(
        self, *, params: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Async variant of :meth:`BaseResource._iter_all`."""
        base_params: dict[str, Any] = dict(params or {})
        cursor: str | None = None

        while True:
            page_params: dict[str, Any] = dict(base_params)
            if cursor is not None:
                page_params["cursor"] = cursor

            response = await self._client._request(
                "GET", self._path_prefix, params=page_params or None
            )

            data = response.get("data", [])
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        yield item

            next_token = response.get("next")
            if not isinstance(next_token, str) or next_token == "":
                return
            cursor = next_token
