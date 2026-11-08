"""HTTP transport for the acquisition step (ADR-0005).

This is the only module under ``src/rnp`` that imports a networking library. It
does not retry, throttle, follow redirects or decompress: every HTTP response,
including an error status or a redirect, is handed back to the caller as data,
and only a failure to obtain any response becomes NetworkError.
"""

from __future__ import annotations

import http.client
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .. import __version__

ALLOWED_HOSTS = ("files.rcsb.org", "data.rcsb.org", "rest.uniprot.org")
DEFAULT_TIMEOUT = 60.0
USER_AGENT = f"rnp-acquire/{__version__} (+https://github.com/zym137706-ops/reproducible-network-pharmacology)"


class NetworkError(Exception):
    """No HTTP response was obtained."""


@dataclass(frozen=True)
class FetchRequest:
    """One request: extra headers only, the transport adds the User-Agent."""

    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None
    timeout: float


@dataclass(frozen=True)
class FetchResponse:
    """One received response: lower-case header names and the raw body bytes."""

    status: int
    headers: Mapping[str, str]
    body: bytes


Fetcher = Callable[[FetchRequest], FetchResponse]


def check_url(url: str) -> None:
    """Refuse anything that is not an https URL on one of the three hosts."""
    parts = urllib.parse.urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in ALLOWED_HOSTS
        or parts.netloc != parts.hostname
    ):
        raise ValueError(f"URL is not an allowed ADR-0005 endpoint: {url}")


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Hand every 3xx back to the caller instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirects)


def _lower_headers(headers):
    return {str(name).lower(): str(value) for name, value in headers.items()}


def _reason(error):
    reason = getattr(error, "reason", error)
    text = str(reason)
    return text if text else type(error).__name__


def urllib_fetcher(request: FetchRequest) -> FetchResponse:
    """Send one request through urllib; any non-response failure is NetworkError."""
    check_url(request.url)
    headers = {"User-Agent": USER_AGENT, **request.headers}
    prepared = urllib.request.Request(
        request.url, data=request.body, headers=headers, method=request.method
    )
    try:
        with _OPENER.open(prepared, timeout=request.timeout) as reply:
            status = reply.status
            response_headers = _lower_headers(reply.headers)
            body = reply.read()
        return FetchResponse(status, response_headers, body)
    except urllib.error.HTTPError as error:
        try:
            status = error.code
            response_headers = _lower_headers(error.headers)
            body = error.read()
        except (OSError, http.client.HTTPException) as inner:
            raise NetworkError(_reason(inner)) from inner
        finally:
            error.close()
        return FetchResponse(status, response_headers, body)
    except (urllib.error.URLError, OSError, http.client.HTTPException) as error:
        raise NetworkError(_reason(error)) from error
