"""`ingest stp --compounds DIR --selection DIR2`: only the exports of selected compounds are parsed.

The compounds stage runs first (`rnp ingest compounds`), then the selection stage
(`rnp compounds select`), then `ingest stp` reads both directories. The status of every candidate
decides what happens to its export: `selected` is parsed, `excluded` and `needs_review` are recorded
as `not_selected` (not parsed), `quarantined` stays quarantined. A selection stage that is not
current is refused before anything is written. Everything here runs with the fakes of
selection_support: no RDKit, no network.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import jsonschema
import pytest
from ingest_link_support import export_text
from selection_ingest_support import (
    ALL_FOUR,
    EVERYTHING_DECIDED,
    FOUR_OK,
    Case,
    decision,
    ingest,
    make,
    read_json,
    read_tsv,
    snapshot,
)
from selection_support import select, stage, write_decisions

from rnp.analysis.ingest import run_ingest
from rnp.config import load_config, load_schema
from rnp.errors import RnpError

REGISTERED_COLUMNS = [
    "compound_id",
    "group",
    "name",
    "stp_file",
    "submission_id",
    "identity_basis",
]
SUMMARY_KEYS = [
    "status",
    "stage_status",
    "run_id",
    "run_dir",
    "summary",
    "quarantine",
    "missing_exports",
]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_files(summary) -> dict[str, dict]:
    audit = read_json(Path(summary["run_dir"]) / "stp_audit.json")
    return {entry["path"]: entry for entry in audit["files"]}


# --- what the selection decides ------------------------------------------------------------------
def test_every_status_is_handled_as_the_requirement_says(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    summary = ingest(case)
    assert list(summary) == SUMMARY_KEYS
    assert (summary["status"], summary["stage_status"], summary["run_id"]) == (
        "partial",
        "partial",
        "i1",
    )
    assert summary["summary"] == {
        "files": 4,
        "files_bound": 1,
        "files_quarantined": 1,
        "files_not_selected": 2,
        "files_missing": 0,
        "rows_total": 2,
        "rows_valid": 2,
        "rows_invalid": 0,
        "rows_below_threshold": 0,
        "rows_used": 2,
        "compounds_registered": 4,
        "warnings": 0,
        "errors": 0,
    }
    assert summary["quarantine"] == [
        {"path": "c2.csv", "sha256": sha256(export_text(2)), "reason": "compound_quarantined"}
    ]
    assert summary["missing_exports"] == []
    files = run_files(summary)
    assert sorted(files) == ["c1.csv", "c2.csv", "c3.csv", "c4.csv"]
    assert [(name, files[name]["status"], files[name].get("reason")) for name in sorted(files)] == [
        ("c1.csv", "ok", None),
        ("c2.csv", "quarantined", "compound_quarantined"),
        ("c3.csv", "not_selected", "compound_excluded"),
        ("c4.csv", "not_selected", "compound_needs_review"),
    ]


def test_a_selection_that_decides_everything_gives_a_complete_stage(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    summary = ingest(case)
    assert (summary["status"], summary["stage_status"]) == ("ok", "complete")
    assert summary["quarantine"] == []
    assert summary["summary"] == {
        "files": 4,
        "files_bound": 2,
        "files_quarantined": 0,
        "files_not_selected": 2,
        "files_missing": 0,
        "rows_total": 3,
        "rows_valid": 3,
        "rows_invalid": 0,
        "rows_below_threshold": 0,
        "rows_used": 3,
        "compounds_registered": 4,
        "warnings": 0,
        "errors": 0,
    }
    files = run_files(summary)
    assert files["c1.csv"]["status"] == files["c4.csv"]["status"] == "ok"
    for name in ("c2.csv", "c3.csv"):
        assert files[name]["status"] == "not_selected"
        assert files[name]["reason"] == "compound_excluded"


def test_an_exclusion_resolves_a_quarantine_of_the_compounds_stage(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    compounds_audit = read_json(case.compounds / "compounds_audit.json")
    assert compounds_audit["stage_status"] == "partial"
    assert ingest(case)["stage_status"] == "complete"


def test_an_included_but_quarantined_compound_stays_quarantined(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    entry = run_files(ingest(case))["c2.csv"]
    assert (entry["status"], entry["reason"]) == ("quarantined", "compound_quarantined")
    assert (entry["rows_total"], entry["rows_used"]) == (0, 0)


def test_only_the_exports_of_selected_compounds_give_targets(tmp_path):
    first = make(tmp_path / "a", ALL_FOUR)
    rows = read_tsv(Path(ingest(first)["run_dir"]) / "targets.tsv")
    assert {row["source_file"] for row in rows} == {"c1.csv"}
    assert sorted(row["common_name"] for row in rows) == ["CA2", "TNF"]
    second = make(tmp_path / "b", EVERYTHING_DECIDED)
    rows = read_tsv(Path(ingest(second)["run_dir"]) / "targets.tsv")
    assert {row["source_file"] for row in rows} == {"c1.csv", "c4.csv"}
    assert sorted(row["common_name"] for row in rows) == ["CA2", "EGFR", "TNF"]


def test_the_exports_of_every_unselected_compound_are_not_read(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    for name in ("c3.csv", "c4.csv"):
        (case.root / "inputs" / "stp" / name).write_bytes(b"not an STP export at all")
    summary = ingest(case)
    files = run_files(summary)
    assert files["c3.csv"]["status"] == files["c4.csv"]["status"] == "not_selected"
    assert files["c3.csv"]["sha256"] == hashlib.sha256(b"not an STP export at all").hexdigest()
    assert summary["summary"]["errors"] == 0


def test_the_audit_says_why_an_export_was_not_used(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    audit = read_json(Path(ingest(case)["run_dir"]) / "stp_audit.json")
    jsonschema.validate(audit, load_schema("stp_audit"))
    assert audit["schema_version"] == "1.2"
    assert "parents" not in audit
    assert audit["stage_status"] == "partial"
    entry = {item["path"]: item for item in audit["files"]}["c3.csv"]
    assert entry == {
        "path": "c3.csv",
        "format": "csv",
        "sha256": sha256(export_text(3)),
        "status": "not_selected",
        "compound_id": "CMP0003",
        "group": "all",
        "reason": "compound_excluded",
        "warnings": [],
        "errors": [],
        "rows_total": 0,
        "rows_valid": 0,
        "rows_invalid": 0,
        "rows_below_threshold": 0,
        "rows_used": 0,
    }
    assert [item["path"] for item in audit["quarantine"]] == ["c2.csv"]
    assert audit["missing_exports"] == []


def test_the_audit_notes_the_selection_stage_after_the_compounds_stage(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    audit = read_json(Path(ingest(case)["run_dir"]) / "stp_audit.json")
    assert [note["code"] for note in audit["notes"]][-2:] == [
        "compounds_stage_applied",
        "selection_stage_applied",
    ]
    message = audit["notes"][-1]["message"]
    found = re.fullmatch(
        r"selection decisions come from the selection stage (.+): "
        r"selected 1, excluded 1, needs_review 1, quarantined 1",
        message,
    )
    assert found, message
    assert Path(found.group(1)) == case.selection.resolve()


def test_the_counts_of_the_note_follow_the_decisions(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    audit = read_json(Path(ingest(case)["run_dir"]) / "stp_audit.json")
    assert audit["notes"][-1]["message"].endswith(
        ": selected 2, excluded 2, needs_review 0, quarantined 0"
    )


# --- the registered table -------------------------------------------------------------------------
def test_the_registered_table_ends_with_the_selection_status(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    rows = read_tsv(Path(ingest(case)["run_dir"]) / "compounds_registered.tsv")
    assert list(rows[0]) == [
        *REGISTERED_COLUMNS,
        "structure_id",
        "structure_status",
        "selection_status",
    ]
    assert [(row["compound_id"], row["selection_status"]) for row in rows] == [
        ("CMP0001", "selected"),
        ("CMP0002", "quarantined"),
        ("CMP0003", "excluded"),
        ("CMP0004", "needs_review"),
    ]
    assert [row["structure_status"] for row in rows] == [
        "registered",
        "registered",
        "not_registered",
        "registered",
    ]


def test_a_name_only_stage_gets_just_the_selection_column(tmp_path):
    rows = [
        decision("Compound 1", "include"),
        decision("Compound 2", "exclude", reason="out_of_scope"),
        decision("Compound 3", "needs_review", reason="check_identity"),
    ]
    case = make(tmp_path, rows, mode="name", names=3)
    summary = ingest(case)
    assert summary["stage_status"] == "partial"
    table = read_tsv(Path(summary["run_dir"]) / "compounds_registered.tsv")
    assert list(table[0]) == [*REGISTERED_COLUMNS, "selection_status"]
    assert [row["selection_status"] for row in table] == ["selected", "excluded", "needs_review"]
    files = run_files(summary)
    assert [(name, files[name]["status"]) for name in sorted(files)] == [
        ("c1.csv", "ok"),
        ("c2.csv", "not_selected"),
        ("c3.csv", "not_selected"),
    ]
    assert files["c3.csv"]["reason"] == "compound_needs_review"


def test_the_selection_status_of_a_compound_in_another_group_is_its_own(tmp_path):
    rows = [
        decision("Compound 1", "include", group="g1"),
        decision("Compound 2", "exclude", group="g1", reason="x"),
        decision("Compound 3", "include", group="g2"),
        decision("Compound 4", "exclude", group="g2", reason="x"),
    ]
    case = make(tmp_path, rows, FOUR_OK, groups=["g1", "g1", "g2", "g2"])
    table = read_tsv(Path(ingest(case)["run_dir"]) / "compounds_registered.tsv")
    assert [(row["group"], row["selection_status"]) for row in table] == [
        ("g1", "selected"),
        ("g1", "excluded"),
        ("g2", "selected"),
        ("g2", "excluded"),
    ]


# --- the records ----------------------------------------------------------------------------------
def test_the_manifest_names_both_stages_as_its_parents(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    manifest = read_json(Path(ingest(case)["run_dir"]) / "run_manifest.json")
    jsonschema.validate(manifest, load_schema("run_manifest"))
    assert manifest["command"] == "ingest stp"
    assert manifest["stage_status"] == "partial" and manifest["exit_code"] == 3
    assert [parent["stage"] for parent in manifest["parents"]] == [
        "ingest compounds",
        "compounds select",
    ]
    compounds_audit = case.compounds / "compounds_audit.json"
    assert manifest["parents"][0] == {
        "stage": "ingest compounds",
        "dir": str(case.compounds.resolve()),
        "audit": "compounds_audit.json",
        "audit_sha256": hashlib.sha256(compounds_audit.read_bytes()).hexdigest(),
        "stage_status": "partial",
        "status_override": False,
    }
    selection_audit = case.selection / "selection_audit.json"
    assert manifest["parents"][1] == {
        "stage": "compounds select",
        "dir": str(case.selection.resolve()),
        "audit": "selection_audit.json",
        "audit_sha256": hashlib.sha256(selection_audit.read_bytes()).hexdigest(),
        "stage_status": "partial",
        "status_override": False,
    }
    assert manifest["args"]["compounds"] == str(case.compounds.resolve())
    assert manifest["args"]["selection"] == str(case.selection.resolve())


def test_the_parent_record_of_a_complete_selection_says_complete(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    manifest = read_json(Path(ingest(case)["run_dir"]) / "run_manifest.json")
    assert manifest["stage_status"] == "complete" and manifest["exit_code"] == 0
    assert manifest["parents"][1]["stage_status"] == "complete"


def test_the_manifest_lists_the_files_of_both_stages_as_inputs(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    manifest = read_json(Path(ingest(case)["run_dir"]) / "run_manifest.json")
    assert [Path(item["path"]).name for item in manifest["inputs"]] == [
        "run.yaml",
        "compounds.tsv",
        "c1.csv",
        "c2.csv",
        "c3.csv",
        "c4.csv",
        "compounds_audit.json",
        "compound_structures.tsv",
        "selection_audit.json",
        "selection_decisions.tsv",
        "selected_compounds.tsv",
        "decisions.tsv",
    ]
    for item in manifest["inputs"]:
        assert item["sha256"] == hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()


def registry_rows(case: Case) -> list[dict[str, str]]:
    """The identity registry without the time it was last written (it changes with every run)."""
    rows = read_tsv(case.registry)
    for row in rows:
        del row["last_seen_utc"]
    return rows


def test_the_identity_registry_is_written_as_without_the_selection(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    ingest(case, run_id="plain", selection=None)
    plain = registry_rows(case)
    assert [row["compound_id"] for row in plain] == ["CMP0001", "CMP0002", "CMP0003", "CMP0004"]
    ingest(case, run_id="chosen")
    assert registry_rows(case) == plain


def test_the_other_stages_are_not_touched(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    compounds, selection = snapshot(case.compounds), snapshot(case.selection)
    decisions = case.decisions.read_bytes()
    ingest(case)
    assert snapshot(case.compounds) == compounds
    assert snapshot(case.selection) == selection
    assert case.decisions.read_bytes() == decisions


def test_a_run_is_deterministic(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    first = Path(ingest(case, run_id="a")["run_dir"])
    second = Path(ingest(case, run_id="b")["run_dir"])
    for name in ("compounds_registered.tsv", "targets.tsv", "stp_audit.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_the_directories_may_be_given_as_text(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    expected = Path(ingest(case, run_id="a")["run_dir"]) / "targets.tsv"
    summary = ingest(Case(case.config, str(case.compounds), str(case.selection)), run_id="b")
    assert (Path(summary["run_dir"]) / "targets.tsv").read_bytes() == expected.read_bytes()


# --- an export that is not there ------------------------------------------------------------------
def test_the_missing_export_of_an_excluded_compound_is_not_an_error(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    (case.root / "inputs" / "stp" / "c3.csv").unlink()
    summary = ingest(case)
    assert (summary["status"], summary["stage_status"]) == ("ok", "complete")
    assert summary["missing_exports"] == []
    assert summary["summary"]["files"] == 3
    assert summary["summary"]["files_missing"] == 0 and summary["summary"]["errors"] == 0


def test_the_missing_export_of_a_compound_held_for_review_is_reported(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    (case.root / "inputs" / "stp" / "c4.csv").unlink()
    summary = ingest(case)
    assert summary["stage_status"] == "partial"
    assert summary["missing_exports"] == [
        {
            "compound_id": "CMP0004",
            "stp_file": "c4.csv",
            "status": "error",
            "reason": "missing_export",
        }
    ]
    assert summary["summary"]["files"] == 3
    assert summary["summary"]["files_missing"] == 1 and summary["summary"]["errors"] == 1


def test_the_missing_export_of_a_selected_compound_makes_the_stage_partial(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    (case.root / "inputs" / "stp" / "c1.csv").unlink()
    summary = ingest(case)
    assert summary["stage_status"] == "partial"
    assert [item["compound_id"] for item in summary["missing_exports"]] == ["CMP0001"]
    rows = read_tsv(Path(summary["run_dir"]) / "targets.tsv")
    assert {row["source_file"] for row in rows} == {"c4.csv"}


# --- nothing usable -------------------------------------------------------------------------------
NOBODY = [
    decision("Compound 1", "exclude", reason="out_of_scope"),
    decision("Compound 2", "exclude", reason="out_of_scope"),
    decision("Compound 3", "exclude", reason="out_of_scope"),
    decision("Compound 4", "needs_review", reason="check_identity"),
]


def test_when_nobody_is_selected_nothing_is_usable(tmp_path):
    case = make(tmp_path, NOBODY)
    before = case.registry.read_bytes()
    with pytest.raises(RnpError) as caught:
        ingest(case)
    assert caught.value.exit_code == 2
    assert caught.value.message == "ingest produced no usable export"
    assert caught.value.details == [
        "no compound was selected: every candidate is excluded, held for review or quarantined"
    ]
    assert not (tmp_path / "results" / "i1").exists()
    assert case.registry.read_bytes() == before


def test_the_selection_stage_itself_is_complete_when_nobody_is_selected(tmp_path):
    case = make(tmp_path, NOBODY)
    audit = read_json(case.selection / "selection_audit.json")
    assert audit["summary"]["selected"] == 0


def test_a_selected_compound_whose_export_is_missing_gives_the_usual_failure(tmp_path):
    rows = [
        decision("Compound 1", "include"),
        decision("Compound 2", "exclude", reason="x"),
        decision("Compound 3", "exclude", reason="x"),
        decision("Compound 4", "exclude", reason="x"),
    ]
    case = make(tmp_path, rows)
    (case.root / "inputs" / "stp" / "c1.csv").unlink()
    with pytest.raises(RnpError) as caught:
        ingest(case)
    assert caught.value.message == "ingest produced no usable export"
    assert caught.value.details == ["no export could be parsed"]
    assert not (tmp_path / "results" / "i1").exists()


# --- the option needs the compounds stage ---------------------------------------------------------
def refused(case: Case, fragment: str, *, run_id: str = "x1", **kwargs) -> RnpError:
    before = case.registry.read_bytes() if case.registry.exists() else None
    with pytest.raises(RnpError) as caught:
        ingest(case, run_id=run_id, **kwargs)
    assert caught.value.exit_code == 2
    assert fragment in caught.value.message
    assert not (case.root / "results" / run_id).exists()
    if before is not None:
        assert case.registry.read_bytes() == before
    return caught.value


def test_a_selection_without_a_compounds_stage_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    with pytest.raises(RnpError) as caught:
        run_ingest(load_config(case.config), run_id="x1", selection=case.selection)
    assert caught.value.exit_code == 2
    assert caught.value.message == "--selection needs --compounds"
    assert not (tmp_path / "results" / "x1").exists()


def test_a_selection_without_a_compounds_stage_is_refused_before_it_is_read(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    with pytest.raises(RnpError) as caught:
        run_ingest(load_config(case.config), run_id="x1", selection=tmp_path / "nowhere")
    assert caught.value.message == "--selection needs --compounds"


# --- a selection stage that is not current is refused ---------------------------------------------
def test_a_directory_that_does_not_exist_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    refused(case, "selection stage directory not found", selection=tmp_path / "nowhere")


def test_a_file_instead_of_a_directory_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    refused(case, "selection stage directory not found", selection=case.config)


def test_the_compounds_stage_directory_is_not_a_selection_stage(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    refused(case, "selection audit not found", selection=case.compounds)


def test_a_stage_without_its_audit_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    (case.selection / "selection_audit.json").unlink()
    refused(case, "selection audit not found")


def test_an_audit_that_is_not_json_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    (case.selection / "selection_audit.json").write_bytes(b"{not json")
    refused(case, "cannot read selection audit")


def test_an_audit_that_does_not_fit_its_schema_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    audit = read_json(case.selection / "selection_audit.json")
    audit["stage_status"] = "something else"
    (case.selection / "selection_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    refused(case, "selection audit")


def test_a_run_config_that_changed_after_the_stage_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    with case.config.open("ab") as handle:
        handle.write(b"\n# changed after the stages ran\n")
    newer = stage(case.config, run_id="s2")
    refused(
        Case(case.config, newer, case.selection), "run config changed since the selection stage"
    )


def test_a_stage_without_its_table_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    (case.selection / "selection_decisions.tsv").unlink()
    refused(case, "selection stage table not found")


def test_a_table_that_changed_after_the_stage_wrote_it_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    table = case.selection / "selection_decisions.tsv"
    table.write_bytes(table.read_bytes().replace(b"\tneeds_review\t", b"\tselected\t"))
    refused(case, "selection_decisions.tsv does not match its audit")


def test_a_stage_without_its_list_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    (case.selection / "selected_compounds.tsv").unlink()
    refused(case, "selection stage list not found")


def test_a_list_that_changed_after_the_stage_wrote_it_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    chosen = case.selection / "selected_compounds.tsv"
    chosen.write_bytes(chosen.read_bytes() + b"CMP0009\n")
    refused(case, "selected_compounds.tsv does not match its audit")


def test_a_decision_table_that_changed_after_the_stage_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    text = case.decisions.read_bytes().decode("utf-8").replace("needs_review", "include")
    case.decisions.write_bytes(text.encode("utf-8"))
    refused(case, "the decision table changed since the selection stage")


def test_a_decision_table_that_is_gone_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    case.decisions.unlink()
    refused(case, "inputs.selection is not a file")


def test_a_selection_stage_of_another_compounds_stage_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    table = case.root / "inputs" / "compounds.tsv"
    table.write_bytes(table.read_bytes().replace(b"CCO", b"CCCO"))
    newer = stage(case.config, run_id="s2")
    refused(
        Case(case.config, newer, case.selection),
        "the selection stage was made from another compounds stage",
    )


def test_an_audit_that_names_another_compounds_audit_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    audit = read_json(case.selection / "selection_audit.json")
    audit["inputs"]["compounds_stage"]["audit_sha256"] = "0" * 64
    (case.selection / "selection_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    refused(case, "the selection stage was made from another compounds stage")


def retable(case: Case, change) -> None:
    """Rewrite the table of the selection stage and put its new hash into the audit."""
    path = case.selection / "selection_decisions.tsv"
    lines = path.read_bytes().decode("utf-8").split("\n")
    lines = change(lines)
    data = "\n".join(lines).encode("utf-8")
    path.write_bytes(data)
    audit = read_json(case.selection / "selection_audit.json")
    audit["selection_decisions_sha256"] = hashlib.sha256(data).hexdigest()
    (case.selection / "selection_audit.json").write_text(json.dumps(audit), encoding="utf-8")


def test_a_table_with_rows_that_do_not_fit_their_schema_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    retable(
        case, lambda lines: [lines[0], lines[1].replace("\tselected\t", "\tmaybe\t"), *lines[2:]]
    )
    error = refused(case, "selection_decisions.tsv is not valid")
    assert error.details and error.details[0].startswith("row 1:")


def test_a_table_that_is_not_in_the_order_of_the_compounds_stage_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    retable(case, lambda lines: [lines[0], lines[2], lines[1], *lines[3:]])
    refused(case, "the selection stage does not match the compounds stage")


def test_a_table_with_fewer_rows_than_the_compounds_stage_is_refused(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    retable(case, lambda lines: lines[:-2] + [""])
    error = refused(case, "the selection stage does not match the compounds stage")
    assert error.details


# --- a decision that changes ----------------------------------------------------------------------
def test_a_changed_decision_needs_a_new_selection_stage(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    compounds = snapshot(case.compounds)
    assert ingest(case)["stage_status"] == "partial"
    write_decisions(
        case.decisions,
        [
            decision("Compound 1", "include"),
            decision("Compound 2", "include"),
            decision("Compound 3", "exclude", reason="no_structure;bad_data", refs="notes.pdf"),
            decision("Compound 4", "include", reason="checked"),
        ],
    )
    refused(case, "the decision table changed since the selection stage")
    newer = Path(select(case.config, case.compounds, run_id="sel2")["run_dir"])
    summary = ingest(case, run_id="i2", selection=newer)
    files = run_files(summary)
    assert files["c4.csv"]["status"] == "ok"
    assert files["c3.csv"]["status"] == "not_selected"
    assert files["c2.csv"]["status"] == "quarantined"
    assert summary["stage_status"] == "partial"
    assert snapshot(case.compounds) == compounds


def test_a_selection_stage_may_be_a_partial_one(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    assert read_json(case.selection / "selection_audit.json")["stage_status"] == "partial"
    assert ingest(case)["stage_status"] == "partial"


def test_the_exports_may_change_after_the_selection_for_a_quarantined_compound(tmp_path):
    case = make(tmp_path, ALL_FOUR)
    (case.root / "inputs" / "stp" / "c2.csv").write_bytes(b"changed later")
    assert run_files(ingest(case))["c2.csv"]["status"] == "quarantined"


def test_an_export_of_a_selected_compound_that_changed_after_the_compounds_stage_is_refused(
    tmp_path,
):
    case = make(tmp_path, EVERYTHING_DECIDED)
    (case.root / "inputs" / "stp" / "c1.csv").write_bytes(b"changed later")
    refused(case, "an export changed since the compounds stage")
