"""Tests for the acquisition record schema (ADR-0005).

Every example is synthetic: the response bodies are made-up strings and all byte counts and
hashes are computed from them here, so the records never depend on a live service.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest
from jsonschema import Draft202012Validator

from rnp.config import load_schema

SCHEMA = load_schema("acquisition_record")
VALIDATOR = Draft202012Validator(SCHEMA)
SCHEMA_ID = (
    "https://github.com/zym137706-ops/reproducible-network-pharmacology/"
    "schemas/acquisition_record.schema.json"
)

CIF_BODY = "synthetic mmCIF body of 1M17"
ENTRY_BODY = '{"synthetic": "rcsb entry 1M17"}'
UNIPROT_BODY = '{"synthetic": "uniprot P00533"}'
GRAPHQL_BODY = "synthetic graphql body for 9ZZZ"
EMPTY_GRAPHQL_ANSWER = "synthetic empty graphql answer"
FETCHED_AT = "2026-11-07T02:00:00Z"


def sha256(text: str) -> str:
    """Return the SHA-256 hex digest of the UTF-8 bytes of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_request(
    request_id: str,
    role: str,
    method: str,
    url: str,
    *,
    body: str | None = None,
    fetched_at: str = FETCHED_AT,
    http_status: int = 200,
    outcome: str = "ok",
    frozen_file: str | None = None,
    headers: dict[str, str] | None = None,
    request_body_sha256: str | None = None,
    message: str | None = None,
    byte_count: int | None = None,
    sha256_value: str | None = None,
) -> dict[str, object]:
    """Build one request entry; body supplies the byte count and hash of an ok retrieval."""
    entry: dict[str, object] = {
        "request_id": request_id,
        "role": role,
        "method": method,
        "url": url,
        "request_body_sha256": request_body_sha256,
        "fetched_at_utc": fetched_at,
        "http_status": http_status,
        "outcome": outcome,
        "bytes": byte_count,
        "sha256": sha256_value,
        "headers": dict(headers or {}),
        "frozen_file": frozen_file,
    }
    if body is not None:
        entry["bytes"] = byte_count if byte_count is not None else len(body.encode("utf-8"))
        entry["sha256"] = sha256_value if sha256_value is not None else sha256(body)
    if message is not None:
        entry["message"] = message
    return entry


def make_item(
    item_id: str,
    pdb_id: str,
    accession: str,
    status: str,
    request_ids: list[str],
) -> dict[str, object]:
    """Build one item entry."""
    return {
        "item_id": item_id,
        "pdb_id": pdb_id,
        "uniprot_accession": accession,
        "status": status,
        "request_ids": request_ids,
    }


def example_complete() -> dict[str, object]:
    """A complete synthetic acquisition: one item, three successful retrievals."""
    return {
        "schema_version": "1.0",
        "acquisition_id": "20261107T020000Z_synthetic",
        "tool": {"name": "reproducible-network-pharmacology", "version": "0.1.0"},
        "started_at_utc": "2026-11-07T02:00:00Z",
        "finished_at_utc": "2026-11-07T02:00:07Z",
        "status": "complete",
        "items": [make_item("i1", "1M17", "P00533", "complete", ["r1", "r2", "r3"])],
        "requests": [
            make_request(
                "r1",
                "structure_mmcif",
                "GET",
                "https://files.rcsb.org/download/1M17.cif",
                body=CIF_BODY,
                frozen_file="1M17/1M17.cif",
                headers={"last-modified": "Tue, 03 Mar 2026 00:00:00 GMT"},
            ),
            make_request(
                "r2",
                "rcsb_entry",
                "GET",
                "https://data.rcsb.org/rest/v1/core/entry/1M17",
                body=ENTRY_BODY,
                frozen_file="1M17/rcsb_entry.json",
                headers={"etag": 'W/"synthetic"'},
            ),
            make_request(
                "r3",
                "uniprot_entry",
                "GET",
                "https://rest.uniprot.org/uniprotkb/P00533.json",
                body=UNIPROT_BODY,
                frozen_file="uniprot/P00533.json",
                headers={
                    "date": "Sat, 07 Nov 2026 02:00:05 GMT",
                    "x-uniprot-release": "2026_04",
                    "x-uniprot-release-date": "04-November-2026",
                },
            ),
        ],
        "warnings": [],
    }


def example_partial() -> dict[str, object]:
    """The complete record plus one item and one retrieval that ended as unknown_id."""
    record = example_complete()
    record["status"] = "partial"
    items = record["items"]
    requests = record["requests"]
    assert isinstance(items, list) and isinstance(requests, list)
    items.append(make_item("i2", "9ZZZ", "P00533", "failed", ["r4"]))
    requests.append(
        make_request(
            "r4",
            "rcsb_graphql",
            "POST",
            "https://data.rcsb.org/graphql",
            body=EMPTY_GRAPHQL_ANSWER,
            byte_count=17,
            fetched_at="2026-11-07T02:00:07Z",
            outcome="unknown_id",
            request_body_sha256=sha256(GRAPHQL_BODY),
            message="RCSB returned no entry for 9ZZZ",
        )
    )
    record["warnings"] = ["RCSB returned no entry for 9ZZZ"]
    return record


def example_failed() -> dict[str, object]:
    """A failed synthetic acquisition: the only retrieval returned HTTP 404."""
    return {
        "schema_version": "1.0",
        "acquisition_id": "20261107T020100Z_synthetic",
        "tool": {"name": "reproducible-network-pharmacology", "version": "0.1.0"},
        "started_at_utc": "2026-11-07T02:00:00Z",
        "finished_at_utc": "2026-11-07T02:00:07Z",
        "status": "failed",
        "items": [make_item("i1", "9ZZZ", "P00533", "failed", ["r1"])],
        "requests": [
            make_request(
                "r1",
                "structure_mmcif",
                "GET",
                "https://files.rcsb.org/download/9ZZZ.cif",
                http_status=404,
                outcome="http_error",
                message="HTTP 404 for https://files.rcsb.org/download/9ZZZ.cif",
            )
        ],
        "warnings": [],
    }


BASES = {
    "complete": example_complete,
    "partial": example_partial,
    "failed": example_failed,
}


def error_path(error) -> str:
    """Return the instance path of a validation error as a slash-joined string."""
    return "/".join(str(part) for part in error.absolute_path)


def container(record: dict[str, object], location: str) -> dict[str, object]:
    """Return the nested object addressed by a slash-joined location."""
    node: object = record
    if location:
        for part in location.split("/"):
            node = node[int(part)] if part.isdigit() else node[part]  # type: ignore[index]
    assert isinstance(node, dict)
    return node


def mutate(record: dict[str, object], path: tuple[object, ...], change: str, value) -> None:
    """Apply one change (set or delete) at path."""
    node: object = record
    for part in path[:-1]:
        node = node[part]  # type: ignore[index]
    last = path[-1]
    if change == "set":
        node[last] = value  # type: ignore[index]
    else:
        del node[last]  # type: ignore[index]


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    """The metaschema accepts the schema itself."""
    Draft202012Validator.check_schema(SCHEMA)


def test_schema_identity_and_closed_root() -> None:
    """The schema keeps its agreed identity and rejects unknown top-level keys."""
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert SCHEMA["$id"] == SCHEMA_ID
    assert SCHEMA["title"] == "rnp acquisition record"
    assert SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize(
    ("build", "expected_status"),
    [
        (example_complete, "complete"),
        (example_partial, "partial"),
        (example_failed, "failed"),
    ],
    ids=["complete", "partial", "failed"],
)
def test_valid_examples_pass(build, expected_status: str) -> None:
    """Each synthetic example validates cleanly and survives a JSON round trip."""
    record = build()
    assert record["status"] == expected_status
    assert list(VALIDATOR.iter_errors(record)) == []
    assert json.loads(json.dumps(record)) == record


NEGATIVE_CASES = [
    # (id, base, path, change, value, expected location, expected validator keyword)
    ("missing-requests", "complete", ("requests",), "delete", None, "", "required"),
    ("unknown-top-level-key", "complete", ("extra",), "set", 1, "", "additionalProperties"),
    ("wrong-schema-version", "complete", ("schema_version",), "set", "2.0",
     "schema_version", "const"),
    ("status-not-in-enum", "complete", ("status",), "set", "done", "status", "enum"),
    ("no-items", "complete", ("items",), "set", [], "items", "minItems"),
    ("no-requests", "complete", ("requests",), "set", [], "requests", "minItems"),
    ("bad-timestamp", "complete", ("started_at_utc",), "set", "2026-11-07 02:00:00",
     "started_at_utc", "pattern"),
    ("bad-tool-name", "complete", ("tool", "name"), "set", "rnp", "tool/name", "const"),
    ("url-host-not-allowed", "complete", ("requests", 0, "url"), "set",
     "https://example.org/1M17.cif", "requests/0/url", "pattern"),
    ("url-not-https", "complete", ("requests", 0, "url"), "set",
     "http://files.rcsb.org/download/1M17.cif", "requests/0/url", "pattern"),
    ("header-not-whitelisted", "complete", ("requests", 2, "headers", "set-cookie"), "set", "x",
     "requests/2/headers", "enum"),
    ("role-unknown", "complete", ("requests", 0, "role"), "set", "pdb_download",
     "requests/0/role", "enum"),
    ("sha-uppercase", "complete", ("requests", 0, "sha256"), "set", "A" * 64,
     "requests/0/sha256", None),
    ("sha-too-short", "complete", ("requests", 0, "sha256"), "set", "abc",
     "requests/0/sha256", None),
    ("ok-with-http-404", "complete", ("requests", 0, "http_status"), "set", 404,
     "requests/0/http_status", None),
    ("ok-without-hash", "complete", ("requests", 0, "sha256"), "set", None,
     "requests/0/sha256", None),
    ("ok-without-frozen-file", "complete", ("requests", 0, "frozen_file"), "set", None,
     "requests/0/frozen_file", None),
    ("ok-with-empty-body", "complete", ("requests", 0, "bytes"), "set", 0,
     "requests/0/bytes", "minimum"),
    ("failure-without-message", "partial", ("requests", 3, "message"), "delete", None,
     "requests/3", "required"),
    ("failure-with-frozen-file", "partial", ("requests", 3, "frozen_file"), "set",
     "9ZZZ/answer.json", "requests/3/frozen_file", None),
    ("http-error-with-2xx", "failed", ("requests", 0, "http_status"), "set", 200,
     "requests/0/http_status", "not"),
    ("network-error-with-status", "failed", ("requests", 0, "outcome"), "set",
     "network_error", "requests/0/http_status", None),
    ("post-without-body-hash", "partial", ("requests", 3, "request_body_sha256"), "set", None,
     "requests/3/request_body_sha256", None),
    ("get-with-body-hash", "complete", ("requests", 0, "request_body_sha256"), "set",
     "a" * 64, "requests/0/request_body_sha256", None),
    ("item-without-requests", "complete", ("items", 0, "request_ids"), "set", [],
     "items/0/request_ids", "minItems"),
    ("item-duplicate-request-ids", "complete", ("items", 0, "request_ids"), "set",
     ["r1", "r1"], "items/0/request_ids", "uniqueItems"),
    ("complete-with-failed-item", "partial", ("status",), "set", "complete",
     "items/1/status", "const"),
    ("complete-with-failed-request", "complete", ("requests", 0, "outcome"), "set",
     "api_error", "requests/0/outcome", "const"),
    ("failed-with-complete-item", "failed", ("items", 0, "status"), "set", "complete",
     "items/0/status", "const"),
    ("partial-with-all-items-complete", "partial", ("items", 1, "status"), "set", "complete",
     "items", "contains"),
    ("frozen-file-absolute", "complete", ("requests", 0, "frozen_file"), "set",
     "/tmp/1M17.cif", "requests/0/frozen_file", None),
    ("frozen-file-parent-segment", "complete", ("requests", 0, "frozen_file"), "set",
     "../1M17.cif", "requests/0/frozen_file", None),
    ("frozen-file-drive-letter", "complete", ("requests", 0, "frozen_file"), "set",
     "C:/1M17.cif", "requests/0/frozen_file", None),
    ("frozen-file-backslash", "complete", ("requests", 0, "frozen_file"), "set",
     "1M17\\1M17.cif", "requests/0/frozen_file", None),
    ("frozen-file-empty-segment", "complete", ("requests", 0, "frozen_file"), "set",
     "1M17//1M17.cif", "requests/0/frozen_file", None),
    ("frozen-file-dot-segment", "complete", ("requests", 0, "frozen_file"), "set",
     "./1M17.cif", "requests/0/frozen_file", None),
    ("pdb-id-lowercase", "complete", ("items", 0, "pdb_id"), "set", "1m17",
     "items/0/pdb_id", "pattern"),
    ("pdb-id-too-short", "complete", ("items", 0, "pdb_id"), "set", "1M1",
     "items/0/pdb_id", "pattern"),
    ("pdb-id-starts-with-letter", "complete", ("items", 0, "pdb_id"), "set", "AM17",
     "items/0/pdb_id", "pattern"),
    ("uniprot-isoform-suffix", "complete", ("items", 0, "uniprot_accession"), "set",
     "P00533-2", "items/0/uniprot_accession", "pattern"),
    ("uniprot-lowercase", "complete", ("items", 0, "uniprot_accession"), "set", "p00533",
     "items/0/uniprot_accession", "pattern"),
    ("uniprot-malformed", "complete", ("items", 0, "uniprot_accession"), "set", "ABC",
     "items/0/uniprot_accession", "pattern"),
    ("timestamp-without-z", "complete", ("started_at_utc",), "set", "2026-11-07T02:00:00",
     "started_at_utc", "pattern"),
    ("timestamp-with-offset", "complete", ("finished_at_utc",), "set",
     "2026-11-07T10:00:07+08:00", "finished_at_utc", "pattern"),
    ("unknown-tool-key", "complete", ("tool", "extra"), "set", 1, "tool",
     "additionalProperties"),
    ("unknown-item-key", "complete", ("items", 0, "extra"), "set", 1, "items/0",
     "additionalProperties"),
    ("unknown-request-key", "complete", ("requests", 0, "extra"), "set", 1, "requests/0",
     "additionalProperties"),
    ("partial-without-any-complete-item", "partial", ("items", 0, "status"), "set", "failed",
     "items", "contains"),
    ("acquisition-id-with-space", "complete", ("acquisition_id",), "set", "bad id",
     "acquisition_id", "pattern"),
    ("acquisition-id-empty", "complete", ("acquisition_id",), "set", "", "acquisition_id",
     "pattern"),
    ("request-id-with-slash", "complete", ("requests", 0, "request_id"), "set", "r/1",
     "requests/0/request_id", None),
    ("header-value-not-a-string", "complete", ("requests", 2, "headers", "etag"), "set", 5,
     "requests/2/headers/etag", "type"),
    ("warning-empty-string", "complete", ("warnings",), "set", [""], "warnings/0", "minLength"),
    ("http-status-above-599", "failed", ("requests", 0, "http_status"), "set", 999,
     "requests/0/http_status", "maximum"),
    ("http-status-below-100", "failed", ("requests", 0, "http_status"), "set", 99,
     "requests/0/http_status", "minimum"),
    ("negative-bytes", "failed", ("requests", 0, "bytes"), "set", -1,
     "requests/0/bytes", "minimum"),
]


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=[case[0] for case in NEGATIVE_CASES])
def test_invalid_records_are_rejected(case) -> None:
    """Each weakened record produces an error at the expected place."""
    case_id, base, path, change, value, location, keyword = case
    record = copy.deepcopy(BASES[base]())
    mutate(record, path, change, value)
    errors = list(VALIDATOR.iter_errors(record))
    assert errors, str(case_id) + ": the schema accepted an invalid record"
    at_location = [error for error in errors if error_path(error).startswith(location)]
    assert at_location, (
        str(case_id) + ": expected an error at " + repr(location) + ", got "
        + repr(sorted({error_path(error) for error in errors}))
    )
    if keyword is not None:
        assert any(error.validator == keyword for error in at_location), (
            str(case_id) + ": expected validator " + repr(keyword) + " at " + repr(location)
            + ", got " + repr(sorted({error.validator for error in at_location}))
        )


REQUIRED_KEYS = [
    ("", "schema_version"),
    ("", "acquisition_id"),
    ("", "tool"),
    ("", "started_at_utc"),
    ("", "finished_at_utc"),
    ("", "status"),
    ("", "items"),
    ("", "requests"),
    ("", "warnings"),
    ("tool", "name"),
    ("tool", "version"),
    ("items/0", "item_id"),
    ("items/0", "pdb_id"),
    ("items/0", "uniprot_accession"),
    ("items/0", "status"),
    ("items/0", "request_ids"),
    ("requests/0", "request_id"),
    ("requests/0", "role"),
    ("requests/0", "method"),
    ("requests/0", "url"),
    ("requests/0", "request_body_sha256"),
    ("requests/0", "fetched_at_utc"),
    ("requests/0", "http_status"),
    ("requests/0", "outcome"),
    ("requests/0", "bytes"),
    ("requests/0", "sha256"),
    ("requests/0", "headers"),
    ("requests/0", "frozen_file"),
]


@pytest.mark.parametrize(
    ("location", "key"),
    REQUIRED_KEYS,
    ids=[(location or "root") + "::" + key for location, key in REQUIRED_KEYS],
)
def test_required_key_is_enforced(location: str, key: str) -> None:
    """Deleting a required key is reported as required at its containing object."""
    record = example_complete()
    target = container(record, location)
    del target[key]
    errors = list(VALIDATOR.iter_errors(record))
    hits = [
        error
        for error in errors
        if error_path(error) == location
        and error.validator == "required"
        and key in error.message
    ]
    assert hits, (
        "removing " + repr(key) + " from " + repr(location or "<root>")
        + " was not reported as required"
    )
