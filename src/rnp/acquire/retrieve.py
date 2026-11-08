"""Classify and record one retrieval (ADR-0005). Offline.

The fetcher is injected; only :mod:`rnp.acquire.transport` touches the network.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from .endpoints import (
    HEADER_WHITELIST,
    ROLE_ENTRY,
    ROLE_GRAPHQL,
    ROLE_MMCIF,
    ROLE_UNIPROT,
    build_request,
)
from .transport import DEFAULT_TIMEOUT, NetworkError

REDIRECT_STATUSES = (301, 302, 303, 307, 308)
_UNIPROT_REDIRECT_PATH = re.compile(r"^/uniprotkb/([A-Z0-9]+)(?:\.json)?$")


@dataclass(frozen=True)
class Retrieval:
    """One attempt to retrieve one record, classified and ready to be recorded."""

    role: str
    key: str
    method: str
    url: str
    request_body_sha256: str | None
    fetched_at_utc: str
    http_status: int | None
    outcome: str
    message: str | None
    size: int | None
    sha256: str | None
    headers: Mapping[str, str]
    body: bytes | None

    @property
    def ok(self) -> bool:
        """True only when the response was accepted as the requested record."""
        return self.outcome == "ok"

    def as_request(self, request_id: str, frozen_file: str | None) -> dict[str, object]:
        """The acquisition_record ``requests`` entry for this retrieval."""
        entry: dict[str, object] = {
            "request_id": request_id,
            "role": self.role,
            "method": self.method,
            "url": self.url,
            "request_body_sha256": self.request_body_sha256,
            "fetched_at_utc": self.fetched_at_utc,
            "http_status": self.http_status,
            "outcome": self.outcome,
        }
        if self.message is not None:
            entry["message"] = self.message
        entry["bytes"] = self.size
        entry["sha256"] = self.sha256
        entry["headers"] = dict(self.headers)
        entry["frozen_file"] = frozen_file
        return entry


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_object(data: bytes):
    """Parse UTF-8 JSON; return (object, "") or (None, "not_json"|"not_object")."""
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, "not_json"
    if not isinstance(parsed, dict):
        return None, "not_object"
    return parsed, ""


def _graphql_error_text(errors) -> str:
    first = errors[0] if isinstance(errors, list) and errors else errors
    text = first.get("message") if isinstance(first, dict) else first
    return str(text)[:300]


def _inactive_detail(reason) -> str:
    """``TYPE; mergeDemergeTo: ...; deletedReason: ...`` for an inactive entry."""
    if not isinstance(reason, dict):
        return "unknown"
    kind = reason.get("inactiveReasonType")
    text = "unknown" if kind is None else str(kind)
    details: list[str] = []
    targets = reason.get("mergeDemergeTo")
    if isinstance(targets, list) and targets:
        details.append("mergeDemergeTo: " + ", ".join(str(target) for target in targets))
    deleted = reason.get("deletedReason")
    if isinstance(deleted, str) and deleted.strip():
        details.append("deletedReason: " + deleted.strip())
    return text + ("; " + "; ".join(details) if details else "")


def _redirect_primary(location: str, key: str) -> str | None:
    """The primary accession for a UniProt secondary-accession redirect, else None."""
    parts = urlsplit(location.strip())
    match = _UNIPROT_REDIRECT_PATH.fullmatch(parts.path)
    if match is None:
        return None
    if parse_qs(parts.query).get("from") != [key]:
        return None
    return match.group(1)


def retrieve(
    role: str,
    key: str,
    *,
    fetcher,
    now,
    timeout: float = DEFAULT_TIMEOUT,
) -> Retrieval:
    """Build one request, send it through ``fetcher`` and classify the response."""
    request = build_request(role, key, timeout)
    url = request.url
    body_sha256 = _digest(request.body) if request.body is not None else None
    try:
        response = fetcher(request)
    except NetworkError as error:
        return Retrieval(
            role=role,
            key=key,
            method=request.method,
            url=url,
            request_body_sha256=body_sha256,
            fetched_at_utc=now(),
            http_status=None,
            outcome="network_error",
            message=f"network error for {url}: {error}",
            size=None,
            sha256=None,
            headers={},
            body=None,
        )
    fetched_at_utc = now()
    raw_headers = {str(name).lower(): str(value) for name, value in response.headers.items()}
    headers = {
        name: raw_headers[name].strip()
        for name in HEADER_WHITELIST
        if raw_headers.get(name, "").strip()
    }
    status = response.status
    encoding = raw_headers.get("content-encoding", "").strip().lower() or "identity"
    if encoding == "identity":
        decoded = response.body
    elif encoding in ("gzip", "x-gzip"):
        try:
            decoded = gzip.decompress(response.body)
        except (OSError, EOFError, zlib.error):
            return Retrieval(
                role=role,
                key=key,
                method=request.method,
                url=url,
                request_body_sha256=body_sha256,
                fetched_at_utc=fetched_at_utc,
                http_status=status,
                outcome="api_error",
                message=f"cannot decode gzip body for {url}",
                size=None,
                sha256=None,
                headers=headers,
                body=None,
            )
    else:
        return Retrieval(
            role=role,
            key=key,
            method=request.method,
            url=url,
            request_body_sha256=body_sha256,
            fetched_at_utc=fetched_at_utc,
            http_status=status,
            outcome="api_error",
            message=f"unsupported content-encoding {encoding!r} for {url}",
            size=None,
            sha256=None,
            headers=headers,
            body=None,
        )
    size = len(decoded)
    digest = _digest(decoded)

    def record(outcome: str, message: str | None, body: bytes | None = None) -> Retrieval:
        return Retrieval(
            role=role,
            key=key,
            method=request.method,
            url=url,
            request_body_sha256=body_sha256,
            fetched_at_utc=fetched_at_utc,
            http_status=status,
            outcome=outcome,
            message=message,
            size=size,
            sha256=digest,
            headers=headers,
            body=body,
        )

    if not 200 <= status <= 299:
        location = raw_headers.get("location", "").strip()
        if role == ROLE_UNIPROT and status in REDIRECT_STATUSES:
            primary = _redirect_primary(location, key)
            if primary is not None:
                message = (
                    f"UniProt accession {key} is a secondary accession; "
                    f"UniProt redirects to primary accession {primary} ({url})"
                )
                return record("inactive_accession", message)
        message = f"HTTP {status} for {url}"
        if status in REDIRECT_STATUSES:
            if location:
                message += f" (redirect to {location}; redirects are not followed)"
            else:
                message += " (redirect without a Location header; redirects are not followed)"
        return record("http_error", message)

    if not decoded:
        return record("empty_body", f"empty response body (HTTP {status}) for {url}")

    if role == ROLE_MMCIF:
        first = decoded.split(b"\n", 1)[0].rstrip(b"\r")
        if first != b"data_" + key.encode("utf-8"):
            message = (
                f"response is not an mmCIF block for {key} ({url}): "
                f"expected first line data_{key}"
            )
            return record("api_error", message)
        return record("ok", None, decoded)

    parsed, problem = _json_object(decoded)
    if parsed is None:
        message = (
            f"response is not valid JSON for {url}"
            if problem == "not_json"
            else f"response JSON is not an object for {url}"
        )
        return record("api_error", message)

    if role == ROLE_ENTRY:
        seen = parsed.get("rcsb_id")
        if seen != key:
            message = (
                f"RCSB entry JSON does not describe {key} ({url}): "
                f"rcsb_id is {seen!r}"
            )
            return record("api_error", message)
        return record("ok", None, decoded)

    if role == ROLE_GRAPHQL:
        if parsed.get("errors"):
            text = _graphql_error_text(parsed.get("errors"))
            message = f"RCSB GraphQL reported an error for {url}: {text}"
            return record("api_error", message)
        data = parsed.get("data")
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            message = f"RCSB GraphQL response has no data.entries list for {url}"
            return record("api_error", message)
        found = any(isinstance(entry, dict) and entry.get("rcsb_id") == key for entry in entries)
        if not found:
            message = (
                f"RCSB returned no entry for {key} ({url}); "
                "the GraphQL API silently drops unknown IDs"
            )
            return record("unknown_id", message)
        return record("ok", None, decoded)

    if parsed.get("entryType") == "Inactive":
        detail = _inactive_detail(parsed.get("inactiveReason"))
        message = (
            f"UniProt accession {key} is inactive (inactiveReasonType: {detail}) "
            f"for {url}"
        )
        return record("inactive_accession", message)
    primary = parsed.get("primaryAccession")
    if not isinstance(primary, str) or not primary:
        return record("api_error", f"UniProt entry JSON has no primaryAccession for {url}")
    if primary != key:
        message = (
            f"UniProt accession {key} is a secondary accession; "
            f"UniProt returned primary accession {primary} ({url})"
        )
        return record("inactive_accession", message)
    return record("ok", None, decoded)
