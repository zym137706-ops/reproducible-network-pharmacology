"""`rnp ingest stp --compounds DIR --selection DIR2`: exit codes, the printed summary and the help.

The stages are written with the fake structure describer (no RDKit, no network). The run of the
whole pipeline with the real toolkit is in test_selection_pipeline.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from selection_ingest_support import (
    ALL_FOUR,
    EVERYTHING_DECIDED,
    decision,
    make,
)

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


def invoke(case, *extra, run_id="i1", compounds=True, selection=True):
    arguments = ["ingest", "stp", "--config", str(case.config), "--run-id", run_id]
    if compounds:
        arguments += ["--compounds", str(case.compounds)]
    if selection:
        arguments += ["--selection", str(case.selection)]
    return main([*arguments, *extra])


def test_a_complete_selection_exits_0_and_prints_the_usual_summary(tmp_path, capsys):
    case = make(tmp_path, EVERYTHING_DECIDED)
    assert invoke(case) == 0
    printed = json.loads(capsys.readouterr().out)
    assert list(printed) == SUMMARY_KEYS
    assert printed["status"] == "ok" and printed["stage_status"] == "complete"
    assert printed["quarantine"] == [] and printed["summary"]["rows_used"] == 3
    assert printed["summary"]["files_not_selected"] == 2
    header = (Path(printed["run_dir"]) / "compounds_registered.tsv").read_text(encoding="utf-8")
    assert header.splitlines()[0].endswith("\tstructure_status\tselection_status")


def test_a_compound_held_for_review_or_quarantined_exits_3(tmp_path, capsys):
    case = make(tmp_path, ALL_FOUR)
    assert invoke(case) == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "partial" and printed["stage_status"] == "partial"
    assert [(item["path"], item["reason"]) for item in printed["quarantine"]] == [
        ("c2.csv", "compound_quarantined")
    ]
    assert printed["summary"]["files_not_selected"] == 2


def test_a_selection_without_the_compounds_stage_exits_2_and_writes_nothing(tmp_path, capsys):
    case = make(tmp_path, ALL_FOUR)
    assert invoke(case, compounds=False) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--selection needs --compounds" in captured.err
    assert not (tmp_path / "results" / "i1").exists()


def test_a_selection_that_is_not_current_exits_2_and_writes_nothing(tmp_path, capsys):
    case = make(tmp_path, ALL_FOUR)
    text = case.decisions.read_bytes().decode("utf-8").replace("needs_review", "include")
    case.decisions.write_bytes(text.encode("utf-8"))
    assert invoke(case) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "the decision table changed since the selection stage" in captured.err
    assert not (tmp_path / "results" / "i1").exists()


def test_a_directory_that_does_not_exist_exits_2(tmp_path, capsys):
    case = make(tmp_path, ALL_FOUR)
    case.selection = tmp_path / "nowhere"
    assert invoke(case) == 2
    assert "selection stage directory not found" in capsys.readouterr().err


def test_when_nobody_is_selected_the_command_exits_2(tmp_path, capsys):
    rows = [decision(f"Compound {n}", "exclude", reason="out_of_scope") for n in range(1, 5)]
    case = make(tmp_path, rows)
    assert invoke(case) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ingest produced no usable export" in captured.err
    assert "no compound was selected" in captured.err
    assert not (tmp_path / "results" / "i1").exists()


def test_without_the_option_nothing_changes(tmp_path, capsys):
    case = make(tmp_path, EVERYTHING_DECIDED)
    assert invoke(case, selection=False) == 3
    printed = json.loads(capsys.readouterr().out)
    assert list(printed) == SUMMARY_KEYS
    assert "files_not_selected" not in printed["summary"]
    path = Path(printed["run_dir"]) / "compounds_registered.tsv"
    assert path.read_text(encoding="utf-8").splitlines()[0].endswith("\tstructure_status")


def test_the_help_names_the_option(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["ingest", "stp", "--help"])
    assert caught.value.code == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "--selection DIR" in text
    assert "selection stage" in text
    assert "needs --compounds" in text
    assert "--compounds DIR" in text and "--force" in text and "--run-id" not in text


def test_the_manifest_of_the_run_checks_out_and_a_changed_decision_is_drift(tmp_path, capsys):
    case = make(tmp_path, EVERYTHING_DECIDED)
    assert invoke(case) == 0
    run_dir = Path(json.loads(capsys.readouterr().out)["run_dir"])
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 0
    assert json.loads(capsys.readouterr().out)["drift"] == []
    text = case.decisions.read_bytes().decode("utf-8").replace("ok_by_hand", "changed")
    case.decisions.write_bytes(text.encode("utf-8"))
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 3
    drift = json.loads(capsys.readouterr().out)["drift"]
    assert [(Path(item["path"]).name, item["problem"]) for item in drift] == [
        ("decisions.tsv", "sha256 changed")
    ]
