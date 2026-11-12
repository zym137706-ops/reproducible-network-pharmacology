"""`rnp ingest stp --compounds DIR`: exit codes, the printed summary, the help and a run end to end.

The first tests use the compounds stage written with the fake structure describer; the last one runs
both commands of the pipeline (`rnp ingest compounds`, then `rnp ingest stp --compounds`) with the
real RDKit. It is skipped when RDKit is not installed, unless RNP_REQUIRE_CHEM is 1 (CI sets it).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from ingest_link_support import CLEAN, MIXED, build, compounds_stage, read_tsv

from rnp.cli import main

SUMMARY_KEYS = [
    "status",
    "stage_status",
    "run_id",
    "run_dir",
    "summary",
    "quarantine",
    "missing_exports",
]


@pytest.fixture
def chem():
    try:
        import rdkit  # noqa: F401
    except ImportError:
        if os.environ.get("RNP_REQUIRE_CHEM") == "1":
            pytest.fail("RDKit is required (RNP_REQUIRE_CHEM=1) but is not installed")
        pytest.skip("RDKit is not installed (optional extra 'chem')")


def invoke(config, *extra, run_id="i1"):
    return main(["ingest", "stp", "--config", str(config), "--run-id", run_id, *extra])


def test_a_clean_stage_exits_0_and_prints_the_usual_summary(tmp_path, capsys):
    config = build(tmp_path, CLEAN)
    stage = compounds_stage(config)
    assert invoke(config, "--compounds", str(stage)) == 0
    printed = json.loads(capsys.readouterr().out)
    assert list(printed) == SUMMARY_KEYS
    assert printed["status"] == "ok" and printed["stage_status"] == "complete"
    assert printed["quarantine"] == [] and printed["summary"]["rows_used"] == 3
    header = (Path(printed["run_dir"]) / "compounds_registered.tsv").read_text(encoding="utf-8")
    assert header.splitlines()[0].endswith("\tstructure_id\tstructure_status")


def test_a_quarantined_compound_exits_3(tmp_path, capsys):
    config = build(tmp_path, MIXED)
    stage = compounds_stage(config)
    assert invoke(config, "--compounds", str(stage)) == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "partial" and printed["stage_status"] == "partial"
    assert [(item["path"], item["reason"]) for item in printed["quarantine"]] == [
        ("c2.csv", "compound_quarantined"),
        ("c3.csv", "compound_quarantined"),
    ]


def test_a_stage_that_is_not_current_exits_2_and_writes_nothing(tmp_path, capsys):
    config = build(tmp_path, MIXED)
    stage = compounds_stage(config)
    with (tmp_path / "inputs" / "compounds.tsv").open("ab") as handle:
        handle.write(b"Compound 5\tall\tc5.csv\tCCCCC\t\n")
    assert invoke(config, "--compounds", str(stage)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "the compound table changed since the compounds stage" in captured.err
    assert not (tmp_path / "results" / "i1").exists()


def test_a_directory_that_does_not_exist_exits_2(tmp_path, capsys):
    config = build(tmp_path, CLEAN)
    compounds_stage(config)
    assert invoke(config, "--compounds", str(tmp_path / "nowhere")) == 2
    assert "compounds stage directory not found" in capsys.readouterr().err


def test_without_the_option_nothing_changes(tmp_path, capsys):
    config = build(tmp_path, CLEAN)
    compounds_stage(config)
    assert invoke(config) == 0
    printed = json.loads(capsys.readouterr().out)
    assert list(printed) == SUMMARY_KEYS
    path = Path(printed["run_dir"]) / "compounds_registered.tsv"
    assert path.read_text(encoding="utf-8").splitlines()[0].endswith("\tidentity_basis")


def test_the_help_names_the_option(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["ingest", "stp", "--help"])
    assert caught.value.code == 0
    text = capsys.readouterr().out
    assert "--compounds DIR" in text
    assert "compounds stage" in text
    assert "--force" in text and "--run-id" not in text


def test_both_commands_of_the_pipeline_work_together_with_the_real_toolkit(tmp_path, capsys, chem):
    config = build(tmp_path, [("CCO", "ok"), ("c1ccccc1", "ok"), ("", None)])
    assert main(["ingest", "compounds", "--config", str(config), "--run-id", "s"]) == 3
    stage = Path(json.loads(capsys.readouterr().out)["run_dir"])
    assert invoke(config, "--compounds", str(stage)) == 3
    printed = json.loads(capsys.readouterr().out)
    assert [(item["path"], item["reason"]) for item in printed["quarantine"]] == [
        ("c3.csv", "compound_quarantined")
    ]
    run_dir = Path(printed["run_dir"])
    rows = read_tsv(run_dir / "compounds_registered.tsv")
    assert [(row["structure_id"], row["structure_status"]) for row in rows] == [
        ("STR0001", "registered"),
        ("STR0002", "registered"),
        ("", "not_registered"),
    ]
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 0
