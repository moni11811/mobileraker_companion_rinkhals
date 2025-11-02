"""Lightweight fallback implementation of a subset of the ``requests`` API.

This module is **not** a drop-in replacement for the real `requests` package,
but it implements the small feature surface area that Mobileraker Companion
uses.  It allows the Rinkhals package to run on systems where installing
third-party python packages is not possible.

Only the following pieces of functionality are supported:

``get`` and ``post`` helpers returning a :class:`Response` object with
``status_code``, ``content``, ``text`` and ``json`` helpers as well as a
``raise_for_status`` method.  The ``json=`` argument for ``post`` is
supported, and the ``timeout`` argument is honoured for both helpers.

Error handling mimics the relevant pieces of the requests exception hierarchy
that the project relies on.  We expose ``exceptions`` with ``RequestException``
and the common subclasses ``Timeout`` and ``ConnectionError``.  All network
related errors raise one of those exceptions.

The implementation uses :mod:`urllib` from the Python standard library and is
careful to keep the interface compact so it remains easy to maintain.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request


class RequestException(Exception):
    """Base class for all HTTP errors raised by :mod:`simple_requests`."""


class Timeout(RequestException):
    """Raised when a request exceeds the supplied timeout."""


class ConnectionError(RequestException):
    """Raised when a connection to the remote host fails."""


class HTTPError(RequestException):
    """Raised when the server returns an error response (status >= 400)."""


exceptions = SimpleNamespace(
    RequestException=RequestException,
    Timeout=Timeout,
    ConnectionError=ConnectionError,
    HTTPError=HTTPError,
)


@dataclass
class Response:
    """Simplified response object returned by :func:`get` and :func:`post`."""

    status_code: int
    headers: Dict[str, str]
    content: bytes

    def raise_for_status(self) -> None:
        """Raise :class:`HTTPError` when the response indicates a failure."""

        if 400 <= self.status_code:
            raise HTTPError(f"HTTP {self.status_code}: {self.text}")

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


def _build_request(
    url: str,
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
) -> urllib_request.Request:
    req = urllib_request.Request(url, data=data)
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    return req


def _handle_url_error(err: urllib_error.URLError) -> None:
    reason = err.reason
    if isinstance(reason, socket.timeout):
        raise Timeout(str(reason)) from None
    raise ConnectionError(str(reason)) from None


def _execute_request(
    req: urllib_request.Request, timeout: Optional[float]
) -> Response:
    try:
        with urllib_request.urlopen(req, timeout=timeout) as res:  # nosec B310
            content = res.read()
            headers = {k: v for k, v in res.headers.items()}
            return Response(status_code=res.getcode(), headers=headers, content=content)
    except urllib_error.HTTPError as err:
        response = Response(
            status_code=err.code,
            headers=dict(err.headers.items()) if err.headers else {},
            content=err.read(),
        )
        response.raise_for_status()
        return response
    except urllib_error.URLError as err:
        _handle_url_error(err)
        # ``_handle_url_error`` always raises, but keep ``mypy`` happy.
        raise ConnectionError(str(err))
    except socket.timeout as err:
        raise Timeout(str(err)) from None


def get(url: str, timeout: Optional[float] = None, headers: Optional[Dict[str, str]] = None) -> Response:
    """Perform a HTTP GET request.

    Parameters mirror :func:`requests.get` for the supported arguments.
    """

    req = _build_request(url, headers=headers)
    return _execute_request(req, timeout)


def post(
    url: str,
    *,
    json: Optional[Any] = None,
    data: Optional[bytes] = None,
    timeout: Optional[float] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Response:
    """Perform a HTTP POST request supporting ``json=`` bodies."""

    body: Optional[bytes] = data
    req_headers: Dict[str, str] = {}
    if headers:
        req_headers.update(headers)

    if json is not None:
        body = json_dumps(json)
        req_headers.setdefault("Content-Type", "application/json")

    req = _build_request(url, data=body, headers=req_headers)
    return _execute_request(req, timeout)


def json_dumps(payload: Any) -> bytes:
    """Serialise *payload* to JSON bytes using UTF-8 encoding."""

    return json.dumps(payload).encode("utf-8")


__all__ = [
    "ConnectionError",
    "HTTPError",
    "RequestException",
    "Response",
    "Timeout",
    "exceptions",
    "get",
    "post",
]
