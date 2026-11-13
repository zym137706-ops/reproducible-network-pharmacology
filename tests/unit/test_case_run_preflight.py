"""The structure layer of the case preflight, with the real `rnp ingest compounds`.

With a submission log, `verify_inputs` checks the files first (the case policy of the file layer),
then runs `rnp ingest compounds` on a copy of the inputs in a temporary directory and applies the
case policy to what the command wrote. These tests run the real command, so they need RDKit
(optional extra `chem`): without it they are skipped, unless RNP_REQUIRE_CHEM is 1 (CI sets it),
in which case a missing RDKit is a failure.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml
from case_run_support import (
    ROOT,
    argv_for,
    case_args,
    load_run,
    read_tsv,
    require_chem,
    rewrite,
    sha256_of,
    write_log,
    write_tsv,
)

from rnp.config import load_config


@pytest.fixture
def chem():
    require_chem()


def verify(tmp_path: Path, edit=None, **overrides):
    """Build the quickstart case with structures, let `edit(args)` break it, run verify_inputs."""
    run = load_run()
    args = case_args(tmp_path, **overrides)
    if edit is not None:
        edit(args)
    return run, args, run.verify_inputs(args)


def rejected(tmp_path: Path, edit, **overrides) -> str:
    run = load_run()
    args = case_args(tmp_path, **overrides)
    edit(args)
    with pytest.raises(ValueError) as caught:
        run.verify_inputs(args)
    return str(caught.value)


# --- accepted --------------------
def test_a_consistent_case_is_accepted_and_the_structures_are_recorded(tmp_path, chem) -> None:
    import rdkit

    _, args, inputs = verify(tmp_path)
    assert inputs["log"]["provided"] is True
    assert inputs["log"]["verified_by"] == "rnp ingest compounds"
    assert inputs["log"]["policy"] == "case-log-policy-v2"
    assert inputs["log"]["bindings_verified"] is True
    assert inputs["log"]["structures_verified"] is True
    assert inputs["log"]["rows"] == 2
    assert inputs["log"]["path"] == str(args.log.resolve())
    assert inputs["log"]["sha256"] == sha256_of(args.log)
    assert "date-only" in inputs["log"]["time_precision"]
    assert inputs["structures"] == {
        "mode": "structure",
        "toolkit": {"name": "rdkit", "version": rdkit.rdBase.rdkitVersion},
        "rows": 2,
        "submission_status_counts": {"verified_kind_unstated": 2},
        "issue_code_counts": {},
    }


def test_the_recorded_warnings_do_not_stop_the_case(tmp_path, chem) -> None:
    # alanine without its stereo centre specified (stereo_undefined), twice (shared_structure)
    _, args, inputs = verify(tmp_path, smiles=("CC(N)C(=O)O", "CC(N)C(=O)O"))
    assert inputs["structures"]["issue_code_counts"] == {
        "shared_structure": 2,
        "stereo_undefined": 2,
    }
    assert inputs["structures"]["submission_status_counts"] == {"verified_kind_unstated": 2}


def test_export_kinds_decide_the_submission_status(tmp_path, chem) -> None:
    def kinds(args) -> None:
        write_log(
            args,
            export_kind=["native_export", "reconstructed_from_result_page"],
            job_id=["not_saved", "job-1"],
            result_rows=["", "12"],
        )

    _, _, inputs = verify(tmp_path, kinds)
    assert inputs["structures"]["submission_status_counts"] == {"reconstructed": 1, "verified": 1}
    assert inputs["structures"]["issue_code_counts"] == {"submission_export_reconstructed": 1}


def test_a_byte_order_mark_crlf_and_row_order_change_nothing(tmp_path, chem) -> None:
    def reshape(args) -> None:
        for path in (args.compounds, args.log):
            header, rows = read_tsv(path)
            if path == args.log:
                rows.reverse()
            write_tsv(path, header, rows, bom=True, newline="\r\n")

    _, _, inputs = verify(tmp_path, reshape)
    assert inputs["structures"]["submission_status_counts"] == {"verified_kind_unstated": 2}


def test_spaces_around_cells_are_tolerated_as_before(tmp_path, chem) -> None:
    def pad(args) -> None:
        def edit(header, rows) -> None:
            rows[0]["species"] = " Homo sapiens "
            rows[0]["result_sha256"] = " " + rows[0]["result_sha256"] + " "
            rows[0]["submitted_structure"] = " " + rows[0]["submitted_structure"] + " "

        rewrite(args.log, edit)

    _, _, inputs = verify(tmp_path, pad)
    assert inputs["structures"]["rows"] == 2


def test_without_a_log_nothing_is_run_and_the_record_is_the_old_one(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))
    run = load_run()
    args = case_args(tmp_path, log=False)
    inputs = run.verify_inputs(args)
    assert calls == []
    assert inputs["log"] == {"provided": False}
    assert "structures" not in inputs
    assert set(inputs) == {
        "compounds",
        "compounds_sha256",
        "compound_rows",
        "stp_dir",
        "stp_files",
        "disease_genes",
        "disease_sha256",
        "disease_rows",
        "hgnc_map",
        "hgnc_sha256",
        "log",
    }


# --- rejected: the words of the message name the field --------------------
def set_log(column: str, value: str, row: int = 0):
    def edit(args) -> None:
        def change(header, rows) -> None:
            rows[row][column] = value

        rewrite(args.log, change)

    return edit


def set_compound(column: str, value: str, row: int = 0):
    def edit(args) -> None:
        def change(header, rows) -> None:
            rows[row][column] = value

        rewrite(args.compounds, change)

    return edit


def drop_log_column(column: str):
    def edit(args) -> None:
        def change(header, rows) -> None:
            header.remove(column)
            for row in rows:
                del row[column]

        rewrite(args.log, change)

    return edit


def both(*edits):
    def edit(args) -> None:
        for each in edits:
            each(args)

    return edit


def break_export(args) -> None:
    (args.stp_dir / "compound_a.csv").write_bytes(b"changed after the submission\n")


def add_unbound_export(args) -> None:
    (args.stp_dir / "unbound.csv").write_bytes((args.stp_dir / "compound_a.csv").read_bytes())


def remove_an_export(args) -> None:
    (args.stp_dir / "compound_b.csv").unlink()


FAILURES = {
    # id: (edit, words that the message must contain)
    "wrong submitted structure": (set_log("submitted_structure", "C"), ["submitted_structure"]),
    "wrong result hash": (set_log("result_sha256", "0" * 64), ["result_sha256"]),
    "an export changed after the log": (break_export, ["result_sha256"]),
    "hash not declared": (set_log("result_sha256", ""), ["result_sha256"]),
    "species of another organism": (set_log("species", "Mus musculus"), ["species"]),
    "species written with an underscore": (set_log("species", "Homo_sapiens"), ["species"]),
    "wrong pubchem_cid": (set_log("pubchem_cid", "999"), ["pubchem_cid"]),
    "wrong compound name": (set_log("compound", "Somebody else"), ["compound"]),
    "smiles that is no structure": (
        both(set_compound("smiles", "C(C"), set_log("submitted_structure", "C(C")),
        ["smiles"],
    ),
    "smiles with a space inside": (
        both(set_compound("smiles", "CC O"), set_log("submitted_structure", "CC O")),
        ["submitted_structure"],
    ),
    "log without submitted_date": (drop_log_column("submitted_date"), ["submitted_date"]),
}


@pytest.mark.parametrize("name", sorted(FAILURES))
def test_a_broken_case_is_rejected_by_the_core_with_the_field_in_the_message(
    tmp_path, monkeypatch, chem, name
) -> None:
    edit, words = FAILURES[name]
    calls = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or real(*a, **k))
    message = rejected(tmp_path, edit)
    assert len(calls) == 1, "the file layer must let this through: the command is the judge"
    for word in words:
        assert word in message, message


def test_the_message_names_the_compound_and_the_file(tmp_path, chem) -> None:
    run = load_run()
    args = case_args(tmp_path)
    set_log("submitted_structure", "C", row=1)(args)
    with pytest.raises(ValueError) as caught:
        run.verify_inputs(args)
    message = str(caught.value)
    assert "Kaempferol" in message
    assert "Quercetin" not in message
    assert str(args.log) in message
    assert "submission_structure_mismatch" in message


def test_all_the_problems_are_reported_in_one_go(tmp_path, chem) -> None:
    message = rejected(
        tmp_path,
        both(
            set_log("submitted_structure", "C", row=0),
            set_log("result_sha256", "0" * 64, row=1),
        ),
    )
    assert "submitted_structure" in message
    assert "result_sha256" in message
    assert "Quercetin" in message
    assert "Kaempferol" in message


# --- rejected by the file layer, before the command is run --------------------
FILE_LAYER = {
    "an export nobody binds": (add_unbound_export, ["unbound.csv"]),
    "a bound export is missing": (remove_an_export, ["compound_b.csv"]),
    "empty pubchem_cid in the log": (set_log("pubchem_cid", ""), ["pubchem_cid"]),
    "empty pubchem_cid in the compounds": (set_compound("pubchem_cid", ""), ["pubchem_cid"]),
    "log without pubchem_cid": (drop_log_column("pubchem_cid"), ["missing columns", "pubchem_cid"]),
    "log without result_sha256": (
        drop_log_column("result_sha256"),
        ["missing columns", "result_sha256"],
    ),
    "empty smiles": (set_compound("smiles", ""), ["empty smiles"]),
    "submission_id of another compound": (
        both(
            lambda args: rewrite(
                args.compounds, lambda h, rows: _add(h, rows, "submission_id", "S-1")
            ),
            lambda args: write_log(args, submission_id=["S-1", "S-2"]),
        ),
        ["submission_id"],
    ),
}


def _add(header: list[str], rows: list[dict[str, str]], column: str, value: str) -> None:
    header.append(column)
    for row in rows:
        row[column] = value


@pytest.mark.parametrize("name", sorted(FILE_LAYER))
def test_the_file_layer_rejects_before_any_command_is_run(tmp_path, monkeypatch, name) -> None:
    edit, words = FILE_LAYER[name]
    calls = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or real(*a, **k))
    message = rejected(tmp_path, edit)
    for word in words:
        assert word in message, message
    assert calls == []


def test_a_missing_or_surplus_or_repeated_log_row_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("the command was run"))

    def drop(args) -> None:
        rewrite(args.log, lambda header, rows: rows.pop())

    def extra(args) -> None:
        rewrite(args.log, lambda header, rows: rows.append({**rows[0], "stp_file": "other.csv"}))

    def repeat(args) -> None:
        rewrite(args.log, lambda header, rows: rows.append(dict(rows[0])))

    assert "has 1 rows, expected 2" in rejected(tmp_path / "a", drop)
    assert "has 3 rows, expected 2" in rejected(tmp_path / "b", extra)
    assert "duplicate stp_file" in rejected(tmp_path / "c", repeat)


def test_a_log_row_for_an_export_that_no_compound_binds_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("the command was run"))
    message = rejected(tmp_path, set_log("stp_file", "other.csv", row=0))
    assert "binding mismatch" in message
    assert "other.csv" in message


# --- how the command is run --------------------
def test_the_command_runs_on_a_copy_in_a_temporary_directory_that_is_removed(
    tmp_path, monkeypatch, chem
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    real = subprocess.run
    seen = []

    def spy(command, *args, **kwargs):
        config_path = Path(command[command.index("--config") + 1])
        seen.append(
            {
                "command": list(command),
                "config": yaml.safe_load(config_path.read_text(encoding="utf-8")),
                "config_path": config_path,
                "cwd": kwargs.get("cwd"),
                "env": kwargs.get("env") or {},
                "encoding": kwargs.get("encoding"),
                "errors": kwargs.get("errors"),
            }
        )
        return real(command, *args, **kwargs)

    run = load_run()
    args = case_args(tmp_path / "case")
    monkeypatch.setattr(subprocess, "run", spy)
    run.verify_inputs(args)
    monkeypatch.undo()

    assert len(seen) == 1
    command = seen[0]["command"]
    assert command[0] == sys.executable
    assert command[1:5] == ["-m", "rnp.cli", "ingest", "compounds"]
    assert command[command.index("--run-id") + 1] == "run"
    assert "--force" not in command
    assert Path(seen[0]["cwd"]) == ROOT
    assert seen[0]["env"].get("PYTHONUTF8") == "1"
    assert seen[0]["encoding"] == "utf-8"
    assert seen[0]["errors"] == "replace"
    assert seen[0]["config_path"].name == "run-0.05.yaml"  # the smallest threshold
    assert scratch in seen[0]["config_path"].parents
    config = seen[0]["config"]
    assert scratch in Path(config["outputs"]["dir"]).parents
    # the very inputs that the chain will use, plus the log
    expected = load_config(run.write_configs(args, tmp_path / "reference")["0.05"]).data
    assert config["inputs"] == expected["inputs"]
    assert config["inputs"]["submission_log"] == str(args.log.resolve())
    assert config["species"] == expected["species"]
    assert list(scratch.iterdir()) == []
    assert not (tmp_path / "case" / "results").exists()


def test_the_temporary_directory_is_removed_when_the_case_is_rejected(
    tmp_path, monkeypatch, chem
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    run = load_run()
    args = case_args(tmp_path / "case")
    set_log("submitted_structure", "C")(args)
    with pytest.raises(ValueError):
        run.verify_inputs(args)
    assert list(scratch.iterdir()) == []


def test_a_missing_toolkit_is_reported_with_the_installation_hint(tmp_path, monkeypatch) -> None:
    run = load_run()
    args = case_args(tmp_path)

    class Finished:
        returncode = 2
        stdout = ""
        stderr = (
            "error: RDKit is not installed, so a new structure cannot be registered\n"
            "  - install the optional extra with: uv sync --extra chem\n"
        )

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Finished())
    with pytest.raises(ValueError) as caught:
        run.verify_inputs(args)
    assert "RDKit is not installed" in str(caught.value)
    assert "uv sync --extra chem" in str(caught.value)


# --- the command line --------------------
def run_script(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "case_run.py"), *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_the_script_rejects_a_wrong_structure_and_creates_nothing(tmp_path, chem) -> None:
    args = case_args(tmp_path / "case")
    set_log("submitted_structure", "C")(args)
    out = tmp_path / "out"
    result = run_script(*argv_for(args, out, preflight_only=True))
    assert result.returncode != 0, result.stdout
    assert "submitted_structure" in result.stderr
    assert not out.exists()


def test_the_script_rejects_a_file_layer_problem_and_creates_nothing(tmp_path) -> None:
    args = case_args(tmp_path / "case")
    set_log("pubchem_cid", "", row=1)(args)
    out = tmp_path / "out"
    result = run_script(*argv_for(args, out, preflight_only=True))
    assert result.returncode != 0
    assert "pubchem_cid" in result.stderr
    assert not out.exists()


def test_a_preflight_only_run_leaves_configs_and_provenance_and_no_stage(tmp_path, chem) -> None:
    import json

    args = case_args(tmp_path / "case")
    out = tmp_path / "out"
    result = run_script(*argv_for(args, out, preflight_only=True))
    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in out.iterdir()) == ["case_provenance.json", "configs"]
    provenance = json.loads((out / "case_provenance.json").read_text(encoding="utf-8"))
    assert provenance["status"] == "preflight_only"
    assert provenance["inputs"]["structures"]["mode"] == "structure"
    assert "compounds_stage" not in provenance["inputs"]
    assert provenance["inputs"]["log"]["policy"] == "case-log-policy-v2"
    for config in (out / "configs").glob("run-*.yaml"):
        assert load_config(config).data["inputs"]["submission_log"] == str(args.log.resolve())
    shown = json.loads(result.stdout)
    assert shown["inputs"]["structures"] == provenance["inputs"]["structures"]
    _, rows = read_tsv(args.compounds)
    assert len(rows) == provenance["inputs"]["structures"]["rows"]
