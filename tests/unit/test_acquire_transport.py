"""The HTTP transport and the guard that keeps networking inside it (ADR-0005). Offline."""

from __future__ import annotations

import ast
import http.client
import io
import socket
import ssl
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

from rnp import __version__
from rnp.acquire import transport
from rnp.acquire.transport import FetchRequest, NetworkError, urllib_fetcher

SRC = Path(transport.__file__).resolve().parents[1]
URL = "https://files.rcsb.org/download/1M17.cif"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a unit test tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def headers_of(**fields: str) -> Message:
    message = Message()
    for name, value in fields.items():
        message[name.replace("_", "-")] = value
    return message


class Reply:
    """A minimal stand-in for the object that ``OpenerDirector.open`` returns."""

    def __init__(self, status: int, headers: Message, body: bytes, fail=None) -> None:
        self.status, self.headers, self._body, self._fail = status, headers, body, fail
        self.closed = False

    def read(self) -> bytes:
        if self._fail is not None:
            raise self._fail
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False


class FakeOpener:
    def __init__(self, outcome) -> None:
        self.outcome, self.requests, self.timeouts = outcome, [], []

    def open(self, request, timeout=None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def fetch(outcome, *, url=URL, method="GET", headers=None, body=None, timeout=12.5):
    opener = FakeOpener(outcome)
    return opener, FetchRequest(method, url, headers or {}, body, timeout)


def run(monkeypatch, outcome, **kwargs):
    opener, request = fetch(outcome, **kwargs)
    monkeypatch.setattr(transport, "_OPENER", opener)
    return opener, urllib_fetcher(request)


# --- the allowed endpoints -------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://files.rcsb.org/download/1M17.cif",
        "https://data.rcsb.org/graphql",
        "https://data.rcsb.org/rest/v1/core/entry/1M17?x=1",
        "https://rest.uniprot.org/uniprotkb/P00533.json",
    ],
)
def test_the_allowed_endpoints_pass(url) -> None:
    transport.check_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://files.rcsb.org/download/1M17.cif",
        "https://www.rcsb.org/structure/1M17",
        "https://search.rcsb.org/rcsbsearch/v2/query",
        "https://rest.uniprot.org.evil.example/x",
        "https://evil.example/rest.uniprot.org",
        "https://user@files.rcsb.org/x",
        "https://files.rcsb.org:8443/x",
        "https://FILES.RCSB.ORG/x",
        "ftp://files.rcsb.org/x",
        "file:///etc/passwd",
        "//files.rcsb.org/x",
        "",
    ],
)
def test_anything_else_is_refused(url) -> None:
    with pytest.raises(ValueError, match="not an allowed ADR-0005 endpoint"):
        transport.check_url(url)


def test_the_allowed_hosts_and_defaults_are_fixed() -> None:
    assert transport.ALLOWED_HOSTS == ("files.rcsb.org", "data.rcsb.org", "rest.uniprot.org")
    assert transport.DEFAULT_TIMEOUT == 60.0
    assert transport.USER_AGENT == (
        f"rnp-acquire/{__version__} "
        "(+https://github.com/zym137706-ops/reproducible-network-pharmacology)"
    )


def test_a_url_outside_the_list_never_reaches_the_opener(monkeypatch) -> None:
    opener, request = fetch(Reply(200, headers_of(), b""), url="https://example.org/x")
    monkeypatch.setattr(transport, "_OPENER", opener)
    with pytest.raises(ValueError):
        urllib_fetcher(request)
    assert opener.requests == []


# --- responses -------------------------------------------------------------------------------


def test_a_response_is_returned_with_lowercase_headers_and_the_raw_body(monkeypatch) -> None:
    reply = Reply(200, headers_of(Content_Type="chemical/x-cif", ETag='W/"x"'), b"data_1M17\n")
    opener, response = run(monkeypatch, reply)
    assert (response.status, response.body) == (200, b"data_1M17\n")
    assert dict(response.headers) == {"content-type": "chemical/x-cif", "etag": 'W/"x"'}
    assert reply.closed
    assert opener.timeouts == [12.5]


def test_the_request_is_sent_as_given_plus_the_user_agent(monkeypatch) -> None:
    opener, _ = run(
        monkeypatch,
        Reply(200, headers_of(), b"{}"),
        url="https://data.rcsb.org/graphql",
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        body=b'{"q":1}',
    )
    (sent,) = opener.requests
    assert sent.full_url == "https://data.rcsb.org/graphql"
    assert sent.get_method() == "POST"
    assert sent.data == b'{"q":1}'
    assert dict(sent.header_items()) == {
        "Accept": "application/json",
        "Content-type": "application/json",
        "User-agent": transport.USER_AGENT,
    }


def test_a_get_request_has_no_body(monkeypatch) -> None:
    opener, _ = run(monkeypatch, Reply(200, headers_of(), b"x"))
    (sent,) = opener.requests
    assert sent.get_method() == "GET"
    assert sent.data is None


def test_an_http_error_status_is_a_response_not_an_exception(monkeypatch) -> None:
    stream = io.BytesIO(b"<html>404</html>")
    headers = headers_of(Content_Type="text/html")
    error = urllib.error.HTTPError(URL, 404, "Not Found", headers, stream)
    _, response = run(monkeypatch, error)
    assert (response.status, response.body) == (404, b"<html>404</html>")
    assert dict(response.headers) == {"content-type": "text/html"}
    assert stream.closed


def test_a_redirect_is_handed_back_with_its_location(monkeypatch) -> None:
    error = urllib.error.HTTPError(
        URL, 303, "See Other", headers_of(Location="/uniprotkb/P00533?from=P06268"), io.BytesIO(b"")
    )
    _, response = run(monkeypatch, error)
    assert response.status == 303
    assert response.headers["location"] == "/uniprotkb/P00533?from=P06268"


def test_redirects_are_never_followed() -> None:
    handler = transport._NoRedirects()
    request = urllib.request.Request(URL)
    assert (
        handler.redirect_request(request, None, 303, "See Other", headers_of(), "/elsewhere")
        is None
    )
    redirect_handlers = [
        type(handler)
        for handler in transport._OPENER.handlers
        if isinstance(handler, urllib.request.HTTPRedirectHandler)
    ]
    assert redirect_handlers == [transport._NoRedirects]


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.URLError("name resolution failed"),
        TimeoutError("timed out"),
        ConnectionResetError("connection reset by peer"),
        ssl.SSLError("certificate verify failed"),
        http.client.IncompleteRead(b"ab", 10),
        http.client.RemoteDisconnected("remote end closed connection"),
    ],
    ids=["dns", "timeout", "reset", "tls", "truncated", "disconnected"],
)
def test_failures_without_a_response_become_network_errors(monkeypatch, failure) -> None:
    with pytest.raises(NetworkError) as caught:
        run(monkeypatch, failure)
    assert str(caught.value)
    assert caught.value.__cause__ is failure


def test_the_reason_of_a_url_error_is_reported(monkeypatch) -> None:
    with pytest.raises(NetworkError, match="^name resolution failed$"):
        run(monkeypatch, urllib.error.URLError("name resolution failed"))
    with pytest.raises(NetworkError, match="^timed out$"):
        run(monkeypatch, TimeoutError("timed out"))
    with pytest.raises(NetworkError, match="^ConnectionResetError$"):
        run(monkeypatch, ConnectionResetError())


def test_a_body_that_breaks_off_is_a_network_error(monkeypatch) -> None:
    reply = Reply(200, headers_of(), b"", fail=http.client.IncompleteRead(b"ab", 10))
    with pytest.raises(NetworkError):
        run(monkeypatch, reply)
    error = urllib.error.HTTPError(URL, 500, "Boom", headers_of(), io.BytesIO(b""))
    error.read = lambda: (_ for _ in ()).throw(ConnectionResetError("reset"))
    with pytest.raises(NetworkError, match="reset"):
        run(monkeypatch, error)


def test_other_exceptions_are_not_swallowed(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="bug"):
        run(monkeypatch, RuntimeError("bug"))


# --- the guard: networking libraries are imported in one module only -------------------------

BANNED = (
    "urllib.request",
    "urllib.error",
    "urllib.robotparser",
    "http.client",
    "http.server",
    "http.cookiejar",
    "socket",
    "socketserver",
    "ssl",
    "ftplib",
    "smtplib",
    "poplib",
    "imaplib",
    "nntplib",
    "telnetlib",
    "xmlrpc",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "websocket",
    "websockets",
    "paramiko",
    "pycurl",
)


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def networking(path: Path) -> list[str]:
    return sorted(
        name
        for name in imports_of(path)
        if any(name == banned or name.startswith(banned + ".") for banned in BANNED)
    )


def test_only_the_transport_module_imports_a_networking_library() -> None:
    files = sorted(SRC.rglob("*.py"))
    assert len(files) > 15
    assert SRC / "cli.py" in files
    offenders = {
        path.relative_to(SRC).as_posix(): networking(path)
        for path in files
        if path.name != "transport.py" and networking(path)
    }
    assert offenders == {}


def test_the_guard_is_not_vacuous() -> None:
    assert networking(SRC / "acquire" / "transport.py") == [
        "http.client",
        "urllib.error",
        "urllib.request",
    ]


def test_the_guard_notices_each_way_of_importing(tmp_path) -> None:
    source = tmp_path / "sample.py"
    cases = {
        "import socket\n": ["socket"],
        "import urllib.request as r\n": ["urllib.request"],
        "from urllib import request\n": ["urllib.request"],
        "from urllib.request import urlopen\n": ["urllib.request", "urllib.request.urlopen"],
        "from http import client\n": ["http.client"],
        "import requests, json\n": ["requests"],
        "from urllib.parse import urlsplit\nimport json\n": [],
        "def f():\n    import ssl\n": ["ssl"],
    }
    for text, expected in cases.items():
        source.write_text(text, encoding="utf-8")
        assert networking(source) == expected, text
