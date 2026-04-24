"""Base classes for sub-resource modules.

Concrete resource modules (``entities``, ``persons``, ...) subclass
:class:`BaseResource` (sync) or :class:`AsyncBaseResource` (async) and
expose typed accessors that delegate to ``_get`` / ``_list`` /
``_iter_all``. The cursor-pagination protocol is documented on
:meth:`BaseResource._iter_all`.

The list response envelope is normalised over two historical shapes:

* ``{"data": [...], "next": "<cursor>"|null, "page": {...}}`` — the
  shape documented in the openapi-python-client fixture and used by
  every unit test.
* ``{"items": [...], "next_cursor": "<cursor>"|null, "prev_cursor": ...,
  "limit": N}`` — the shape emitted by the live production API at
  ``https://compliance.cerberus.cl/v1`` (FastAPI default for
  ``fastapi-pagination``'s cursor provider).

Both shapes are read transparently by :meth:`_list` / :meth:`_iter_all`;
the shape the API returns is whatever is available in the envelope. If
neither ``data`` nor ``items`` is present, the list is treated as empty
and iteration stops.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import quote

if TYPE_CHECKING:
    from cerberus_compliance.client import AsyncCerberusClient, CerberusClient

__all__ = ["AsyncBaseResource", "BaseResource"]


def _extract_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the list of dict rows out of a paginated envelope.

    Accepts either ``{"data": [...]}`` (SDK-documented shape) or
    ``{"items": [...]}`` (live prod API shape). Non-dict entries are
    filtered out so callers receive a homogeneous ``list[dict]``. A
    missing / non-list payload yields an empty list rather than an
    exception — the SDK treats "no rows" and "malformed body" alike
    from the caller's perspective.
    """
    payload: Any = body.get("data")
    if not isinstance(payload, list):
        payload = body.get("items")
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _extract_next_cursor(body: dict[str, Any]) -> str | None:
    """Return the next-page cursor from a paginated envelope, or ``None``.

    Accepts either the SDK-documented ``"next"`` key or the prod API's
    ``"next_cursor"`` key. Empty strings and non-strings collapse to
    ``None`` so :meth:`_iter_all` can use a single ``is None`` check to
    decide whether to stop.
    """
    for key in ("next", "next_cursor"):
        token = body.get(key)
        if isinstance(token, str) and token != "":
            return token
    return None


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

    # Instance-method mirror of the module-level :func:`_extract_items` helper.
    # Subclasses that implement bespoke endpoints (``EntitiesResource.sanctions``,
    # ``RPSFResource.by_entity``/``by_servicio``, ``RegulationsResource.search``,
    # etc.) call this directly so every nested-list endpoint uniformly accepts
    # both ``{"data": [...]}`` and ``{"items": [...]}`` envelopes — matching what
    # :meth:`_list` / :meth:`_iter_all` already do for the standard list path.
    # Bound as a staticmethod because it has no per-instance state; the shared
    # implementation stays in :func:`_extract_items` so the method body is a
    # one-liner and both sync + async bases can re-expose it.
    _extract_items = staticmethod(_extract_items)

    def _list(self, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Issue ``GET <prefix>?params`` and return the row array.

        The envelope is normalised over ``{"data": [...]}`` and
        ``{"items": [...]}`` — see the module docstring for the full
        shape rationale.
        """
        body = self._client._request("GET", self._path_prefix, params=params)
        return _extract_items(body)

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
        The response envelope is read via :func:`_extract_items` /
        :func:`_extract_next_cursor` so both ``{"data"/"next"}`` and
        ``{"items"/"next_cursor"}`` shapes paginate correctly.
        Pagination stops when no next-page cursor is returned.
        """
        base_params: dict[str, Any] = dict(params or {})
        cursor: str | None = None

        while True:
            page_params: dict[str, Any] = dict(base_params)
            if cursor is not None:
                page_params["cursor"] = cursor

            response = self._client._request("GET", self._path_prefix, params=page_params or None)

            yield from _extract_items(response)

            next_token = _extract_next_cursor(response)
            if next_token is None:
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

    # See :attr:`BaseResource._extract_items` for rationale.
    _extract_items = staticmethod(_extract_items)

    async def _list(self, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Async variant of :meth:`BaseResource._list`."""
        body = await self._client._request("GET", self._path_prefix, params=params)
        return _extract_items(body)

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

            for item in _extract_items(response):
                yield item

            next_token = _extract_next_cursor(response)
            if next_token is None:
                return
            cursor = next_token
