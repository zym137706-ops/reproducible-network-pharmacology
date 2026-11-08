"""Freezing an acquisition run and verifying it offline (ADR-0005). Offline."""

from __future__ import annotations

import hashlib
import inspect
import json
import socket
from pathlib import Path

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
    ok_fetcher,
    ok_routes,
    reply,
    uniprot_body,
    uniprot_url,
)
from jsonschema import Draft202012Validator

from rnp import acquire as package
from rnp.acquire import freeze
from rnp.acquire.endpoints import GRAPHQL_QUERY
from rnp.acquire.transport import NetworkError, urllib_fetcher
from rnp.config import load_schema
from rnp.errors import InputError, SchemaViolation
from rnp.provenance import package_version


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a unit test tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_schema_valid(record) -> None:
    validator = Draft202012Validator(load_schema("acquisition_record"))
    assert [error.message for error in validator.iter_errors(record)] == []


def tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def graphql_by_id(known):
    """A GraphQL answer that, like RCSB, silently drops IDs it does not know."""

    def answer(pdb_id):
        if pdb_id in known:
            return reply(graphql_answer(pdb_id))
        return reply(json.dumps({"data": {"entries": []}}).encode())

    return answer


def inactive_routes():
    body = {
        "entryType": "Inactive",
        "primaryAccession": "O00688",
        "inactiveReason": {
            "inactiveReasonType": "DEMERGED",
            "mergeDemergeTo": ["P00533", "Q92795"],
        },
    }
    return {("GET", uniprot_url("O00688")): reply(json.dumps(body).encode())}


@pytest.fixture
def one(tmp_path):
    """A complete acquisition of 1M17 / P00533."""
    fetcher = FakeFetcher(ok_routes("1M17", "P00533"))
    result = freeze.acquire(
        [("1M17", "P00533")], tmp_path / "out", fetcher=fetcher, now=FakeClock()
    )
    return result, fetcher


@pytest.fixture
def two(tmp_path):
    """A partial acquisition: 1M17 / P00533 is complete, 1M17 / O00688 failed."""
    pairs = [("1M17", "P00533"), ("1M17", "O00688")]
    fetcher = ok_fetcher(pairs[:1], inactive_routes())
    return freeze.acquire(pairs, tmp_path / "two", fetcher=fetcher, now=FakeClock())


@pytest.fixture
def three(tmp_path):
    """A partial acquisition of three items: complete, complete, failed."""
    pairs = [("1M17", "P00533"), ("3POZ", "P00533"), ("1M17", "O00688")]
    fetcher = ok_fetcher(pairs[:2], inactive_routes())
    return freeze.acquire(pairs, tmp_path / "three", fetcher=fetcher, now=FakeClock())


# --- a complete run --------------------------------------------------------------------------


def test_a_complete_run_writes_the_frozen_files_and_the_record(one) -> None:
    result, _ = one
    root = result.out_dir
    assert result.status == "complete"
    assert result.record_path == root / "acquisition_record.json"
    assert freeze.RECORD_FILENAME == "acquisition_record.json"
    files = tree(root)
    assert sorted(files) == [
        "1M17/1M17.cif",
        "1M17/rcsb_entry.json",
        "1M17/rcsb_graphql.json",
        "acquisition_record.json",
        "uniprot/P00533.json",
    ]
    assert files["1M17/1M17.cif"] == cif_body("1M17")
    assert files["1M17/rcsb_entry.json"] == entry_body("1M17")
    assert files["1M17/rcsb_graphql.json"] == graphql_answer("1M17")
    assert files["uniprot/P00533.json"] == uniprot_body("P00533")
    assert json.loads(files["acquisition_record.json"]) == result.record
    assert files["acquisition_record.json"].endswith(b"\n")
    assert not list(root.glob("*.tmp"))


def test_the_record_of_a_complete_run_is_exact(one) -> None:
    result, _ = one
    graphql_request = json.dumps(
        {"query": GRAPHQL_QUERY, "variables": {"ids": ["1M17"]}},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    def request(number, role, method, url, body, frozen, headers, when, request_hash=None):
        return {
            "request_id": f"r{number}",
            "role": role,
            "method": method,
            "url": url,
            "request_body_sha256": request_hash,
            "fetched_at_utc": when,
            "http_status": 200,
            "outcome": "ok",
            "bytes": len(body),
            "sha256": sha(body),
            "headers": headers,
            "frozen_file": frozen,
        }

    assert result.record == {
        "schema_version": "1.0",
        "acquisition_id": f"20261108T060000Z_{sha(b'1M17:P00533')[:8]}",
        "tool": {"name": "reproducible-network-pharmacology", "version": package_version()},
        "started_at_utc": "2026-11-08T06:00:00Z",
        "finished_at_utc": "2026-11-08T06:00:05Z",
        "status": "complete",
        "items": [
            {
                "item_id": "i1",
                "pdb_id": "1M17",
                "uniprot_accession": "P00533",
                "status": "complete",
                "request_ids": ["r1", "r2", "r3", "r4"],
            }
        ],
        "requests": [
            request(
                1,
                "structure_mmcif",
                "GET",
                mmcif_url("1M17"),
                cif_body("1M17"),
                "1M17/1M17.cif",
                {"last-modified": "L"},
                "2026-11-08T06:00:01Z",
            ),
            request(
                2,
                "rcsb_entry",
                "GET",
                entry_url("1M17"),
                entry_body("1M17"),
                "1M17/rcsb_entry.json",
                {},
                "2026-11-08T06:00:02Z",
            ),
            request(
                3,
                "rcsb_graphql",
                "POST",
                GRAPHQL_URL,
                graphql_answer("1M17"),
                "1M17/rcsb_graphql.json",
                {},
                "2026-11-08T06:00:03Z",
                sha(graphql_request),
            ),
            request(
                4,
                "uniprot_entry",
                "GET",
                uniprot_url("P00533"),
                uniprot_body("P00533"),
                "uniprot/P00533.json",
                {"x-uniprot-release": "2026_04"},
                "2026-11-08T06:00:04Z",
            ),
        ],
        "warnings": [],
    }
    assert_schema_valid(result.record)


def test_requests_are_made_in_a_fixed_order(one) -> None:
    _, fetcher = one
    assert [(call.method, call.url) for call in fetcher.calls] == [
        ("GET", mmcif_url("1M17")),
        ("GET", entry_url("1M17")),
        ("POST", GRAPHQL_URL),
        ("GET", uniprot_url("P00533")),
    ]


def test_the_clock_is_read_for_the_start_each_response_and_the_finish(tmp_path) -> None:
    clock = FakeClock()
    fetcher = FakeFetcher(ok_routes("1M17", "P00533"))
    result = freeze.acquire([("1M17", "P00533")], tmp_path / "out", fetcher=fetcher, now=clock)
    assert clock.calls == 6
    assert result.record["started_at_utc"] == "2026-11-08T06:00:00Z"
    assert result.record["finished_at_utc"] == "2026-11-08T06:00:05Z"


def test_the_default_acquisition_id_comes_from_the_start_time_and_the_sorted_items(
    tmp_path,
) -> None:
    pairs = [("6VXX", "P0DTC2"), ("1M17", "P00533")]
    fetcher = ok_fetcher(pairs)
    result = freeze.acquire(pairs, tmp_path / "a", fetcher=fetcher, now=FakeClock())
    assert (
        result.record["acquisition_id"]
        == f"20261108T060000Z_{sha(b'1M17:P00533' + chr(10).encode() + b'6VXX:P0DTC2')[:8]}"
    )
    other = freeze.acquire(
        pairs, tmp_path / "b", fetcher=fetcher, now=FakeClock(), acquisition_id="my-run.1"
    )
    assert other.record["acquisition_id"] == "my-run.1"


def test_the_timeout_reaches_every_request(tmp_path) -> None:
    fetcher = FakeFetcher(ok_routes("1M17", "P00533"))
    freeze.acquire([("1M17", "P00533")], tmp_path / "out", fetcher=fetcher, timeout=7.5)
    assert [call.timeout for call in fetcher.calls] == [7.5, 7.5, 7.5, 7.5]


def test_the_default_fetcher_is_the_urllib_fetcher() -> None:
    parameter = inspect.signature(freeze.acquire).parameters["fetcher"]
    assert parameter.default is urllib_fetcher
    assert package.acquire is freeze.acquire
    assert package.verify_acquisition is freeze.verify_acquisition
    assert package.urllib_fetcher is urllib_fetcher
    assert package.RECORD_FILENAME == "acquisition_record.json"


# --- shared requests, partial and failed runs ------------------------------------------------


def test_items_that_share_a_request_retrieve_it_once(tmp_path) -> None:
    pairs = [("1M17", "P00533"), ("3POZ", "P00533")]
    fetcher = ok_fetcher(pairs)
    result = freeze.acquire(pairs, tmp_path / "out", fetcher=fetcher)
    assert result.status == "complete"
    assert fetcher.urls.count(uniprot_url("P00533")) == 1
    assert len(fetcher.calls) == 7
    items = result.record["items"]
    assert [item["item_id"] for item in items] == ["i1", "i2"]
    assert [item["request_ids"] for item in items] == [
        ["r1", "r2", "r3", "r4"],
        ["r5", "r6", "r7", "r4"],
    ]
    assert [entry["request_id"] for entry in result.record["requests"]] == [
        f"r{number}" for number in range(1, 8)
    ]
    assert sorted(tree(result.out_dir)) == [
        "1M17/1M17.cif",
        "1M17/rcsb_entry.json",
        "1M17/rcsb_graphql.json",
        "3POZ/3POZ.cif",
        "3POZ/rcsb_entry.json",
        "3POZ/rcsb_graphql.json",
        "acquisition_record.json",
        "uniprot/P00533.json",
    ]
    assert_schema_valid(result.record)


def test_one_good_and_one_bad_item_give_a_partial_run(two) -> None:
    assert two.status == "partial"
    assert two.record["status"] == "partial"
    assert [item["status"] for item in two.record["items"]] == ["complete", "failed"]
    assert two.record["items"][1]["request_ids"] == ["r1", "r2", "r3", "r5"]
    failed = two.record["requests"][4]
    assert (failed["request_id"], failed["outcome"], failed["frozen_file"]) == (
        "r5",
        "inactive_accession",
        None,
    )
    assert two.record["warnings"] == [failed["message"]]
    assert "uniprot/O00688.json" not in tree(two.out_dir)
    assert_schema_valid(two.record)


def test_a_failed_item_keeps_the_files_that_did_arrive(tmp_path) -> None:
    routes = {
        ("GET", mmcif_url("0ZZZ")): reply(b"<html>404</html>", 404),
        ("GET", entry_url("0ZZZ")): reply(b'{"status":404}', 404),
        ("GET", uniprot_url("P00533")): reply(uniprot_body("P00533")),
    }
    fetcher = FakeFetcher(routes, graphql=graphql_by_id(set()))
    result = freeze.acquire([("0ZZZ", "P00533")], tmp_path / "out", fetcher=fetcher)
    assert result.status == "failed"
    assert result.record["items"][0]["status"] == "failed"
    outcomes = [entry["outcome"] for entry in result.record["requests"]]
    assert outcomes == ["http_error", "http_error", "unknown_id", "ok"]
    assert sorted(tree(result.out_dir)) == ["acquisition_record.json", "uniprot/P00533.json"]
    assert result.record["warnings"] == [
        entry["message"] for entry in result.record["requests"] if "message" in entry
    ]
    assert len(result.record["warnings"]) == 3
    assert_schema_valid(result.record)


def test_a_run_where_nothing_arrives_is_failed_and_freezes_nothing(tmp_path) -> None:
    down = NetworkError("connection refused")
    fetcher = FakeFetcher(
        {
            ("GET", mmcif_url("1M17")): down,
            ("GET", entry_url("1M17")): down,
            ("POST", GRAPHQL_URL): down,
            ("GET", uniprot_url("P00533")): down,
        }
    )
    result = freeze.acquire([("1M17", "P00533")], tmp_path / "out", fetcher=fetcher)
    assert result.status == "failed"
    assert [entry["outcome"] for entry in result.record["requests"]] == ["network_error"] * 4
    assert [entry["http_status"] for entry in result.record["requests"]] == [None] * 4
    assert sorted(tree(result.out_dir)) == ["acquisition_record.json"]
    assert result.record["warnings"][0] == (
        f"network error for {mmcif_url('1M17')}: connection refused"
    )
    assert_schema_valid(result.record)


def test_a_network_failure_in_the_middle_does_not_stop_the_run(tmp_path) -> None:
    routes = ok_routes("1M17", "P00533")
    routes[("GET", entry_url("1M17"))] = NetworkError("timed out")
    fetcher = FakeFetcher(routes)
    result = freeze.acquire([("1M17", "P00533")], tmp_path / "out", fetcher=fetcher)
    assert len(fetcher.calls) == 4
    outcomes = [entry["outcome"] for entry in result.record["requests"]]
    assert outcomes == ["ok", "network_error", "ok", "ok"]
    assert result.status == "failed"


def test_one_run_can_record_every_outcome_and_every_recorded_header(tmp_path) -> None:
    properties = load_schema("acquisition_record")["$defs"]["request"]["properties"]
    all_outcomes = set(properties["outcome"]["enum"])
    all_headers = set(properties["headers"]["propertyNames"]["enum"])
    assert len(all_outcomes) == 7 and len(all_headers) == 6
    headers = {
        "date": "Sun, 08 Nov 2026 06:00:00 GMT",
        "last-modified": "Mon, 22 Sep 2025 00:17:19 GMT",
        "etag": 'W/"x"',
        "x-uniprot-release": "2026_04",
        "x-uniprot-release-date": "04-November-2026",
        "x-api-deployment-date": "07-November-2026",
    }
    secondary = {"location": "/uniprotkb/P00533?from=P06268"}
    routes = {
        ("GET", mmcif_url("1M17")): reply(cif_body("1M17"), headers=headers),
        ("GET", entry_url("1M17")): reply(entry_body("1M17")),
        ("GET", uniprot_url("P00533")): reply(uniprot_body("P00533"), headers=headers),
        ("GET", mmcif_url("6VXX")): reply(b""),
        ("GET", entry_url("6VXX")): reply(b"not json"),
        ("GET", uniprot_url("P06268")): reply(b"", 303, secondary),
        ("GET", mmcif_url("0ZZZ")): reply(b"<html>404</html>", 404),
        ("GET", entry_url("0ZZZ")): NetworkError("timed out"),
        ("GET", uniprot_url("Q00000")): reply(b"{}", 404),
    }
    fetcher = FakeFetcher(routes, graphql=graphql_by_id({"1M17", "6VXX"}))
    pairs = [("1M17", "P00533"), ("6VXX", "P06268"), ("0ZZZ", "Q00000")]
    result = freeze.acquire(pairs, tmp_path / "out", fetcher=fetcher)
    requests = result.record["requests"]
    assert result.status == "partial"
    assert {entry["outcome"] for entry in requests} == all_outcomes
    assert {name for entry in requests for name in entry["headers"]} == all_headers
    assert_schema_valid(result.record)
    assert freeze.verify_acquisition(result.out_dir) == []


# --- input and output directory errors -------------------------------------------------------


def _refuses(items, tmp_path, details):
    fetcher = FakeFetcher()
    clock = FakeClock()
    target = tmp_path / "out"
    with pytest.raises(InputError) as caught:
        freeze.acquire(items, target, fetcher=fetcher, now=clock)
    assert caught.value.message == "invalid acquisition input"
    assert caught.value.details == details
    assert caught.value.exit_code == 2
    assert not target.exists()
    assert fetcher.calls == [] and clock.calls == 0


def test_no_items_are_refused(tmp_path) -> None:
    _refuses([], tmp_path, ["no items given"])


def test_bad_identifiers_and_duplicates_are_refused_before_anything_happens(tmp_path) -> None:
    _refuses(
        [("1m17", "P00533"), ("1M17", "P00533-2"), ("1M17", "P00533"), ("1M17", "P00533")],
        tmp_path,
        [
            "item 1: PDB ID '1m17' must match ^[0-9][A-Z0-9]{3}$",
            "item 2: UniProt accession 'P00533-2' must be a canonical accession without an isoform "
            "suffix (^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$)",
            "item 4: duplicate of item 3",
        ],
    )


def test_malformed_items_are_refused(tmp_path) -> None:
    _refuses(["1M17"], tmp_path, ["item 1: expected (pdb_id, uniprot_accession)"])
    _refuses([("1M17",)], tmp_path, ["item 1: expected (pdb_id, uniprot_accession)"])


def test_a_non_empty_output_directory_is_refused(tmp_path) -> None:
    target = tmp_path / "out"
    target.mkdir()
    (target / "keep.txt").write_text("x")
    fetcher = FakeFetcher()
    with pytest.raises(InputError, match="output directory is not empty"):
        freeze.acquire([("1M17", "P00533")], target, fetcher=fetcher)
    assert fetcher.calls == []
    assert (target / "keep.txt").read_text() == "x"


def test_an_output_path_that_is_a_file_is_refused(tmp_path) -> None:
    target = tmp_path / "out"
    target.write_text("x")
    with pytest.raises(InputError, match="output path exists and is not a directory"):
        freeze.acquire([("1M17", "P00533")], target, fetcher=FakeFetcher())


def test_an_empty_or_missing_output_directory_is_accepted(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    for target in (empty, tmp_path / "deep" / "er" / "out"):
        fetcher = FakeFetcher(ok_routes("1M17", "P00533"))
        assert freeze.acquire([("1M17", "P00533")], target, fetcher=fetcher).status == "complete"


def test_a_second_run_into_the_same_directory_is_refused(tmp_path) -> None:
    target = tmp_path / "out"
    fetcher = FakeFetcher(ok_routes("1M17", "P00533"))
    freeze.acquire([("1M17", "P00533")], target, fetcher=fetcher)
    before = tree(target)
    with pytest.raises(InputError, match="output directory is not empty"):
        freeze.acquire([("1M17", "P00533")], target, fetcher=fetcher)
    assert tree(target) == before


def test_a_bug_in_the_fetcher_propagates_and_leaves_no_record(tmp_path) -> None:
    routes = ok_routes("1M17", "P00533")
    routes[("GET", entry_url("1M17"))] = RuntimeError("bug")
    with pytest.raises(RuntimeError, match="bug"):
        freeze.acquire([("1M17", "P00533")], tmp_path / "out", fetcher=FakeFetcher(routes))
    assert not (tmp_path / "out" / "acquisition_record.json").exists()


def test_a_record_that_breaks_its_own_schema_is_an_internal_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(freeze, "package_version", lambda: "")
    fetcher = FakeFetcher(ok_routes("1M17", "P00533"))
    with pytest.raises(SchemaViolation) as caught:
        freeze.acquire([("1M17", "P00533")], tmp_path / "out", fetcher=fetcher)
    assert caught.value.exit_code == 1
    assert any("tool.version" in detail for detail in caught.value.details)
    assert not (tmp_path / "out" / "acquisition_record.json").exists()


# --- offline verification --------------------------------------------------------------------


def rewrite(result, change) -> None:
    record = json.loads(result.record_path.read_text(encoding="utf-8"))
    change(record)
    result.record_path.write_text(json.dumps(record), encoding="utf-8")


def test_a_clean_directory_verifies(one, two, three) -> None:
    assert freeze.verify_acquisition(one[0].out_dir) == []
    assert freeze.verify_acquisition(str(two.out_dir)) == []
    assert freeze.verify_acquisition(three.out_dir) == []


def test_verification_changes_nothing(one) -> None:
    before = tree(one[0].out_dir)
    freeze.verify_acquisition(one[0].out_dir)
    assert tree(one[0].out_dir) == before


def test_a_modified_file_is_reported_with_the_request_the_url_and_the_hashes(one) -> None:
    result, _ = one
    changed = cif_body("1M17").replace(b"1M17 ", b"1M18 ")
    (result.out_dir / "1M17" / "1M17.cif").write_bytes(changed)
    assert freeze.verify_acquisition(result.out_dir) == [
        f"r1 {mmcif_url('1M17')}: sha256 of 1M17/1M17.cif is {sha(changed)}, "
        f"the record says {sha(cif_body('1M17'))}"
    ]


def test_a_truncated_file_is_reported_by_size_and_hash(one) -> None:
    result, _ = one
    shortened = uniprot_body("P00533")[:-3]
    (result.out_dir / "uniprot" / "P00533.json").write_bytes(shortened)
    problems = freeze.verify_acquisition(result.out_dir)
    assert problems == [
        f"r4 {uniprot_url('P00533')}: uniprot/P00533.json has {len(shortened)} bytes, "
        f"the record says {len(uniprot_body('P00533'))}",
        f"r4 {uniprot_url('P00533')}: sha256 of uniprot/P00533.json is {sha(shortened)}, "
        f"the record says {sha(uniprot_body('P00533'))}",
    ]


def test_a_missing_file_is_reported(one) -> None:
    result, _ = one
    (result.out_dir / "1M17" / "rcsb_entry.json").unlink()
    assert freeze.verify_acquisition(result.out_dir) == [
        f"r2 {entry_url('1M17')}: frozen file 1M17/rcsb_entry.json is missing"
    ]


def test_an_unlisted_file_is_reported(one) -> None:
    result, _ = one
    (result.out_dir / "1M17" / "notes.txt").write_text("x")
    (result.out_dir / "stray.bin").write_bytes(b"x")
    assert freeze.verify_acquisition(result.out_dir) == [
        "1M17/notes.txt: unexpected file not listed in the record",
        "stray.bin: unexpected file not listed in the record",
    ]


def test_a_missing_directory_or_record_is_reported(tmp_path) -> None:
    nothing = tmp_path / "nothing"
    assert freeze.verify_acquisition(nothing) == [f"{nothing}: not a directory"]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert freeze.verify_acquisition(empty) == [f"acquisition_record.json: missing in {empty}"]


def test_an_unreadable_record_is_reported(one) -> None:
    result, _ = one
    result.record_path.write_text("{not json", encoding="utf-8")
    (problem,) = freeze.verify_acquisition(result.out_dir)
    assert problem.startswith("acquisition_record.json: cannot be read as JSON: ")


def test_a_record_that_breaks_the_schema_is_reported_and_nothing_else_is_checked(one) -> None:
    result, _ = one
    rewrite(result, lambda record: record.pop("status"))
    (result.out_dir / "stray.bin").write_bytes(b"x")
    assert freeze.verify_acquisition(result.out_dir) == [
        "schema: <root>: 'status' is a required property"
    ]


def test_schema_problems_name_their_location(one) -> None:
    result, _ = one
    rewrite(result, lambda record: record["requests"][0].__setitem__("sha256", "ABC"))
    problems = freeze.verify_acquisition(result.out_dir)
    assert len(problems) >= 2
    assert all(problem.startswith("schema: requests/0/sha256: ") for problem in problems)
    assert problems == sorted(problems)


def test_a_run_status_that_the_items_contradict_fails_the_schema(two) -> None:
    rewrite(two, lambda record: record.__setitem__("status", "complete"))
    problems = freeze.verify_acquisition(two.out_dir)
    assert problems
    assert all(problem.startswith("schema: ") for problem in problems)


def test_an_item_marked_failed_whose_requests_all_succeeded_is_reported(one) -> None:
    def tamper(record):
        record["items"][0]["status"] = "failed"
        record["status"] = "failed"

    rewrite(one[0], tamper)
    assert freeze.verify_acquisition(one[0].out_dir) == [
        "i1: status is failed but its requests give complete"
    ]


def test_an_item_marked_complete_with_a_failed_request_is_reported(three) -> None:
    failed_id = three.record["items"][2]["request_ids"][3]
    assert three.record["requests"][int(failed_id[1:]) - 1]["outcome"] == "inactive_accession"
    rewrite(three, lambda record: record["items"][1]["request_ids"].__setitem__(3, failed_id))
    assert freeze.verify_acquisition(three.out_dir) == [
        "i2: status is complete but its requests give failed"
    ]


def test_an_unknown_request_id_in_an_item_is_reported(one) -> None:
    result, _ = one
    rewrite(result, lambda record: record["items"][0]["request_ids"].__setitem__(3, "r9"))
    assert freeze.verify_acquisition(result.out_dir) == [
        "i1: request_id r9 is not in requests",
        f"r4 {uniprot_url('P00533')}: not referenced by any item",
    ]


def test_duplicate_request_ids_are_reported(one) -> None:
    result, _ = one
    rewrite(result, lambda record: record["requests"][1].__setitem__("request_id", "r1"))
    assert "requests: duplicate request_id r1" in freeze.verify_acquisition(result.out_dir)


def test_a_frozen_path_used_twice_is_reported(one) -> None:
    result, _ = one
    rewrite(
        result, lambda record: record["requests"][1].__setitem__("frozen_file", "1M17/1M17.cif")
    )
    problems = freeze.verify_acquisition(result.out_dir)
    assert "requests: frozen_file 1M17/1M17.cif is used by more than one request" in problems
