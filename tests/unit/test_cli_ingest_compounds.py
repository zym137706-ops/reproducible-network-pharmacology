"""`rnp ingest compounds`: exit codes, the printed summary, --force, and a run with real RDKit.

The tests with real molecules need RDKit (optional extra `chem`): without it they are skipped,
unless the environment variable RNP_REQUIRE_CHEM is 1 (CI sets it), in which case a missing RDKit
is a failure.
"""

from __future__ import annotations

import json
import os
import sys

import pytest
from compounds_support import (
    NAME_COLUMNS,
    compound_row,
    read_json,
    write_config,
    write_exports,
)
from structures_support import log_row

from rnp.cli import main
from rnp.io.tables import read_table
from rnp.structures import read_registry

# smiles, InChIKey, stereo status, formula
MOLECULES = [
    ("CCO", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "none_present", "C2H6O"),
    ("c1ccccc1", "UHOVQNZJYSORNB-UHFFFAOYSA-N", "none_present", "C6H6"),
    ("C[C@H](N)C(=O)O", "QNAYBMKLOCPYGJ-REOHCLBHSA-N", "defined", "C3H7NO2"),
]


@pytest.fixture
def chem():
    try:
        import rdkit  # noqa: F401
    except ImportError:
        if os.environ.get("RNP_REQUIRE_CHEM") == "1":
            pytest.fail("RDKit is required (RNP_REQUIRE_CHEM=1) but is not installed")
        pytest.skip("RDKit is not installed (optional extra 'chem')")


def invoke(config, *extra, run_id="r1"):
    return main(["ingest", "compounds", "--config", str(config), "--run-id", run_id, *extra])


def real_setup(tmp_path, extra_rows=()):
    digests = write_exports(tmp_path)
    rows = [compound_row(number, smiles) for number, (smiles, *_) in enumerate(MOLECULES, start=1)]
    log = [
        log_row(number, digests[number], submitted_structure=smiles)
        for number, (smiles, *_) in enumerate(MOLECULES, start=1)
    ]
    return write_config(tmp_path, [*rows, *extra_rows], log_rows=log), digests


# --- real molecules -------------------------------------------------------------------------------
def test_a_run_with_real_molecules(tmp_path, capsys, chem):
    import rdkit

    config, digests = real_setup(tmp_path)
    assert invoke(config) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok"
    assert printed["stage_status"] == "complete"
    assert printed["identity_mode"] == "structure"
    assert printed["run_id"] == "r1_compounds"
    assert printed["quarantine"] == []
    assert printed["summary"]["rows"] == 3
    assert printed["summary"]["rows_accepted"] == 3
    assert printed["summary"]["structures_new"] == 3
    assert printed["summary"]["submissions_verified"] == 3
    assert (printed["summary"]["errors"], printed["summary"]["warnings"]) == (0, 0)

    run_dir = tmp_path / "results" / "r1_compounds"
    table = read_table(run_dir / "compound_structures.tsv")
    assert [row["structure_id"] for row in table] == ["STR0001", "STR0002", "STR0003"]
    assert [row["inchikey"] for row in table] == [key for _, key, _, _ in MOLECULES]
    assert [row["stereo_status"] for row in table] == [status for _, _, status, _ in MOLECULES]
    assert [row["submission_status"] for row in table] == ["verified"] * 3
    assert [row["export_sha256"] for row in table] == [digests[1], digests[2], digests[3]]

    registry = read_registry(tmp_path / "results" / "registry" / "structure_registry.tsv")
    assert [row["formula"] for row in registry] == [formula for _, _, _, formula in MOLECULES]
    assert {row["toolkit_version"] for row in registry} == {rdkit.rdBase.rdkitVersion}
    audit = read_json(run_dir / "compounds_audit.json")
    assert audit["toolkit"] == {"name": "rdkit", "version": rdkit.rdBase.rdkitVersion}


def test_a_second_run_with_real_molecules_reuses_them(tmp_path, capsys, chem):
    config, _ = real_setup(tmp_path)
    assert invoke(config) == 0
    capsys.readouterr()
    assert invoke(config, run_id="r2") == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["summary"]["structures_new"] == 0
    assert printed["summary"]["structures_reused"] == 3


def test_a_string_that_is_not_a_structure_makes_the_run_partial(tmp_path, capsys, chem):
    config, _ = real_setup(tmp_path, extra_rows=[compound_row(4, "C1CC")])
    assert invoke(config) == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "partial"
    assert printed["stage_status"] == "partial"
    assert printed["quarantine"] == [{"compound_id": "CMP0004", "issue_codes": ["invalid_smiles"]}]
    assert printed["summary"]["rows_accepted"] == 3
    assert printed["summary"]["rows_quarantined"] == 1
    run_dir = tmp_path / "results" / "r1_compounds"
    assert sorted(path.name for path in run_dir.iterdir()) == [
        "compound_structures.tsv",
        "compounds_audit.json",
        "run_manifest.json",
    ]
    manifest = read_json(run_dir / "run_manifest.json")
    assert (manifest["stage_status"], manifest["exit_code"]) == ("partial", 3)


def test_a_smiles_column_without_any_structure_is_quarantined_with_the_real_toolkit(
    tmp_path, capsys, chem
):
    import rdkit

    write_exports(tmp_path)
    config = write_config(tmp_path, [compound_row(1), compound_row(2)])
    assert invoke(config) == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "partial"
    assert [item["issue_codes"] for item in printed["quarantine"]] == [["missing_structure"]] * 2
    audit = read_json(tmp_path / "results" / "r1_compounds" / "compounds_audit.json")
    assert audit["toolkit"] == {"name": "rdkit", "version": rdkit.rdBase.rdkitVersion}


# --- exit codes that need no RDKit ----------------------------------------------------------------
def test_name_only_run_prints_its_summary_and_exits_0(tmp_path, capsys):
    config = write_config(tmp_path, [compound_row(1), compound_row(2)], columns=NAME_COLUMNS)
    assert invoke(config) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok"
    assert printed["identity_mode"] == "name_only"
    assert printed["summary"]["rows_name_only"] == 2
    assert (tmp_path / "results" / "r1_compounds" / "compound_structures.tsv").is_file()


def test_a_log_without_a_smiles_column_exits_2_and_writes_nothing(tmp_path, capsys):
    digests = write_exports(tmp_path)
    config = write_config(
        tmp_path,
        [compound_row(1)],
        columns=NAME_COLUMNS,
        log_rows=[log_row(1, digests[1])],
    )
    assert invoke(config) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "submission_log" in captured.err
    assert not (tmp_path / "results").exists()


def test_a_missing_config_exits_2(tmp_path, capsys):
    assert main(["ingest", "compounds", "--config", str(tmp_path / "nowhere.yaml")]) == 2
    assert "config not found" in capsys.readouterr().err


def test_an_existing_run_directory_needs_force(tmp_path, capsys):
    config = write_config(tmp_path, [compound_row(1)], columns=NAME_COLUMNS)
    assert invoke(config) == 0
    capsys.readouterr()
    assert invoke(config) == 2
    assert "already exists" in capsys.readouterr().err
    assert invoke(config, "--force") == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok"
    manifest = read_json(tmp_path / "results" / "r1_compounds" / "run_manifest.json")
    assert manifest["overwritten"] is True


def test_without_rdkit_structure_mode_exits_2_and_writes_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "rdkit", None)
    digests = write_exports(tmp_path)
    config = write_config(tmp_path, [compound_row(1, "CCO")], log_rows=[log_row(1, digests[1])])
    assert invoke(config) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "RDKit" in captured.err
    assert not (tmp_path / "results").exists()


def test_name_only_mode_needs_no_rdkit(tmp_path, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "rdkit", None)
    config = write_config(tmp_path, [compound_row(1)], columns=NAME_COLUMNS)
    assert invoke(config) == 0


# --- the manifest belongs to the family -----------------------------------------------------------
def test_rnp_manifest_reads_the_manifest_of_the_stage(tmp_path, capsys):
    config = write_config(tmp_path, [compound_row(1)], columns=NAME_COLUMNS)
    assert invoke(config) == 0
    capsys.readouterr()
    run_dir = tmp_path / "results" / "r1_compounds"
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok"
    assert printed["command"] == "ingest compounds"
    assert printed["run_id"] == "r1_compounds"
    assert printed["inputs_checked"] == 2 and printed["drift"] == []


def test_rnp_manifest_notices_that_the_compound_table_changed(tmp_path, capsys):
    config = write_config(tmp_path, [compound_row(1)], columns=NAME_COLUMNS)
    assert invoke(config) == 0
    capsys.readouterr()
    with (tmp_path / "inputs" / "compounds.tsv").open("a", encoding="utf-8") as handle:
        handle.write("Another\tall\tother.xlsx\n")
    run_dir = tmp_path / "results" / "r1_compounds"
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "drift"
    assert [os.path.basename(item["path"]) for item in printed["drift"]] == ["compounds.tsv"]


# --- the parser -----------------------------------------------------------------------------------
def test_the_help_of_the_command_hides_the_run_id_and_names_the_options(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["ingest", "compounds", "--help"])
    assert caught.value.code == 0
    text = capsys.readouterr().out
    assert "--config" in text and "--force" in text
    assert "--run-id" not in text


def test_the_ingest_group_lists_both_commands(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["ingest", "--help"])
    assert caught.value.code == 0
    text = capsys.readouterr().out
    assert "compounds" in text and "stp" in text
