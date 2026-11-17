"""The independent recheck of the selection: `check_selection` in scripts/case_check.py.

From the compound table and the decision table alone, the recheck derives what the selection stage
of every threshold must say (the status and the id of every decision) and compares it with the stage
with the registered table and the ingest audit of the run, with `targets.tsv` and with the
intersection audit. It also holds the case to its policy: every candidate is decided (include or
exclude) and at least one is included. The cases are made by hand (case_selection_support), so
nothing here needs RDKit. Every problem is one line of the AssertionError message.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys

import pytest
from case_check_support import load_check
from case_run_support import ROOT, sha256_of
from case_selection_support import (
    SELECTION_COLUMNS,
    check_cli,
    decision_id,
    default_decisions,
    edit_audit,
    edit_chosen,
    edit_decisions,
    edit_ingest,
    edit_intersect,
    edit_registered,
    edit_table,
    edit_targets,
    make_selection_case,
    selection_problems,
    selection_recheck,
)

LABEL = "0.10"


def entry(number: int) -> str:
    return f"entry 'Compound {number}' (c{number}.csv)"


def dropped(column: str):
    """An edit of a table that removes a column (the header and every row)."""

    def edit(header, rows):
        header.remove(column)
        for row in rows:
            del row[column]

    return edit


def changed(row_number: int, column: str, value: str):
    """An edit of a table: set `column` of the `row_number`-th row (from 1)."""

    def edit(rows):
        rows[row_number - 1][column] = value

    return edit


# --- what the recheck is ---------------------------------------------------------------------
def test_the_names_the_case_entry_and_the_tests_rely_on() -> None:
    check = load_check()
    assert check.SELECTION_RULE == "case-selection-recheck-v1"
    assert list(check.SELECTION_COLUMNS) == SELECTION_COLUMNS
    assert list(inspect.signature(check.check_selection).parameters) == [
        "compounds",
        "decisions",
        "stages",
        "selection_stages",
        "runs",
    ]


def test_the_recheck_still_uses_only_the_standard_library_and_no_selection_code() -> None:
    tree = ast.parse((ROOT / "scripts" / "case_check.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imported.add(node.module or "")
    own = {name for name in imported if name.split(".")[0] == "rnp"}
    assert own == {"rnp.io.tables", "rnp.normalize.hgnc"}
    assert {name.split(".")[0] for name in imported} - {"rnp"} <= set(sys.stdlib_module_names)


def test_the_decision_id_rule_of_the_support_is_the_documented_one() -> None:
    row = {
        "compound_id": "CMP0001",
        "structure_id": "STR0001",
        "decision": "include",
        "decision_source": "recorded",
        "reason_codes": "",
        "rules_version": "RA-v1",
        "reviewer": "Researcher",
        "evidence_refs": "a.pdf",
    }
    assert decision_id(row) == "DEC-0723eb98486a"  # the id the core gives this decision


# --- a consistent case passes ---------------------------------------------------------------
def test_a_consistent_case_passes_and_is_recorded(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    record = selection_recheck(sc)
    assert record == {
        "rule": "case-selection-recheck-v1",
        "decisions_sha256": sha256_of(sc.decisions),
        "rows": 3,
        "status_counts": {"excluded": 1, "selected": 2},
        "thresholds": {
            LABEL: {
                "selection_table_sha256": sha256_of(sc.table(LABEL)),
                "selected_list_sha256": sha256_of(sc.chosen(LABEL)),
            }
        },
    }


def test_every_threshold_is_recorded_and_the_stages_agree(tmp_path) -> None:
    sc = make_selection_case(tmp_path, labels=("0.10", "0.05"))
    record = selection_recheck(sc)
    assert sorted(record["thresholds"]) == ["0.05", "0.10"]
    assert record["thresholds"]["0.05"] == record["thresholds"]["0.10"]


def test_a_group_column_is_followed(tmp_path) -> None:
    sc = make_selection_case(tmp_path, group=True)
    assert selection_recheck(sc)["status_counts"] == {"excluded": 1, "selected": 2}


@pytest.mark.parametrize(
    "style",
    ["names", "codes", "bom", "crlf", "spaces"],
)
def test_the_decision_table_is_read_like_the_core_reads_it(tmp_path, style) -> None:
    sc = make_selection_case(tmp_path)
    text = sc.decisions.read_bytes().decode("utf-8")
    if style == "names":  # case, punctuation and no-break spaces do not matter for names
        text = text.replace("Compound 1", "compound-1").replace("Compound 2", "COMPOUND 2")
    elif style == "codes":  # reason codes are sorted and repeats dropped
        text = text.replace("out_of_scope;too_polar", "too_polar;out_of_scope;too_polar")
    elif style == "bom":
        text = "﻿" + text
    elif style == "crlf":
        text = text.replace("\n", "\r\n")
    else:  # whitespace in the cells that the core collapses
        text = text.replace("Researcher", "  Researcher  ").replace("RA-v1", "RA-v1 ")
    sc.decisions.write_bytes(text.encode("utf-8"))
    edit_audit_hash(sc)
    assert selection_recheck(sc)["rows"] == 3


def edit_audit_hash(sc) -> None:
    """Record the new hash of the decision table in every selection audit."""
    for label in sc.selection_stages:
        edit_audit(
            sc,
            label,
            lambda a: a["inputs"]["selection"].__setitem__("sha256", sha256_of(sc.decisions)),
        )


# --- the decision table ---------------------------------------------------------------------
def test_a_decision_for_no_compound_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)

    def add(header, rows):
        rows.append({**rows[0], "compound": "Compound 9"})

    edit_decisions(sc, add)
    assert (
        "decisions.tsv: row 4 compound: no compound row matches 'Compound 9' (group 'all')"
    ) in selection_problems(sc)


def test_a_compound_decided_twice_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)

    def add(header, rows):
        rows.append({**rows[0], "compound": "compound 1"})

    edit_decisions(sc, add)
    assert (
        "decisions.tsv: row 4 compound: 'compound 1' (group 'all') is decided more than once"
    ) in selection_problems(sc)


def test_a_decision_of_another_group_is_no_decision_for_the_compound(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_decisions(sc, lambda header, rows: rows[0].__setitem__("group", "other"))
    lines = selection_problems(sc)
    assert (
        "decisions.tsv: row 1 compound: no compound row matches 'Compound 1' (group 'other')"
        in lines
    )
    assert (
        f"decisions.tsv: {entry(1)} decision: no decision is recorded, "
        "so the candidate is held for review"
    ) in lines


def test_an_unknown_decision_value_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_decisions(sc, lambda header, rows: rows[0].__setitem__("decision", "Include"))
    assert (
        "decisions.tsv: row 1 decision: 'Include' is not include, exclude or needs_review"
        in selection_problems(sc)
    )


def test_a_compound_without_a_decision_breaks_the_policy(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_decisions(sc, lambda header, rows: rows.pop(1))
    assert (
        f"decisions.tsv: {entry(2)} decision: no decision is recorded, "
        "so the candidate is held for review"
    ) in selection_problems(sc)


def test_a_compound_held_for_review_breaks_the_policy(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_decisions(sc, lambda header, rows: rows[1].__setitem__("decision", "needs_review"))
    assert (
        f"decisions.tsv: {entry(2)} decision: needs_review, not a decided candidate"
        in selection_problems(sc)
    )


def test_a_case_in_which_nothing_is_included_breaks_the_policy(tmp_path) -> None:
    sc = make_selection_case(tmp_path)

    def exclude_all(header, rows):
        for row in rows:
            row["decision"] = "exclude"

    edit_decisions(sc, exclude_all)
    assert "decisions.tsv: no compound is selected" in selection_problems(sc)


def test_a_decision_table_without_a_required_column_is_refused(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_decisions(sc, dropped("reviewer"))
    with pytest.raises(AssertionError) as raised:
        selection_recheck(sc)
    assert (
        str(raised.value) == "decisions.tsv: the decision table lacks required column(s): reviewer"
    )


# --- the selection stage --------------------------------------------------------------------
@pytest.mark.parametrize("column", SELECTION_COLUMNS)
def test_a_changed_cell_of_the_selection_table_is_named(tmp_path, column) -> None:
    sc = make_selection_case(tmp_path)
    edit_table(sc, LABEL, changed(1, column, "changed"))
    lines = selection_problems(sc)
    mine = [line for line in lines if f"selection_decisions.tsv: {entry(1)} {column}:" in line]
    assert len(mine) == 1 and "found 'changed'" in mine[0], lines


def test_the_derived_status_and_decision_id_are_stated_exactly(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_table(sc, LABEL, changed(3, "selection_status", "selected"))
    lines = selection_problems(sc)
    assert (
        f"{LABEL}: selection_decisions.tsv: {entry(3)} selection_status: "
        "expected 'excluded' from the inputs, found 'selected'"
    ) in lines


def test_a_missing_row_of_the_selection_table_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_table(sc, LABEL, lambda rows: rows.pop())
    assert (
        f"{LABEL}: selection_decisions.tsv: rows: expected 3 from the compound table, found 2"
        in selection_problems(sc)
    )


def test_a_table_changed_without_sealing_the_audit_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_table(sc, LABEL, changed(1, "reviewer", "Someone"), seal=False)
    lines = selection_problems(sc)
    assert any(
        line.startswith(f"{LABEL}: selection_audit.json: selection_decisions_sha256:")
        for line in lines
    )


def test_the_selected_list_must_be_the_selected_rows_of_the_table(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_chosen(sc, LABEL, lambda rows: rows.pop())
    assert (
        f"{LABEL}: selected_compounds.tsv: rows: expected 2 selected, found 1"
        in selection_problems(sc)
    )


def test_a_changed_cell_of_the_selected_list_is_named(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_chosen(sc, LABEL, changed(2, "reviewer", "Someone"))
    assert (
        f"{LABEL}: selected_compounds.tsv: {entry(2)} reviewer: "
        "expected 'Researcher' from the inputs, found 'Someone'"
    ) in selection_problems(sc)


def test_an_excluded_compound_in_the_selected_list_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)

    def add(rows):
        rows.append(dict(rows[0], name="Compound 3"))

    edit_chosen(sc, LABEL, add)
    assert (
        f"{LABEL}: selected_compounds.tsv: rows: expected 2 selected, found 3"
        in selection_problems(sc)
    )


AUDIT_CASES = [
    ("stage_status", "partial"),
    ("identity_mode", "name_only"),
    ("inputs.selection.sha256", "0" * 64),
    ("inputs.selection.rows", 4),
    ("inputs.compounds_stage.audit_sha256", "0" * 64),
    ("inputs.compounds_stage.table_sha256", "0" * 64),
    ("summary.candidates", 4),
    ("summary.selected", 3),
    ("summary.excluded", 0),
    ("summary.needs_review", 1),
    ("summary.quarantined", 1),
    ("summary.decisions_recorded", 2),
    ("summary.decisions_not_recorded", 1),
    ("summary.decisions_without_compound", 1),
    ("summary.warnings", 1),
    ("selection_decisions_sha256", "0" * 64),
    ("selected_compounds_sha256", "0" * 64),
]


def set_path(document, path, value):
    *parents, last = path.split(".")
    for part in parents:
        document = document[part]
    document[last] = value


@pytest.mark.parametrize(("field", "value"), AUDIT_CASES)
def test_a_changed_field_of_the_selection_audit_is_named(tmp_path, field, value) -> None:
    sc = make_selection_case(tmp_path)
    edit_audit(sc, LABEL, lambda audit: set_path(audit, field, value))
    lines = selection_problems(sc)
    mine = [
        line
        for line in lines
        if line.startswith(f"{LABEL}: selection_audit.json: {field}: expected")
    ]
    assert len(mine) == 1 and f"found {value!r}" in mine[0], lines


def test_an_issue_in_the_selection_audit_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    issue = {"level": "warning", "code": "no_decision_recorded", "compound_id": "CMP0001"}
    edit_audit(sc, LABEL, lambda audit: audit["issues"].append(issue))
    lines = selection_problems(sc)
    assert any(
        line.startswith(f"{LABEL}: selection_audit.json: issues: expected []") for line in lines
    )


# --- the run ---------------------------------------------------------------------------------
def test_the_registered_table_must_carry_the_status(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_registered(sc, LABEL, dropped("selection_status"))
    assert (
        f"{LABEL}: compounds_registered.tsv: selection_status: the column is missing"
        in selection_problems(sc)
    )


def test_a_wrong_status_in_the_registered_table_is_named(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_registered(
        sc, LABEL, lambda header, rows: rows[2].__setitem__("selection_status", "selected")
    )
    assert (
        f"{LABEL}: compounds_registered.tsv: {entry(3)} selection_status: "
        "expected 'excluded' from the selection, found 'selected'"
    ) in selection_problems(sc)


def test_a_wrong_compound_id_in_the_registered_table_is_named(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_registered(sc, LABEL, lambda header, rows: rows[0].__setitem__("compound_id", "CMP0099"))
    assert (
        f"{LABEL}: compounds_registered.tsv: {entry(1)} compound_id: "
        "expected 'CMP0001' from the selection, found 'CMP0099'"
    ) in selection_problems(sc)


@pytest.mark.parametrize(
    ("field", "value", "wanted"),
    [
        ("schema_version", "1.1", "'1.2' from the selection"),
        ("summary.files_not_selected", 0, "1 from the inputs"),
        ("summary.files_quarantined", 1, "0 from the case policy"),
    ],
)
def test_a_wrong_field_of_the_ingest_audit_is_named(tmp_path, field, value, wanted) -> None:
    sc = make_selection_case(tmp_path)
    edit_ingest(sc, LABEL, lambda audit: set_path(audit, field, value))
    assert (
        f"{LABEL}: stp_audit.json: {field}: expected {wanted}, found {value!r}"
    ) in selection_problems(sc)


def test_an_ingest_audit_without_the_selection_note_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_ingest(sc, LABEL, lambda audit: audit["notes"].pop())
    assert f"{LABEL}: stp_audit.json: notes: no selection_stage_applied note" in selection_problems(
        sc
    )


def test_a_target_of_an_excluded_compound_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)

    def add(rows):
        rows.append(dict(rows[0], compound_id="CMP0003", source_file="c3.csv"))

    edit_targets(sc, LABEL, add)
    lines = selection_problems(sc)
    assert f"{LABEL}: targets.tsv: row 3 compound_id: 'CMP0003' is not a selected compound" in lines
    assert (
        f"{LABEL}: targets.tsv: row 3 source_file: 'c3.csv' "
        "is not the export of a selected compound"
    ) in lines


def test_a_target_of_a_compound_nobody_registered_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_targets(sc, LABEL, lambda rows: rows[0].__setitem__("compound_id", "CMP0042"))
    assert (
        f"{LABEL}: targets.tsv: row 1 compound_id: 'CMP0042' is not a selected compound"
        in selection_problems(sc)
    )


def test_a_group_count_of_the_intersection_that_counts_everything_is_reported(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_intersect(sc, LABEL, lambda audit: audit["groups"]["all"].__setitem__("compounds", 3))
    assert (
        f"{LABEL}: intersect_audit.json: groups.all.compounds: expected 2 from the selected "
        "compounds, found 3"
    ) in selection_problems(sc)


def test_a_group_nobody_selected_must_not_be_listed(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_intersect(sc, LABEL, lambda audit: audit["groups"].__setitem__("g2", {"compounds": 1}))
    assert (
        f"{LABEL}: intersect_audit.json: groups: expected ['all'] from the selected compounds, "
        "found ['all', 'g2']"
    ) in selection_problems(sc)


# --- thresholds and files --------------------------------------------------------------------
def test_the_selection_tables_of_two_thresholds_must_be_the_same(tmp_path) -> None:
    sc = make_selection_case(tmp_path, labels=("0.10", "0.05"))
    edit_table(sc, "0.05", changed(1, "reviewer", "Researcher"))  # same value: still the same file
    selection_recheck(sc)
    edit_table(sc, "0.05", changed(1, "reviewer", "Someone"))
    lines = selection_problems(sc)
    assert any(
        line.startswith("0.10: selection_decisions.tsv: sha256: expected")
        and "from the selection stage of threshold 0.05" in line
        for line in lines
    )


@pytest.mark.parametrize(
    "missing",
    [
        "selection_decisions.tsv",
        "selected_compounds.tsv",
        "selection_audit.json",
        "compounds_registered.tsv",
        "stp_audit.json",
        "targets.tsv",
        "intersect_audit.json",
    ],
)
def test_a_missing_file_is_named(tmp_path, missing) -> None:
    sc = make_selection_case(tmp_path)
    paths = {
        "selection_decisions.tsv": sc.table(LABEL),
        "selected_compounds.tsv": sc.chosen(LABEL),
        "selection_audit.json": sc.audit(LABEL),
        "compounds_registered.tsv": sc.case.registered(LABEL),
        "stp_audit.json": sc.case.ingest_audit(LABEL),
        "targets.tsv": sc.targets(LABEL),
        "intersect_audit.json": sc.intersect(LABEL),
    }
    paths[missing].unlink()
    assert f"{LABEL}: {missing}: not found in {paths[missing].parent}" in selection_problems(sc)


def test_every_problem_is_reported_at_once(tmp_path) -> None:
    sc = make_selection_case(tmp_path)
    edit_table(sc, LABEL, changed(1, "reviewer", "Someone"))
    edit_ingest(sc, LABEL, lambda audit: audit.__setitem__("schema_version", "1.1"))
    edit_intersect(sc, LABEL, lambda audit: audit["groups"]["all"].__setitem__("compounds", 3))
    assert len(selection_problems(sc)) == 3


# --- the command line ------------------------------------------------------------------------
def cli(sc, tmp_path, *, selection: bool = True) -> list[str]:
    return check_cli(sc, tmp_path, selection=selection)


def stubbed(monkeypatch):
    check = load_check()
    monkeypatch.setattr(
        check, "check_run", lambda label, run, background, disease, mapper: {"stub": label}
    )
    return check


def test_main_writes_the_selection_record_next_to_the_binding_record(tmp_path, monkeypatch) -> None:
    sc = make_selection_case(tmp_path / "c", labels=("0.10", "0.05"))
    check = stubbed(monkeypatch)
    assert check.main(cli(sc, tmp_path)) == 0
    written = json.loads((tmp_path / "independent-check.json").read_text(encoding="utf-8"))
    assert sorted(written) == ["bindings", "disease_sha256", "hgnc_sha256", "runs", "selection"]
    assert written["selection"] == selection_recheck(sc)


def test_main_without_the_selection_options_writes_the_old_file(tmp_path, monkeypatch) -> None:
    sc = make_selection_case(tmp_path / "c")
    check = stubbed(monkeypatch)
    assert check.main(cli(sc, tmp_path, selection=False)) == 0
    written = json.loads((tmp_path / "independent-check.json").read_text(encoding="utf-8"))
    assert sorted(written) == ["bindings", "disease_sha256", "hgnc_sha256", "runs"]


def test_main_refuses_a_selection_without_the_binding_options(tmp_path, monkeypatch) -> None:
    sc = make_selection_case(tmp_path / "c")
    check = stubbed(monkeypatch)
    argv = cli(sc, tmp_path)
    for option in ("--compound-table", "--stp-dir", "--log", "--species", "--stage"):
        while option in argv:
            position = argv.index(option)
            del argv[position : position + 2]
    with pytest.raises(SystemExit) as raised:
        check.main(argv)
    assert str(raised.value) == (
        "the selection recheck needs the binding recheck: give --compound-table, --stp-dir, "
        "--log, --species and --stage together with --selection and --selection-stage"
    )
    assert not (tmp_path / "independent-check.json").exists()


def test_main_refuses_selection_stages_that_do_not_match_the_runs(tmp_path, monkeypatch) -> None:
    sc = make_selection_case(tmp_path / "c", labels=("0.10", "0.05"))
    check = stubbed(monkeypatch)
    argv = cli(sc, tmp_path)
    position = argv.index("--selection-stage")
    del argv[position : position + 2]
    with pytest.raises(SystemExit) as raised:
        check.main(argv)
    assert str(raised.value) == (
        "--run labels ['0.05', '0.10'] and --selection-stage labels ['0.05'] must be the same"
    )


def test_main_refuses_selection_stages_without_a_selection(tmp_path, monkeypatch) -> None:
    sc = make_selection_case(tmp_path / "c")
    check = stubbed(monkeypatch)
    argv = cli(sc, tmp_path)
    position = argv.index("--selection")
    del argv[position : position + 2]
    with pytest.raises(SystemExit) as raised:
        check.main(argv)
    assert str(raised.value) == "--selection-stage needs --selection"


def test_main_writes_nothing_when_the_selection_is_wrong(tmp_path, monkeypatch) -> None:
    sc = make_selection_case(tmp_path / "c")
    edit_table(sc, LABEL, changed(1, "reviewer", "Someone"))
    check = stubbed(monkeypatch)
    with pytest.raises(AssertionError):
        check.main(cli(sc, tmp_path))
    assert not (tmp_path / "independent-check.json").exists()


def test_the_default_decisions_of_the_support_include_all_but_the_last() -> None:
    table = default_decisions(3)
    assert [row["decision"] for row in table] == ["include", "include", "exclude"]
