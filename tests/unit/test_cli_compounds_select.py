"""`rnp compounds select`: exit codes, the printed summary, --force, `rnp manifest`, `rnp validate`.

The last test runs the real commands (`rnp ingest compounds` and `rnp compounds select`) with real
molecules; it needs RDKit (optional extra `chem`): without it the test is skipped, unless the
environment variable RNP_REQUIRE_CHEM is 1 (CI sets it), in which case a missing RDKit is a failure.
"""

from __future__ import annotations

import json
import os

import pytest
from compounds_support import NAME_COLUMNS, compound_row, write_config, write_exports
from selection_support import (
    ALL_FOUR,
    EVERYTHING_DECIDED,
    build,
    decision,
    decisions_path,
    read_json,
    read_tsv,
    setup,
    write_decisions,
)
from structures_support import log_row

from rnp.cli import main


@pytest.fixture
def chem():
    try:
        import rdkit  # noqa: F401
    except ImportError:
        if os.environ.get("RNP_REQUIRE_CHEM") == "1":
            pytest.fail("RDKit is required (RNP_REQUIRE_CHEM=1) but is not installed")
        pytest.skip("RDKit is not installed (optional extra 'chem')")


def invoke(config, compounds, *extra, run_id="sel"):
    return main(
        [
            "compounds",
            "select",
            "--config",
            str(config),
            "--compounds",
            str(compounds),
            "--run-id",
            run_id,
            *extra,
        ]
    )


def no_selection_dir(tmp_path):
    return not any(path.name.endswith("_selection") for path in (tmp_path / "results").iterdir())


# --- exit codes and the printed summary ------------------------------------------------------
def test_a_selection_with_unresolved_candidates_exits_3_and_prints_its_summary(tmp_path, capsys):
    config, compounds = setup(tmp_path, ALL_FOUR)
    assert invoke(config, compounds) == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "partial"
    assert printed["stage_status"] == "partial"
    assert printed["identity_mode"] == "structure"
    assert printed["run_id"] == "sel_selection"
    assert printed["run_dir"] == str(tmp_path / "results" / "sel_selection")
    assert (printed["summary"]["candidates"], printed["summary"]["selected"]) == (4, 1)
    assert [item["compound_id"] for item in printed["unresolved"]] == ["CMP0002", "CMP0004"]
    run_dir = tmp_path / "results" / "sel_selection"
    manifest = read_json(run_dir / "run_manifest.json")
    assert (manifest["stage_status"], manifest["exit_code"]) == ("partial", 3)
    assert len(read_tsv(run_dir / "selection_decisions.tsv")) == 4


def test_a_selection_in_which_everything_is_decided_exits_0(tmp_path, capsys):
    config, compounds = setup(tmp_path, EVERYTHING_DECIDED)
    assert invoke(config, compounds) == 0
    printed = json.loads(capsys.readouterr().out)
    assert (printed["status"], printed["unresolved"]) == ("ok", [])


def test_the_real_commands_chain_in_name_only_mode(tmp_path, capsys):
    rows = [
        decision("Compound 1", "include"),
        decision("Compound 2", "exclude", reason="not_wanted"),
    ]
    write_decisions(decisions_path(tmp_path), rows)
    write_exports(tmp_path, numbers=range(1, 3))
    config = write_config(
        tmp_path,
        [compound_row(1), compound_row(2)],
        columns=NAME_COLUMNS,
        inputs={"selection": str(decisions_path(tmp_path))},
    )
    assert main(["ingest", "compounds", "--config", str(config), "--run-id", "c"]) == 0
    capsys.readouterr()
    stage_dir = tmp_path / "results" / "c_compounds"
    assert invoke(config, stage_dir) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["identity_mode"] == "name_only"
    assert printed["summary"]["selected"] == 1 and printed["summary"]["excluded"] == 1


# --- exit code 2: nothing is written -------------------------------------------------------------
def test_a_missing_config_exits_2(tmp_path, capsys):
    assert invoke(tmp_path / "nowhere.yaml", tmp_path) == 2
    assert "config not found" in capsys.readouterr().err


def test_without_inputs_selection_it_exits_2_and_writes_nothing(tmp_path, capsys):
    config, compounds = setup(tmp_path, None)
    assert invoke(config, compounds) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "inputs.selection is not set" in captured.err
    assert no_selection_dir(tmp_path)


def test_an_invalid_decision_table_exits_2_and_writes_nothing(tmp_path, capsys):
    config, compounds = setup(tmp_path, [decision("Compound 1", "include", reviewer="")])
    assert invoke(config, compounds) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "the selection table has invalid rows" in captured.err
    assert "row 1: reviewer" in captured.err
    assert no_selection_dir(tmp_path)


def test_a_stale_compounds_stage_exits_2_and_writes_nothing(tmp_path, capsys):
    config, compounds = setup(tmp_path, ALL_FOUR)
    with (tmp_path / "inputs" / "compounds.tsv").open("a", encoding="utf-8") as handle:
        handle.write("Another\tall\tother.csv\tCCO\t\n")
    assert invoke(config, compounds) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "the compound table changed since the compounds stage" in captured.err
    assert no_selection_dir(tmp_path)


def test_a_missing_stage_directory_exits_2(tmp_path, capsys):
    config, _ = setup(tmp_path, ALL_FOUR)
    assert invoke(config, tmp_path / "nowhere") == 2
    assert "compounds stage directory not found" in capsys.readouterr().err


def test_an_existing_run_directory_needs_force(tmp_path, capsys):
    config, compounds = setup(tmp_path, EVERYTHING_DECIDED)
    assert invoke(config, compounds) == 0
    capsys.readouterr()
    assert invoke(config, compounds) == 2
    assert "already exists" in capsys.readouterr().err
    assert invoke(config, compounds, "--force") == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    manifest = read_json(tmp_path / "results" / "sel_selection" / "run_manifest.json")
    assert manifest["overwritten"] is True


# --- the parser ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("args", "missing"),
    [(["--compounds", "x"], "--config"), (["--config", "x"], "--compounds")],
)
def test_the_two_options_are_required(capsys, args, missing):
    with pytest.raises(SystemExit) as caught:
        main(["compounds", "select", *args])
    assert caught.value.code == 2
    assert missing in capsys.readouterr().err


def test_the_help_of_the_command_names_its_options_and_hides_the_run_id(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["compounds", "select", "--help"])
    assert caught.value.code == 0
    text = capsys.readouterr().out
    assert "--config" in text and "--compounds" in text and "--force" in text
    assert "--run-id" not in text


def test_the_groups_list_their_commands(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["compounds", "--help"])
    assert caught.value.code == 0
    assert "select" in capsys.readouterr().out
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    assert "compounds" in capsys.readouterr().out
    with pytest.raises(SystemExit) as caught:
        main(["compounds"])
    assert caught.value.code == 2


def test_the_older_commands_still_dispatch(tmp_path, capsys):
    config = write_config(tmp_path, [compound_row(1)], columns=NAME_COLUMNS)
    write_exports(tmp_path, numbers=range(1, 2))
    assert main(["ingest", "compounds", "--config", str(config), "--run-id", "x"]) == 0
    assert main(["validate", "--config", str(config)]) == 0


# --- the manifest belongs to the family ---------------------------------------------------------
def test_rnp_manifest_reads_and_checks_the_manifest_of_the_stage(tmp_path, capsys):
    config, compounds = setup(tmp_path, EVERYTHING_DECIDED)
    assert invoke(config, compounds) == 0
    capsys.readouterr()
    run_dir = tmp_path / "results" / "sel_selection"
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok"
    assert printed["command"] == "compounds select"
    assert printed["run_id"] == "sel_selection"
    assert printed["inputs_checked"] == 4 and printed["drift"] == []


def test_rnp_manifest_notices_that_a_decision_changed(tmp_path, capsys):
    config, compounds = setup(tmp_path, EVERYTHING_DECIDED)
    assert invoke(config, compounds) == 0
    capsys.readouterr()
    write_decisions(decisions_path(tmp_path), ALL_FOUR)
    run_dir = tmp_path / "results" / "sel_selection"
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "drift"
    assert [os.path.basename(item["path"]) for item in printed["drift"]] == ["decisions.tsv"]


# --- rnp validate -------------------------------------------------------------------------------
def test_validate_reports_an_existing_decision_table(tmp_path, capsys):
    config = build(tmp_path, EVERYTHING_DECIDED)
    assert main(["validate", "--config", str(config)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["selection"] == str(decisions_path(tmp_path))


def test_validate_without_a_decision_table_is_as_before(tmp_path, capsys):
    config = build(tmp_path, None)
    assert main(["validate", "--config", str(config)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and "selection" not in payload


def test_validate_refuses_a_missing_decision_table(tmp_path, capsys):
    config = build(tmp_path, EVERYTHING_DECIDED)
    decisions_path(tmp_path).unlink()
    assert main(["validate", "--config", str(config)]) == 2
    error = capsys.readouterr().err
    assert "inputs.selection" in error and "not a file" in error


# --- real molecules ----------------------------------------------------------------------------
def test_the_real_commands_chain_with_real_molecules(tmp_path, capsys, chem):
    molecules = ["CCO", "c1ccccc1", "C[C@H](N)C(=O)O"]
    digests = write_exports(tmp_path)
    rows = [compound_row(number, smiles) for number, smiles in enumerate(molecules, start=1)]
    log = [
        log_row(number, digests[number], submitted_structure=smiles)
        for number, smiles in enumerate(molecules, start=1)
    ]
    write_decisions(
        decisions_path(tmp_path),
        [
            decision("Compound 1", "include"),
            decision("Compound 2", "exclude", reason="not_in_scope"),
            decision("Compound 3", "needs_review", reason="check_stereo"),
        ],
    )
    config = write_config(
        tmp_path, rows, log_rows=log, inputs={"selection": str(decisions_path(tmp_path))}
    )
    assert main(["ingest", "compounds", "--config", str(config), "--run-id", "c"]) == 0
    capsys.readouterr()
    assert invoke(config, tmp_path / "results" / "c_compounds") == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["identity_mode"] == "structure"
    table = read_tsv(tmp_path / "results" / "sel_selection" / "selection_decisions.tsv")
    assert [row["structure_id"] for row in table] == ["STR0001", "STR0002", "STR0003"]
    assert [row["selection_status"] for row in table] == ["selected", "excluded", "needs_review"]
    assert [row["compound_row_status"] for row in table] == ["accepted"] * 3
