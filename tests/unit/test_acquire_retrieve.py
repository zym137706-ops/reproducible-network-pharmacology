"""Endpoints, request building and the classification of one retrieval (ADR-0005). Offline."""

from __future__ import annotations

import gzip
import hashlib
import json
import socket

import pytest
from acquire_support import (
    GRAPHQL_URL,
    FakeClock,
    FakeFetcher,
    cif_body,
    entry_body,
    entry_url,
    graphql_answer,
    mmcif_url,
    reply,
    uniprot_body,
    uniprot_url,
)

from rnp.acquire import endpoints
from rnp.acquire.retrieve import Retrieval, retrieve
from rnp.acquire.transport import NetworkError, check_url
from rnp.config import load_schema

MMCIF, ENTRY, GRAPHQL, UNIPROT = "structure_mmcif", "rcsb_entry", "rcsb_graphql", "uniprot_entry"
URL = {
    MMCIF: mmcif_url,
    ENTRY: entry_url,
    GRAPHQL: lambda key: GRAPHQL_URL,
    UNIPROT: uniprot_url,
}
GZIP = {"content-encoding": "gzip"}
QUERY_SHA256 = "589ded87da9abbeb8432d4b5910b98a4d70c75870f12e0a2f51951949b1006eb"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a unit test tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jbytes(value) -> bytes:
    return json.dumps(value).encode()


def run(role, key, answer, **options):
    method = "POST" if role == GRAPHQL else "GET"
    fetcher = FakeFetcher({(method, URL[role](key)): answer})
    clock = FakeClock()
    retrieval = retrieve(role, key, fetcher=fetcher, now=clock, **options)
    return retrieval, fetcher, clock


# --- endpoints -------------------------------------------------------------------------------


def test_roles_and_header_whitelist_are_fixed() -> None:
    assert endpoints.ROLES == (MMCIF, ENTRY, GRAPHQL, UNIPROT)
    assert endpoints.HEADER_WHITELIST == (
        "date",
        "last-modified",
        "etag",
        "x-uniprot-release",
        "x-uniprot-release-date",
        "x-api-deployment-date",
    )
    schema = load_schema("acquisition_record")
    whitelist = schema["$defs"]["request"]["properties"]["headers"]["propertyNames"]["enum"]
    assert sorted(endpoints.HEADER_WHITELIST) == sorted(whitelist)
    assert sorted(endpoints.ROLES) == sorted(
        schema["$defs"]["request"]["properties"]["role"]["enum"]
    )


def test_identifier_patterns_equal_the_schema_patterns() -> None:
    item = load_schema("acquisition_record")["$defs"]["item"]["properties"]
    assert endpoints.PDB_ID_REGEX == item["pdb_id"]["pattern"]
    assert endpoints.UNIPROT_ACCESSION_REGEX == item["uniprot_accession"]["pattern"]


@pytest.mark.parametrize("value", ["1M17", "6VXX", "0ZZZ", "9ZZZ", "4HHB"])
def test_valid_pdb_ids(value) -> None:
    assert endpoints.is_pdb_id(value)


@pytest.mark.parametrize(
    "value", ["1m17", "1M1", "1M171", "AM17", "1M17\n", " 1M17", "1M-7", "", None, 1117]
)
def test_invalid_pdb_ids(value) -> None:
    assert not endpoints.is_pdb_id(value)


@pytest.mark.parametrize("value", ["P00533", "Q9ZZZ9", "A0A024R161", "O00688", "P06268"])
def test_valid_accessions(value) -> None:
    assert endpoints.is_uniprot_accession(value)


@pytest.mark.parametrize(
    "value", ["p00533", "P00533-2", "P0053", "P00533\n", "ABC", "P00533 ", "", None, 533]
)
def test_invalid_accessions(value) -> None:
    assert not endpoints.is_uniprot_accession(value)


def test_graphql_query_text_is_pinned() -> None:
    assert sha(endpoints.GRAPHQL_QUERY.encode("utf-8")) == QUERY_SHA256


def test_graphql_body_is_canonical_json() -> None:
    expected = json.dumps(
        {"query": endpoints.GRAPHQL_QUERY, "variables": {"ids": ["1M17"]}},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert endpoints.graphql_body("1M17") == expected
    assert endpoints.graphql_body("1M17") != endpoints.graphql_body("6VXX")


@pytest.mark.parametrize(
    ("role", "key", "method", "url", "headers", "has_body"),
    [
        (MMCIF, "1M17", "GET", "https://files.rcsb.org/download/1M17.cif", {}, False),
        (
            ENTRY,
            "1M17",
            "GET",
            "https://data.rcsb.org/rest/v1/core/entry/1M17",
            {"Accept": "application/json"},
            False,
        ),
        (
            GRAPHQL,
            "1M17",
            "POST",
            "https://data.rcsb.org/graphql",
            {"Accept": "application/json", "Content-Type": "application/json"},
            True,
        ),
        (
            UNIPROT,
            "P00533",
            "GET",
            "https://rest.uniprot.org/uniprotkb/P00533.json",
            {"Accept": "application/json"},
            False,
        ),
    ],
)
def test_requests_are_built_exactly(role, key, method, url, headers, has_body) -> None:
    request = endpoints.build_request(role, key, 12.5)
    assert (request.method, request.url, dict(request.headers), request.timeout) == (
        method,
        url,
        headers,
        12.5,
    )
    assert request.body == (endpoints.graphql_body(key) if has_body else None)
    check_url(request.url)
    assert endpoints.build_request(role, key).timeout == 60.0


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown acquisition role"):
        endpoints.build_request("pdb_download", "1M17")
    with pytest.raises(ValueError, match="unknown acquisition role"):
        retrieve("pdb_download", "1M17", fetcher=FakeFetcher(), now=FakeClock())


# --- classification of one retrieval ---------------------------------------------------------

CIF = cif_body("1M17")
MMCIF_BAD = "response is not an mmCIF block for 1M17 ({url}): expected first line data_1M17"
NOT_JSON = "response is not valid JSON for {url}"
ENTRY_MISMATCH = "RCSB entry JSON does not describe 1M17 ({url}): rcsb_id is {seen}"
GRAPHQL_NONE = (
    "RCSB returned no entry for {key} ({url}); the GraphQL API silently drops unknown IDs"
)
GRAPHQL_SHAPE = "RCSB GraphQL response has no data.entries list for {url}"
GRAPHQL_ERROR = "RCSB GraphQL reported an error for {url}: {text}"
INACTIVE = "UniProt accession {key} is inactive (inactiveReasonType: {detail}) for {url}"
SECONDARY_REDIRECT = (
    "UniProt accession P06268 is a secondary accession; "
    "UniProt redirects to primary accession P00533 ({url})"
)
SECONDARY_BODY = (
    "UniProt accession P06268 is a secondary accession; "
    "UniProt returned primary accession P00533 ({url})"
)
REDIRECT = "HTTP {status} for {url} (redirect to {target}; redirects are not followed)"


def entries(*ids):
    return jbytes({"data": {"entries": [{"rcsb_id": i} if i else None for i in ids]}})


def inactive(key, reason):
    return jbytes({"entryType": "Inactive", "primaryAccession": key, "inactiveReason": reason})


# (id, role, key, answer, outcome, status, message template or None, decoded body or None)
CASES = [
    ("mmcif-ok", MMCIF, "1M17", reply(CIF), "ok", 200, None, CIF),
    (
        "mmcif-ok-crlf",
        MMCIF,
        "1M17",
        reply(b"data_1M17\r\n#\r\n"),
        "ok",
        200,
        None,
        b"data_1M17\r\n#\r\n",
    ),
    (
        "mmcif-ok-gzip",
        MMCIF,
        "1M17",
        reply(gzip.compress(CIF), headers={"Content-Encoding": "GZIP"}),
        "ok",
        200,
        None,
        CIF,
    ),
    (
        "mmcif-ok-identity",
        MMCIF,
        "1M17",
        reply(CIF, headers={"content-encoding": "identity"}),
        "ok",
        200,
        None,
        CIF,
    ),
    (
        "mmcif-404-html",
        MMCIF,
        "0ZZZ",
        reply(b"<html>404</html>", 404),
        "http_error",
        404,
        "HTTP 404 for {url}",
        b"<html>404</html>",
    ),
    (
        "mmcif-500-empty",
        MMCIF,
        "1M17",
        reply(b"", 500),
        "http_error",
        500,
        "HTTP 500 for {url}",
        b"",
    ),
    (
        "mmcif-404-gzip",
        MMCIF,
        "1M17",
        reply(gzip.compress(b"nope"), 404, GZIP),
        "http_error",
        404,
        "HTTP 404 for {url}",
        b"nope",
    ),
    (
        "mmcif-200-empty",
        MMCIF,
        "1M17",
        reply(b""),
        "empty_body",
        200,
        "empty response body (HTTP 200) for {url}",
        b"",
    ),
    (
        "mmcif-html-instead",
        MMCIF,
        "1M17",
        reply(b"<html>captive portal</html>"),
        "api_error",
        200,
        MMCIF_BAD,
        b"<html>captive portal</html>",
    ),
    (
        "mmcif-other-block",
        MMCIF,
        "1M17",
        reply(cif_body("9ZZZ")),
        "api_error",
        200,
        MMCIF_BAD,
        cif_body("9ZZZ"),
    ),
    (
        "mmcif-longer-id",
        MMCIF,
        "1M17",
        reply(b"data_1M17X\n#\n"),
        "api_error",
        200,
        MMCIF_BAD,
        b"data_1M17X\n#\n",
    ),
    (
        "mmcif-lowercase-id",
        MMCIF,
        "1M17",
        reply(b"data_1m17\n#\n"),
        "api_error",
        200,
        MMCIF_BAD,
        b"data_1m17\n#\n",
    ),
    (
        "mmcif-block-not-first",
        MMCIF,
        "1M17",
        reply(b"#\ndata_1M17\n"),
        "api_error",
        200,
        MMCIF_BAD,
        b"#\ndata_1M17\n",
    ),
    (
        "mmcif-redirect",
        MMCIF,
        "1M17",
        reply(b"", 302, {"location": "https://elsewhere.example/x"}),
        "http_error",
        302,
        REDIRECT.replace("{target}", "https://elsewhere.example/x").replace("{status}", "302"),
        b"",
    ),
    (
        "mmcif-redirect-without-location",
        MMCIF,
        "1M17",
        reply(b"", 301),
        "http_error",
        301,
        "HTTP 301 for {url} (redirect without a Location header; redirects are not followed)",
        b"",
    ),
    (
        "mmcif-not-modified",
        MMCIF,
        "1M17",
        reply(b"", 304),
        "http_error",
        304,
        "HTTP 304 for {url}",
        b"",
    ),
    (
        "mmcif-gzip-corrupt",
        MMCIF,
        "1M17",
        reply(b"this is not gzip", headers=GZIP),
        "api_error",
        200,
        "cannot decode gzip body for {url}",
        None,
    ),
    (
        "mmcif-encoding-br",
        MMCIF,
        "1M17",
        reply(b"xx", headers={"content-encoding": "br"}),
        "api_error",
        200,
        "unsupported content-encoding 'br' for {url}",
        None,
    ),
    ("entry-ok", ENTRY, "1M17", reply(entry_body("1M17")), "ok", 200, None, entry_body("1M17")),
    (
        "entry-404-json",
        ENTRY,
        "0ZZZ",
        reply(jbytes({"status": 404, "message": "No data found for entryId: 0ZZZ"}), 404),
        "http_error",
        404,
        "HTTP 404 for {url}",
        jbytes({"status": 404, "message": "No data found for entryId: 0ZZZ"}),
    ),
    ("entry-not-json", ENTRY, "1M17", reply(b"not json"), "api_error", 200, NOT_JSON, b"not json"),
    (
        "entry-not-utf8",
        ENTRY,
        "1M17",
        reply(b"\xff\xfe\x00"),
        "api_error",
        200,
        NOT_JSON,
        b"\xff\xfe\x00",
    ),
    (
        "entry-json-array",
        ENTRY,
        "1M17",
        reply(b"[1, 2]"),
        "api_error",
        200,
        "response JSON is not an object for {url}",
        b"[1, 2]",
    ),
    (
        "entry-other-id",
        ENTRY,
        "1M17",
        reply(entry_body("9ZZZ")),
        "api_error",
        200,
        ENTRY_MISMATCH.replace("{seen}", "'9ZZZ'"),
        entry_body("9ZZZ"),
    ),
    (
        "entry-id-missing",
        ENTRY,
        "1M17",
        reply(b"{}"),
        "api_error",
        200,
        ENTRY_MISMATCH.replace("{seen}", "None"),
        b"{}",
    ),
    (
        "entry-id-lowercase",
        ENTRY,
        "1M17",
        reply(jbytes({"rcsb_id": "1m17"})),
        "api_error",
        200,
        ENTRY_MISMATCH.replace("{seen}", "'1m17'"),
        jbytes({"rcsb_id": "1m17"}),
    ),
    (
        "entry-redirect-is-not-special",
        ENTRY,
        "1M17",
        reply(b"", 303, {"location": "/uniprotkb/P00533?from=1M17"}),
        "http_error",
        303,
        REDIRECT.replace("{target}", "/uniprotkb/P00533?from=1M17").replace("{status}", "303"),
        b"",
    ),
    (
        "mmcif-ok-x-gzip",
        MMCIF,
        "1M17",
        reply(gzip.compress(CIF), headers={"content-encoding": "x-gzip"}),
        "ok",
        200,
        None,
        CIF,
    ),
    (
        "mmcif-ok-padded-encoding",
        MMCIF,
        "1M17",
        reply(gzip.compress(CIF), headers={"content-encoding": " gzip "}),
        "ok",
        200,
        None,
        CIF,
    ),
    (
        "mmcif-gzip-truncated",
        MMCIF,
        "1M17",
        reply(gzip.compress(CIF)[:-6], headers=GZIP),
        "api_error",
        200,
        "cannot decode gzip body for {url}",
        None,
    ),
    (
        "mmcif-gzip-bad-stream",
        MMCIF,
        "1M17",
        reply(gzip.compress(CIF)[:10] + bytes([255]) * 20, headers=GZIP),
        "api_error",
        200,
        "cannot decode gzip body for {url}",
        None,
    ),
    (
        "mmcif-redirect-location-is-stripped",
        MMCIF,
        "1M17",
        reply(b"", 302, {"location": "  https://elsewhere.example/x  "}),
        "http_error",
        302,
        REDIRECT.replace("{target}", "https://elsewhere.example/x").replace("{status}", "302"),
        b"",
    ),
    (
        "uniprot-primary-empty",
        UNIPROT,
        "P00533",
        reply(jbytes({"primaryAccession": ""})),
        "api_error",
        200,
        "UniProt entry JSON has no primaryAccession for {url}",
        jbytes({"primaryAccession": ""}),
    ),
    (
        "uniprot-secondary-redirect-padded-location",
        UNIPROT,
        "P06268",
        reply(b"", 303, {"location": "  /uniprotkb/P00533?from=P06268  "}),
        "inactive_accession",
        303,
        SECONDARY_REDIRECT,
        b"",
    ),
    (
        "uniprot-redirect-wrong-path-with-from",
        UNIPROT,
        "P06268",
        reply(b"", 303, {"location": "/uniprotkb/search?from=P06268"}),
        "http_error",
        303,
        REDIRECT.replace("{target}", "/uniprotkb/search?from=P06268").replace("{status}", "303"),
        b"",
    ),
    (
        "graphql-ok",
        GRAPHQL,
        "1M17",
        reply(graphql_answer("1M17")),
        "ok",
        200,
        None,
        graphql_answer("1M17"),
    ),
    (
        "graphql-ok-other-entry-first",
        GRAPHQL,
        "1M17",
        reply(entries("1ABC", "1M17")),
        "ok",
        200,
        None,
        entries("1ABC", "1M17"),
    ),
    (
        "graphql-empty-list",
        GRAPHQL,
        "0ZZZ",
        reply(entries()),
        "unknown_id",
        200,
        GRAPHQL_NONE.replace("{key}", "0ZZZ"),
        entries(),
    ),
    (
        "graphql-only-another-entry",
        GRAPHQL,
        "1M17",
        reply(entries("1ABC")),
        "unknown_id",
        200,
        GRAPHQL_NONE.replace("{key}", "1M17"),
        entries("1ABC"),
    ),
    (
        "graphql-null-element",
        GRAPHQL,
        "1M17",
        reply(entries(None, "1ABC")),
        "unknown_id",
        200,
        GRAPHQL_NONE.replace("{key}", "1M17"),
        entries(None, "1ABC"),
    ),
    (
        "graphql-error",
        GRAPHQL,
        "1M17",
        reply(jbytes({"errors": [{"message": "Validation error (FieldUndefined)"}]})),
        "api_error",
        200,
        GRAPHQL_ERROR.replace("{text}", "Validation error (FieldUndefined)"),
        jbytes({"errors": [{"message": "Validation error (FieldUndefined)"}]}),
    ),
    (
        "graphql-error-beside-data",
        GRAPHQL,
        "1M17",
        reply(
            jbytes({"errors": [{"message": "partial"}], "data": {"entries": [{"rcsb_id": "1M17"}]}})
        ),
        "api_error",
        200,
        GRAPHQL_ERROR.replace("{text}", "partial"),
        jbytes({"errors": [{"message": "partial"}], "data": {"entries": [{"rcsb_id": "1M17"}]}}),
    ),
    (
        "graphql-error-long",
        GRAPHQL,
        "1M17",
        reply(jbytes({"errors": [{"message": "x" * 500}]})),
        "api_error",
        200,
        GRAPHQL_ERROR.replace("{text}", "x" * 300),
        jbytes({"errors": [{"message": "x" * 500}]}),
    ),
    (
        "graphql-error-plain-string",
        GRAPHQL,
        "1M17",
        reply(jbytes({"errors": ["boom"]})),
        "api_error",
        200,
        GRAPHQL_ERROR.replace("{text}", "boom"),
        jbytes({"errors": ["boom"]}),
    ),
    (
        "graphql-empty-errors-list",
        GRAPHQL,
        "1M17",
        reply(jbytes({"errors": [], "data": {"entries": [{"rcsb_id": "1M17"}]}})),
        "ok",
        200,
        None,
        jbytes({"errors": [], "data": {"entries": [{"rcsb_id": "1M17"}]}}),
    ),
    (
        "graphql-data-null",
        GRAPHQL,
        "1M17",
        reply(jbytes({"data": None})),
        "api_error",
        200,
        GRAPHQL_SHAPE,
        jbytes({"data": None}),
    ),
    (
        "graphql-entries-not-a-list",
        GRAPHQL,
        "1M17",
        reply(jbytes({"data": {"entries": {}}})),
        "api_error",
        200,
        GRAPHQL_SHAPE,
        jbytes({"data": {"entries": {}}}),
    ),
    (
        "graphql-http-400",
        GRAPHQL,
        "1M17",
        reply(jbytes({"errors": []}), 400),
        "http_error",
        400,
        "HTTP 400 for {url}",
        jbytes({"errors": []}),
    ),
    (
        "graphql-200-empty",
        GRAPHQL,
        "1M17",
        reply(b""),
        "empty_body",
        200,
        "empty response body (HTTP 200) for {url}",
        b"",
    ),
    (
        "uniprot-ok",
        UNIPROT,
        "P00533",
        reply(uniprot_body("P00533")),
        "ok",
        200,
        None,
        uniprot_body("P00533"),
    ),
    (
        "uniprot-deleted",
        UNIPROT,
        "Q9ZZZ9",
        reply(
            inactive(
                "Q9ZZZ9",
                {
                    "inactiveReasonType": "DELETED",
                    "deletedReason": "Not part of a reference proteome",
                },
            )
        ),
        "inactive_accession",
        200,
        INACTIVE.replace("{key}", "Q9ZZZ9").replace(
            "{detail}", "DELETED; deletedReason: Not part of a reference proteome"
        ),
        inactive(
            "Q9ZZZ9",
            {"inactiveReasonType": "DELETED", "deletedReason": "Not part of a reference proteome"},
        ),
    ),
    (
        "uniprot-demerged",
        UNIPROT,
        "O00688",
        reply(
            inactive(
                "O00688", {"inactiveReasonType": "DEMERGED", "mergeDemergeTo": ["P00533", "Q92795"]}
            )
        ),
        "inactive_accession",
        200,
        INACTIVE.replace("{key}", "O00688").replace(
            "{detail}", "DEMERGED; mergeDemergeTo: P00533, Q92795"
        ),
        inactive(
            "O00688", {"inactiveReasonType": "DEMERGED", "mergeDemergeTo": ["P00533", "Q92795"]}
        ),
    ),
    (
        "uniprot-inactive-without-reason",
        UNIPROT,
        "P00533",
        reply(jbytes({"entryType": "Inactive"})),
        "inactive_accession",
        200,
        INACTIVE.replace("{key}", "P00533").replace("{detail}", "unknown"),
        jbytes({"entryType": "Inactive"}),
    ),
    (
        "uniprot-secondary-redirect",
        UNIPROT,
        "P06268",
        reply(b"", 303, {"location": "/uniprotkb/P00533?from=P06268"}),
        "inactive_accession",
        303,
        SECONDARY_REDIRECT,
        b"",
    ),
    (
        "uniprot-secondary-redirect-json-suffix",
        UNIPROT,
        "P06268",
        reply(b"", 303, {"location": "/uniprotkb/P00533.json?from=P06268"}),
        "inactive_accession",
        303,
        SECONDARY_REDIRECT,
        b"",
    ),
    (
        "uniprot-secondary-in-body",
        UNIPROT,
        "P06268",
        reply(uniprot_body("P00533")),
        "inactive_accession",
        200,
        SECONDARY_BODY,
        uniprot_body("P00533"),
    ),
    (
        "uniprot-redirect-elsewhere",
        UNIPROT,
        "P06268",
        reply(b"", 303, {"location": "/uniprotkb/search?query=x"}),
        "http_error",
        303,
        REDIRECT.replace("{target}", "/uniprotkb/search?query=x").replace("{status}", "303"),
        b"",
    ),
    (
        "uniprot-redirect-for-another-accession",
        UNIPROT,
        "P06268",
        reply(b"", 303, {"location": "/uniprotkb/P00533?from=Q99999"}),
        "http_error",
        303,
        REDIRECT.replace("{target}", "/uniprotkb/P00533?from=Q99999").replace("{status}", "303"),
        b"",
    ),
    (
        "uniprot-404",
        UNIPROT,
        "Q00000",
        reply(jbytes({"messages": ["Resource not found"]}), 404),
        "http_error",
        404,
        "HTTP 404 for {url}",
        jbytes({"messages": ["Resource not found"]}),
    ),
    (
        "uniprot-no-primary-accession",
        UNIPROT,
        "P00533",
        reply(b"{}"),
        "api_error",
        200,
        "UniProt entry JSON has no primaryAccession for {url}",
        b"{}",
    ),
    (
        "uniprot-primary-not-a-string",
        UNIPROT,
        "P00533",
        reply(jbytes({"primaryAccession": 5})),
        "api_error",
        200,
        "UniProt entry JSON has no primaryAccession for {url}",
        jbytes({"primaryAccession": 5}),
    ),
    (
        "uniprot-not-json",
        UNIPROT,
        "P00533",
        reply(b"<html>"),
        "api_error",
        200,
        NOT_JSON,
        b"<html>",
    ),
]


@pytest.mark.parametrize(
    ("role", "key", "answer", "outcome", "status", "template", "decoded"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_every_response_is_classified(
    role, key, answer, outcome, status, template, decoded
) -> None:
    retrieval, fetcher, clock = run(role, key, answer)
    url = URL[role](key)
    assert isinstance(retrieval, Retrieval)
    assert (retrieval.role, retrieval.key, retrieval.url) == (role, key, url)
    assert (retrieval.outcome, retrieval.http_status) == (outcome, status)
    assert retrieval.ok == (outcome == "ok")
    expected_message = None if template is None else template.format(url=url)
    assert retrieval.message == expected_message
    assert retrieval.body == (decoded if outcome == "ok" else None)
    if decoded is None:
        assert (retrieval.size, retrieval.sha256) == (None, None)
    else:
        assert (retrieval.size, retrieval.sha256) == (len(decoded), sha(decoded))
    assert retrieval.fetched_at_utc == "2026-11-08T06:00:00Z"
    assert clock.calls == 1
    assert len(fetcher.calls) == 1


# --- everything else about one retrieval -----------------------------------------------------


@pytest.mark.parametrize("role", [MMCIF, ENTRY, GRAPHQL, UNIPROT])
def test_a_network_failure_is_recorded(role) -> None:
    key = "P00533" if role == UNIPROT else "1M17"
    retrieval, _, clock = run(role, key, NetworkError("timed out"))
    url = URL[role](key)
    assert retrieval.outcome == "network_error"
    assert retrieval.message == f"network error for {url}: timed out"
    assert (retrieval.http_status, retrieval.size, retrieval.sha256, retrieval.body) == (
        None,
        None,
        None,
        None,
    )
    assert retrieval.headers == {}
    assert retrieval.fetched_at_utc == "2026-11-08T06:00:00Z"
    assert clock.calls == 1


def test_other_exceptions_are_not_swallowed() -> None:
    with pytest.raises(RuntimeError, match="bug"):
        run(MMCIF, "1M17", RuntimeError("bug"))


@pytest.mark.parametrize(
    ("role", "key", "method", "has_body"),
    [
        (MMCIF, "1M17", "GET", False),
        (GRAPHQL, "1M17", "POST", True),
        (UNIPROT, "P00533", "GET", False),
    ],
)
def test_the_request_reaches_the_fetcher_unchanged(role, key, method, has_body) -> None:
    answer = {
        MMCIF: reply(CIF),
        GRAPHQL: reply(graphql_answer(key)),
        UNIPROT: reply(uniprot_body(key)),
    }[role]
    retrieval, fetcher, _ = run(role, key, answer, timeout=12.5)
    (call,) = fetcher.calls
    expected = endpoints.build_request(role, key, 12.5)
    assert call == expected
    assert call.method == method
    assert retrieval.method == method
    if has_body:
        assert retrieval.request_body_sha256 == sha(call.body)
    else:
        assert call.body is None
        assert retrieval.request_body_sha256 is None


def test_default_timeout_is_sixty_seconds() -> None:
    _, fetcher, _ = run(MMCIF, "1M17", reply(CIF))
    assert fetcher.calls[0].timeout == 60.0


def test_only_whitelisted_headers_are_kept_stripped_and_lowercased() -> None:
    headers = {
        "Date": "Sun, 08 Nov 2026 06:00:00 GMT ",
        "Content-Type": "chemical/x-cif",
        "Set-Cookie": "a=b",
        "ETag": 'W/"x"',
        "X-UniProt-Release": "2026_04",
        "x-api-deployment-date": "  ",
        "last-modified": "",
        "Content-Length": "28",
    }
    retrieval, _, _ = run(MMCIF, "1M17", reply(CIF, headers=headers))
    assert retrieval.headers == {
        "date": "Sun, 08 Nov 2026 06:00:00 GMT",
        "etag": 'W/"x"',
        "x-uniprot-release": "2026_04",
    }


def test_headers_are_kept_on_failures_too() -> None:
    retrieval, _, _ = run(
        MMCIF, "1M17", reply(b"nope", 404, {"Date": "D", "x-uniprot-release": "R"})
    )
    assert retrieval.headers == {"date": "D", "x-uniprot-release": "R"}


def test_as_request_of_an_ok_retrieval() -> None:
    retrieval, _, _ = run(
        UNIPROT, "P00533", reply(uniprot_body("P00533"), headers={"x-uniprot-release": "2026_04"})
    )
    assert retrieval.as_request("r4", "uniprot/P00533.json") == {
        "request_id": "r4",
        "role": "uniprot_entry",
        "method": "GET",
        "url": "https://rest.uniprot.org/uniprotkb/P00533.json",
        "request_body_sha256": None,
        "fetched_at_utc": "2026-11-08T06:00:00Z",
        "http_status": 200,
        "outcome": "ok",
        "bytes": len(uniprot_body("P00533")),
        "sha256": sha(uniprot_body("P00533")),
        "headers": {"x-uniprot-release": "2026_04"},
        "frozen_file": "uniprot/P00533.json",
    }


def test_as_request_of_a_failed_retrieval() -> None:
    retrieval, _, _ = run(GRAPHQL, "0ZZZ", reply(entries()))
    assert retrieval.as_request("r8", None) == {
        "request_id": "r8",
        "role": "rcsb_graphql",
        "method": "POST",
        "url": "https://data.rcsb.org/graphql",
        "request_body_sha256": sha(endpoints.graphql_body("0ZZZ")),
        "fetched_at_utc": "2026-11-08T06:00:00Z",
        "http_status": 200,
        "outcome": "unknown_id",
        "message": GRAPHQL_NONE.replace("{key}", "0ZZZ").format(url=GRAPHQL_URL),
        "bytes": len(entries()),
        "sha256": sha(entries()),
        "headers": {},
        "frozen_file": None,
    }


@pytest.mark.parametrize("status", [200, 201, 202, 299])
def test_every_2xx_status_with_a_valid_body_is_ok(status) -> None:
    retrieval, _, _ = run(MMCIF, "1M17", reply(CIF, status))
    assert (retrieval.outcome, retrieval.http_status, retrieval.body) == ("ok", status, CIF)


@pytest.mark.parametrize("status", [100, 199, 300, 304, 305, 400, 404, 429, 500, 503])
def test_every_other_status_is_an_http_error(status) -> None:
    retrieval, _, _ = run(MMCIF, "1M17", reply(CIF, status))
    assert (retrieval.outcome, retrieval.http_status, retrieval.body) == (
        "http_error",
        status,
        None,
    )
    assert retrieval.message == f"HTTP {status} for {mmcif_url('1M17')}"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_every_redirect_status_is_named_as_a_redirect(status) -> None:
    retrieval, _, _ = run(MMCIF, "1M17", reply(b"", status, {"location": "/x"}))
    assert retrieval.outcome == "http_error"
    assert retrieval.message == (
        f"HTTP {status} for {mmcif_url('1M17')} (redirect to /x; redirects are not followed)"
    )


def test_a_204_without_content_is_an_empty_body() -> None:
    retrieval, _, _ = run(MMCIF, "1M17", reply(b"", 204))
    assert retrieval.outcome == "empty_body"
    assert retrieval.message == f"empty response body (HTTP 204) for {mmcif_url('1M17')}"


def test_the_clock_is_read_after_the_response_arrives() -> None:
    for answer, outcome in [(reply(CIF), "ok"), (NetworkError("down"), "network_error")]:
        clock = FakeClock()
        seen = []
        inner = FakeFetcher({("GET", mmcif_url("1M17")): answer})

        def spy(request, inner=inner, clock=clock, seen=seen):
            seen.append(clock.calls)
            return inner(request)

        retrieval = retrieve(MMCIF, "1M17", fetcher=spy, now=clock)
        assert retrieval.outcome == outcome
        assert seen == [0]
        assert clock.calls == 1
