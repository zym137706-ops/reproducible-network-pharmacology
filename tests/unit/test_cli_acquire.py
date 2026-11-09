"""The `rnp acquire` command: arguments, summary, exit codes and offline verification (ADR-0005).

Offline: the fetcher and the clock are replaced where the command looks them up
(`rnp.cli.urllib_fetcher` and `rnp.cli.utc_now_iso`), and a guard fails any real connection.
"""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest
from acquire_support import (
    FakeClock,
    FakeFetcher,
    entry_url,
    mmcif_url,
    ok_fetcher,
    ok_routes,
    reply,
    uniprot_url,
)

import rnp.acquire
import rnp.cli
import rnp.provenance
from rnp.acquire import freeze
from rnp.acquire.endpoints import PDB_ID_REGEX, UNIPROT_ACCESSION_REGEX
from rnp.acquire.transport import NetworkError
from rnp.cli import build_parser, main

RECORD = "acquisition_record.json"
ARGS_HEADER = "invalid arguments for 'rnp acquire'"
NO_OUT = "--out is required unless --verify is given"
NO_ITEMS = "no items given; pass one or more PDB_ID:UNIPROT_ACCESSION pairs"
BAD_TIMEOUT = "--timeout must be a positive, finite number of seconds"
CONFLICT = "--verify cannot be combined with --out, --timeout or items"
E_ACUTE = chr(233)  # a character that is not ASCII, built without writing it in this file


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempts = []

    def refuse(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("a unit test tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield
    assert attempts == []


def install(monkeypatch, fetcher):
    """Put a fetcher and a fake clock where `rnp acquire` looks them up; return the clock."""
    clock = FakeClock()
    monkeypatch.setattr(rnp.cli, "urllib_fetcher", fetcher)
    monkeypatch.setattr(rnp.cli, "utc_now_iso", clock)
    return clock


def run(capsys, *argv):
    code = main(["acquire", *[str(part) for part in argv]])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def inactive(accession: str, **reason):
    """UniProt answers for an inactive accession."""
    body = {
        "entryType": "Inactive",
        "primaryAccession": accession,
        "inactiveReason": {"inactiveReasonType": "DELETED", **reason},
    }
    return {("GET", uniprot_url(accession)): reply(json.dumps(body).encode())}


def item(item_id, pdb_id, accession, status):
    return {
        "item_id": item_id,
        "pdb_id": pdb_id,
        "uniprot_accession": accession,
        "status": status,
    }


@pytest.fixture
def frozen(tmp_path, monkeypatch, capsys):
    """A complete acquisition of 1M17 / P00533 made through the command."""
    install(monkeypatch, ok_fetcher([("1M17", "P00533")]))
    out = tmp_path / "frozen"
    code, _, stderr = run(capsys, "--out", out, "1M17:P00533")
    assert (code, stderr) == (0, "")
    return out


@pytest.fixture
def partial(tmp_path, monkeypatch, capsys):
    """A partial acquisition made through the command: 1M17 / P00533 complete, 1M17 / O00688 not."""
    fetcher = ok_fetcher([("1M17", "P00533")], inactive("O00688", deletedReason="withdrawn"))
    install(monkeypatch, fetcher)
    out = tmp_path / "partial"
    code, stdout, _ = run(capsys, "--out", out, "1M17:P00533", "1M17:O00688")
    assert code == 3
    return out, json.loads(stdout)


# --- the command and its help ----------------------------------------------------------------


def test_the_command_is_registered_and_its_help_states_the_network_boundary(capsys) -> None:
    top = " ".join(build_parser().format_help().split())
    assert "acquire" in top
    assert "uses the network" in top
    with pytest.raises(SystemExit) as caught:
        main(["acquire", "--help"])
    assert caught.value.code == 0
    text = " ".join(capsys.readouterr().out.split())
    for expected in (
        "files.rcsb.org",
        "data.rcsb.org",
        "rest.uniprot.org",
        "the only rnp command whose Python code uses the network",
        "--verify contacts nothing",
        "PDB_ID:UNIPROT_ACCESSION",
        "--out",
        "--timeout",
        "--verify DIR",
        "acquisition_record.json",
    ):
        assert expected in text, expected


def test_the_defaults_are_the_real_fetcher_and_the_real_clock() -> None:
    assert rnp.cli.urllib_fetcher is rnp.acquire.urllib_fetcher
    assert rnp.cli.utc_now_iso is rnp.provenance.utc_now_iso


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--bogus"], "rnp: error: unrecognized arguments: --bogus"),
        (
            ["--timeout", "abc", "1M17:P00533"],
            "rnp acquire: error: argument --timeout: invalid float value: 'abc'",
        ),
        (["--out"], "rnp acquire: error: argument --out: expected one argument"),
        (["--verify"], "rnp acquire: error: argument --verify: expected one argument"),
    ],
)
def test_malformed_options_are_refused_by_the_parser(argv, message, capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["acquire", *argv])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert message in captured.err


# --- a complete run --------------------------------------------------------------------------


def test_a_complete_run_freezes_the_records_and_prints_the_summary(
    tmp_path, monkeypatch, capsys
) -> None:
    pairs = [("1M17", "P00533"), ("3POZ", "P00533")]
    fetcher = ok_fetcher(pairs)
    install(monkeypatch, fetcher)
    out = tmp_path / "frozen"
    code, stdout, stderr = run(capsys, "--out", out, "1M17:P00533", "3POZ:P00533")
    assert code == 0
    assert stderr == ""
    record_bytes = (out / RECORD).read_bytes()
    listing = hashlib.sha256(b"1M17:P00533\n3POZ:P00533").hexdigest()[:8]
    assert json.loads(stdout) == {
        "status": "complete",
        "acquisition_id": f"20261108T060000Z_{listing}",
        "out_dir": str(out.resolve()),
        "record": str((out / RECORD).resolve()),
        "record_sha256": sha(record_bytes),
        "items": [
            item("i1", "1M17", "P00533", "complete"),
            item("i2", "3POZ", "P00533", "complete"),
        ],
        "outcomes": {"ok": 7},
        "warnings": [],
    }
    assert stdout.isascii()
    assert stdout.endswith("}\n")
    assert sorted(tree(out)) == [
        "1M17/1M17.cif",
        "1M17/rcsb_entry.json",
        "1M17/rcsb_graphql.json",
        "3POZ/3POZ.cif",
        "3POZ/rcsb_entry.json",
        "3POZ/rcsb_graphql.json",
        RECORD,
        "uniprot/P00533.json",
    ]
    assert len(fetcher.calls) == 7
    assert {call.timeout for call in fetcher.calls} == {60.0}
    assert freeze.verify_acquisition(out) == []


def test_identifiers_are_case_insensitive_and_recorded_in_upper_case(
    tmp_path, monkeypatch, capsys
) -> None:
    fetcher = ok_fetcher([("1M17", "P00533")])
    install(monkeypatch, fetcher)
    code, stdout, _ = run(capsys, "--out", tmp_path / "out", " 1m17 : p00533 ")
    assert code == 0
    assert json.loads(stdout)["items"] == [item("i1", "1M17", "P00533", "complete")]
    assert fetcher.urls[0] == mmcif_url("1M17")
    record = json.loads((tmp_path / "out" / RECORD).read_text(encoding="utf-8"))
    assert record["items"][0]["pdb_id"] == "1M17"
    assert record["items"][0]["uniprot_accession"] == "P00533"


def test_items_may_come_before_the_options_and_keep_their_order(
    tmp_path, monkeypatch, capsys
) -> None:
    fetcher = ok_fetcher([("3POZ", "P00533"), ("1M17", "P00533")])
    install(monkeypatch, fetcher)
    code, stdout, _ = run(capsys, "3POZ:P00533", "1M17:P00533", "--out", tmp_path / "out")
    assert code == 0
    assert [entry["pdb_id"] for entry in json.loads(stdout)["items"]] == ["3POZ", "1M17"]
    assert fetcher.urls[0] == mmcif_url("3POZ")


def test_a_relative_output_path_is_resolved_and_its_parents_are_created(
    tmp_path, monkeypatch, capsys
) -> None:
    install(monkeypatch, ok_fetcher([("1M17", "P00533")]))
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run(capsys, "--out", "sub/dir", "1M17:P00533")
    assert code == 0
    expected = (tmp_path / "sub" / "dir").resolve()
    payload = json.loads(stdout)
    assert payload["out_dir"] == str(expected)
    assert payload["record"] == str(expected / RECORD)
    assert (expected / RECORD).is_file()


def test_an_existing_empty_output_directory_is_accepted(tmp_path, monkeypatch, capsys) -> None:
    install(monkeypatch, ok_fetcher([("1M17", "P00533")]))
    out = tmp_path / "empty"
    out.mkdir()
    code, _, stderr = run(capsys, "--out", out, "1M17:P00533")
    assert (code, stderr) == (0, "")
    assert (out / RECORD).is_file()


@pytest.mark.parametrize(
    ("given", "expected"), [("7.5", 7.5), ("5", 5.0), ("0.25", 0.25), ("1e3", 1000.0)]
)
def test_the_timeout_reaches_every_request(given, expected, tmp_path, monkeypatch, capsys) -> None:
    fetcher = ok_fetcher([("1M17", "P00533")])
    install(monkeypatch, fetcher)
    code, _, _ = run(capsys, "--out", tmp_path / "out", "--timeout", given, "1M17:P00533")
    assert code == 0
    assert len(fetcher.calls) == 4
    assert [call.timeout for call in fetcher.calls] == [expected] * 4
    assert all(isinstance(call.timeout, float) for call in fetcher.calls)


# --- runs that do not complete ---------------------------------------------------------------


def test_a_partial_run_writes_the_record_and_exits_3(partial) -> None:
    out, payload = partial
    record = json.loads((out / RECORD).read_text(encoding="utf-8"))
    assert record["status"] == "partial"
    assert payload == {
        "status": "partial",
        "acquisition_id": record["acquisition_id"],
        "out_dir": str(out.resolve()),
        "record": str((out / RECORD).resolve()),
        "record_sha256": sha((out / RECORD).read_bytes()),
        "items": [
            item("i1", "1M17", "P00533", "complete"),
            item("i2", "1M17", "O00688", "failed"),
        ],
        "outcomes": {"inactive_accession": 1, "ok": 4},
        "warnings": record["warnings"],
    }
    assert list(payload["outcomes"]) == ["inactive_accession", "ok"]
    assert len(payload["warnings"]) == 1
    assert "O00688" in payload["warnings"][0]
    assert "withdrawn" in payload["warnings"][0]
    assert sorted(tree(out)) == [
        "1M17/1M17.cif",
        "1M17/rcsb_entry.json",
        "1M17/rcsb_graphql.json",
        RECORD,
        "uniprot/P00533.json",
    ]


def test_a_run_where_nothing_arrives_is_failed_and_exits_3(tmp_path, monkeypatch, capsys) -> None:
    def down(request):
        raise NetworkError("connection refused")

    install(monkeypatch, down)
    out = tmp_path / "out"
    code, stdout, stderr = run(capsys, "--out", out, "1M17:P00533")
    assert (code, stderr) == (3, "")
    payload = json.loads(stdout)
    assert payload["status"] == "failed"
    assert payload["items"] == [item("i1", "1M17", "P00533", "failed")]
    assert payload["outcomes"] == {"network_error": 4}
    assert len(payload["warnings"]) == 4
    assert all(text.startswith("network error for https://") for text in payload["warnings"])
    assert sorted(tree(out)) == [RECORD]
    assert json.loads((out / RECORD).read_text(encoding="utf-8"))["status"] == "failed"


def test_the_summary_is_ascii_even_when_a_remote_message_is_not(
    tmp_path, monkeypatch, capsys
) -> None:
    extra = inactive("O00688", deletedReason=f"caf{E_ACUTE} removed")
    install(monkeypatch, ok_fetcher([("1M17", "P00533")], extra))
    code, stdout, stderr = run(capsys, "--out", tmp_path / "out", "1M17:O00688")
    assert (code, stderr) == (3, "")
    assert stdout.isascii()
    assert f"caf{E_ACUTE} removed" in json.loads(stdout)["warnings"][0]


# --- arguments that are refused --------------------------------------------------------------

REFUSED_ARGUMENTS = [
    pytest.param([], [NO_OUT, NO_ITEMS], id="nothing-at-all"),
    pytest.param(["--out", "OUT"], [NO_ITEMS], id="no-items"),
    pytest.param(["1M17:P00533"], [NO_OUT], id="no-out"),
    pytest.param(["--out", "", "1M17:P00533"], [NO_OUT], id="empty-out"),
    pytest.param(["--out", "OUT", "--timeout", "0", "1M17:P00533"], [BAD_TIMEOUT], id="zero"),
    pytest.param(["--out", "OUT", "--timeout", "-1", "1M17:P00533"], [BAD_TIMEOUT], id="negative"),
    pytest.param(["--out", "OUT", "--timeout=nan", "1M17:P00533"], [BAD_TIMEOUT], id="nan"),
    pytest.param(["--out", "OUT", "--timeout=inf", "1M17:P00533"], [BAD_TIMEOUT], id="inf"),
    pytest.param(["--out", "OUT", "--timeout=-inf", "1M17:P00533"], [BAD_TIMEOUT], id="-inf"),
    pytest.param(
        ["--out", "OUT", "1M17", "P00533:", ":P00533", "1M17:P00533:X", ""],
        [
            "item 1: '1M17' is not PDB_ID:UNIPROT_ACCESSION",
            "item 2: 'P00533:' is not PDB_ID:UNIPROT_ACCESSION",
            "item 3: ':P00533' is not PDB_ID:UNIPROT_ACCESSION",
            "item 4: '1M17:P00533:X' is not PDB_ID:UNIPROT_ACCESSION",
            "item 5: '' is not PDB_ID:UNIPROT_ACCESSION",
        ],
        id="item-syntax",
    ),
    pytest.param(
        ["--timeout=nan", "1M17"],
        [NO_OUT, BAD_TIMEOUT, "item 1: '1M17' is not PDB_ID:UNIPROT_ACCESSION"],
        id="every-kind-at-once",
    ),
]


@pytest.mark.parametrize(("argv", "details"), REFUSED_ARGUMENTS)
def test_invalid_arguments_are_refused_before_anything_happens(
    argv, details, tmp_path, monkeypatch, capsys
) -> None:
    fetcher = ok_fetcher([("1M17", "P00533")])
    clock = install(monkeypatch, fetcher)
    out = tmp_path / "out"
    code, stdout, stderr = run(capsys, *[str(out) if part == "OUT" else part for part in argv])
    assert code == 2
    assert stdout == ""
    assert stderr == f"error: {ARGS_HEADER}\n" + "".join(f"  - {text}\n" for text in details)
    assert fetcher.calls == []
    assert clock.calls == 0
    assert not out.exists()


LIBRARY_REFUSALS = [
    pytest.param(
        ["ABCDE:P00533"],
        [f"item 1: PDB ID 'ABCDE' must match {PDB_ID_REGEX}"],
        id="pdb-id",
    ),
    pytest.param(
        ["1M17:P00533-2"],
        [
            "item 1: UniProt accession 'P00533-2' must be a canonical accession without an "
            f"isoform suffix ({UNIPROT_ACCESSION_REGEX})"
        ],
        id="isoform",
    ),
    pytest.param(["1M17:P00533", "1m17:p00533"], ["item 2: duplicate of item 1"], id="duplicate"),
    pytest.param(
        [f"1{chr(223)}X:P00533"],
        [f"item 1: PDB ID '1{chr(223)}X' must match {PDB_ID_REGEX}"],
        id="sharp-s-is-not-mapped-to-SS",
    ),
    pytest.param(
        [f"1M17:Q9{chr(0x17F) * 3}9"],
        [
            f"item 1: UniProt accession 'Q9{chr(0x17F) * 3}9' must be a canonical accession "
            f"without an isoform suffix ({UNIPROT_ACCESSION_REGEX})"
        ],
        id="long-s-is-not-mapped-to-S",
    ),
    pytest.param(
        ["ABCDE:XYZ", "1M17:P00533"],
        [
            f"item 1: PDB ID 'ABCDE' must match {PDB_ID_REGEX}",
            "item 1: UniProt accession 'XYZ' must be a canonical accession without an "
            f"isoform suffix ({UNIPROT_ACCESSION_REGEX})",
        ],
        id="both-in-one-item",
    ),
]


@pytest.mark.parametrize(("items", "details"), LIBRARY_REFUSALS)
def test_identifiers_the_library_refuses_are_reported_in_one_error(
    items, details, tmp_path, monkeypatch, capsys
) -> None:
    fetcher = ok_fetcher([("1M17", "P00533")])
    clock = install(monkeypatch, fetcher)
    out = tmp_path / "out"
    code, stdout, stderr = run(capsys, "--out", out, *items)
    assert code == 2
    assert stdout == ""
    assert stderr == "error: invalid acquisition input\n" + "".join(
        f"  - {text}\n" for text in details
    )
    assert fetcher.calls == []
    assert clock.calls == 0
    assert not out.exists()


def test_a_non_empty_output_directory_is_refused_and_left_alone(
    tmp_path, monkeypatch, capsys
) -> None:
    fetcher = ok_fetcher([("1M17", "P00533")])
    install(monkeypatch, fetcher)
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("keep", encoding="utf-8")
    code, stdout, stderr = run(capsys, "--out", out, "1M17:P00533")
    assert code == 2
    assert stdout == ""
    assert stderr == f"error: output directory is not empty: {out.resolve()}\n"
    assert fetcher.calls == []
    assert tree(out) == {"keep.txt": b"keep"}


def test_an_output_path_that_is_a_file_is_refused(tmp_path, monkeypatch, capsys) -> None:
    fetcher = ok_fetcher([("1M17", "P00533")])
    install(monkeypatch, fetcher)
    out = tmp_path / "out"
    out.write_text("a file", encoding="utf-8")
    code, stdout, stderr = run(capsys, "--out", out, "1M17:P00533")
    assert code == 2
    assert stdout == ""
    assert stderr == f"error: output path exists and is not a directory: {out.resolve()}\n"
    assert fetcher.calls == []


def test_a_second_run_into_the_same_directory_is_refused(tmp_path, monkeypatch, capsys) -> None:
    fetcher = ok_fetcher([("1M17", "P00533")])
    install(monkeypatch, fetcher)
    out = tmp_path / "out"
    assert run(capsys, "--out", out, "1M17:P00533")[0] == 0
    before = tree(out)
    calls = len(fetcher.calls)
    code, _, stderr = run(capsys, "--out", out, "1M17:P00533")
    assert code == 2
    assert "output directory is not empty" in stderr
    assert len(fetcher.calls) == calls
    assert tree(out) == before


# --- internal errors -------------------------------------------------------------------------


def test_a_bug_in_the_fetcher_is_an_internal_error(tmp_path, monkeypatch, capsys) -> None:
    routes = ok_routes("1M17", "P00533")
    routes[("GET", entry_url("1M17"))] = RuntimeError("bug")
    install(monkeypatch, FakeFetcher(routes))
    out = tmp_path / "out"
    code, stdout, stderr = run(capsys, "--out", out, "1M17:P00533")
    assert code == 1
    assert stdout == ""
    assert stderr == "unexpected error: RuntimeError: bug\n"
    assert not (out / RECORD).exists()


def test_a_record_that_breaks_its_own_schema_is_an_internal_error(
    tmp_path, monkeypatch, capsys
) -> None:
    install(monkeypatch, ok_fetcher([("1M17", "P00533")]))
    monkeypatch.setattr(freeze, "package_version", lambda: "")
    out = tmp_path / "out"
    code, stdout, stderr = run(capsys, "--out", out, "1M17:P00533")
    assert code == 1
    assert stdout == ""
    assert stderr.startswith(
        "error: the acquisition record built by rnp does not satisfy its schema\n"
    )
    assert not (out / RECORD).exists()


# --- offline verification --------------------------------------------------------------------


def no_requests(monkeypatch):
    """Replace the fetcher by one that fails on any request; return it and the clock."""
    fetcher = FakeFetcher({})
    return fetcher, install(monkeypatch, fetcher)


def test_a_clean_directory_verifies_and_nothing_changes(frozen, monkeypatch, capsys) -> None:
    fetcher, clock = no_requests(monkeypatch)
    before = tree(frozen)
    code, stdout, stderr = run(capsys, "--verify", frozen)
    assert (code, stderr) == (0, "")
    assert json.loads(stdout) == {
        "status": "verified",
        "directory": str(frozen.resolve()),
        "record": str((frozen / RECORD).resolve()),
        "record_sha256": sha((frozen / RECORD).read_bytes()),
        "acquisition_status": "complete",
        "problems": [],
    }
    assert fetcher.calls == []
    assert clock.calls == 0
    assert tree(frozen) == before


def test_a_relative_directory_is_resolved_for_verification(frozen, monkeypatch, capsys) -> None:
    no_requests(monkeypatch)
    monkeypatch.chdir(frozen.parent)
    code, stdout, _ = run(capsys, "--verify", frozen.name)
    assert code == 0
    payload = json.loads(stdout)
    assert payload["directory"] == str(frozen.resolve())
    assert payload["record"] == str((frozen / RECORD).resolve())


def test_a_partial_acquisition_verifies_and_says_it_is_partial(
    partial, monkeypatch, capsys
) -> None:
    out, _ = partial
    no_requests(monkeypatch)
    code, stdout, stderr = run(capsys, "--verify", out)
    assert (code, stderr) == (0, "")
    payload = json.loads(stdout)
    assert payload["status"] == "verified"
    assert payload["acquisition_status"] == "partial"
    assert payload["problems"] == []


def test_a_changed_file_is_reported_and_exits_3(frozen, monkeypatch, capsys) -> None:
    no_requests(monkeypatch)
    target = frozen / "1M17" / "1M17.cif"
    data = bytearray(target.read_bytes())
    data[-2] ^= 0x01
    target.write_bytes(bytes(data))
    code, stdout, stderr = run(capsys, "--verify", frozen)
    assert (code, stderr) == (3, "")
    payload = json.loads(stdout)
    assert payload["status"] == "problems"
    assert payload["directory"] == str(frozen.resolve())
    assert payload["record_sha256"] == sha((frozen / RECORD).read_bytes())
    assert payload["acquisition_status"] == "complete"
    assert payload["problems"] == freeze.verify_acquisition(frozen)
    assert len(payload["problems"]) == 1
    assert "sha256 of 1M17/1M17.cif" in payload["problems"][0]


def test_a_missing_file_is_reported_and_exits_3(frozen, monkeypatch, capsys) -> None:
    no_requests(monkeypatch)
    (frozen / "uniprot" / "P00533.json").unlink()
    code, stdout, _ = run(capsys, "--verify", frozen)
    assert code == 3
    payload = json.loads(stdout)
    assert payload["status"] == "problems"
    assert payload["problems"] == freeze.verify_acquisition(frozen)
    assert any("uniprot/P00533.json is missing" in text for text in payload["problems"])


@pytest.mark.parametrize(
    ("content", "status"),
    [("{", None), ("[]", None), ('{"status": 42}', None), ('{"status": "partial"}', "partial")],
)
def test_an_unusable_record_is_reported_and_exits_3(
    content, status, frozen, monkeypatch, capsys
) -> None:
    no_requests(monkeypatch)
    (frozen / RECORD).write_text(content, encoding="utf-8")
    code, stdout, stderr = run(capsys, "--verify", frozen)
    assert (code, stderr) == (3, "")
    payload = json.loads(stdout)
    assert payload["status"] == "problems"
    assert payload["acquisition_status"] == status
    assert payload["record_sha256"] == sha(content.encode("utf-8"))
    assert payload["problems"] == freeze.verify_acquisition(frozen)
    assert payload["problems"]


def test_the_verification_summary_is_ascii_even_when_a_file_name_is_not(
    frozen, monkeypatch, capsys
) -> None:
    no_requests(monkeypatch)
    (frozen / f"caf{E_ACUTE}.txt").write_text("stray", encoding="utf-8")
    code, stdout, _ = run(capsys, "--verify", frozen)
    assert code == 3
    assert stdout.isascii()
    assert json.loads(stdout)["problems"] == [
        f"caf{E_ACUTE}.txt: unexpected file not listed in the record"
    ]


def test_a_directory_without_a_record_is_not_an_acquisition(tmp_path, monkeypatch, capsys) -> None:
    fetcher, _ = no_requests(monkeypatch)
    code, stdout, stderr = run(capsys, "--verify", tmp_path)
    assert code == 2
    assert stdout == ""
    assert stderr == (
        f"error: not an acquisition directory (missing {RECORD}): {tmp_path.resolve()}\n"
        "  - a directory without the record is an interrupted run and cannot be used\n"
    )
    assert fetcher.calls == []


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_a_path_that_is_not_a_directory_is_refused(kind, tmp_path, monkeypatch, capsys) -> None:
    no_requests(monkeypatch)
    target = tmp_path / "nothing"
    if kind == "file":
        target.write_text("not a directory", encoding="utf-8")
    code, stdout, stderr = run(capsys, "--verify", target)
    assert code == 2
    assert stdout == ""
    assert stderr == f"error: not a directory: {target.resolve()}\n"


@pytest.mark.parametrize(
    "extra",
    [["--out", "OUT"], ["--timeout", "5"], ["1M17:P00533"], ["--out", "OUT", "1M17:P00533"]],
)
def test_verify_cannot_be_combined_with_anything_else(
    extra, frozen, tmp_path, monkeypatch, capsys
) -> None:
    fetcher, _ = no_requests(monkeypatch)
    before = tree(frozen)
    out = tmp_path / "other"
    code, stdout, stderr = run(
        capsys, "--verify", frozen, *[str(out) if part == "OUT" else part for part in extra]
    )
    assert code == 2
    assert stdout == ""
    assert stderr == f"error: {CONFLICT}\n"
    assert fetcher.calls == []
    assert not out.exists()
    assert tree(frozen) == before
