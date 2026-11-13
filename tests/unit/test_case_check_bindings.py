"""The independent recheck of the submission bindings: `check_bindings` in scripts/case_check.py.

From the compound table, the submission log and the STP exports alone, the recheck derives what the
compounds stage of every threshold must say, and compares. The cases are made by hand
(case_check_support.make_case), so nothing here needs RDKit. Every problem is one line of the
AssertionError message:
`<threshold>: <file>: [entry '<name>' (<stp_file>) ]<field>: expected <x> from <source>, found <y>`.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys

import pytest
from case_check_support import (
    DERIVED_COLUMNS,
    edit_audit,
    edit_compounds,
    edit_log,
    edit_registered,
    edit_stage,
    load_check,
    make_case,
    problems,
    recheck,
    reseal_inputs,
    seal_registered,
    seal_stage,
)
from case_run_support import ROOT, rewrite, sha256_of

from rnp.analysis.compounds_link import CHECKED_SUBMISSIONS

STAGE = "compound_structures.tsv"
AUDIT = "compounds_audit.json"
REGISTERED = "compounds_registered.tsv"
INGEST = "stp_audit.json"
LABEL = "0.10"
HGNC = ROOT / "tests" / "fixtures" / "hgnc" / "hgnc_map.tsv"


def entry(number: int) -> str:
    return f"entry 'Compound {number}' (c{number}.csv)"


def stage_line(number: int, field: str, expected, found, source: str = "the inputs") -> str:
    return (
        f"{LABEL}: {STAGE}: {entry(number)} {field}: "
        f"expected {expected!r} from {source}, found {found!r}"
    )


def rejected_line(number: int, reasons: str) -> str:
    return (
        f"log.tsv: {entry(number)} submission_status: derived 'rejected' from the inputs "
        f"({reasons}), not a checked submission"
    )


# --- what the tests rely on --------------------
def test_the_names_the_case_entry_and_the_tests_rely_on() -> None:
    check = load_check()
    assert check.BINDING_RULE == "case-binding-recheck-v1"
    assert list(check.DERIVED_COLUMNS) == DERIVED_COLUMNS
    assert set(check.CHECKED_STATUSES) == CHECKED_SUBMISSIONS
    assert list(inspect.signature(check.check_bindings).parameters) == [
        "compounds",
        "stp_dir",
        "log",
        "species",
        "stages",
        "runs",
    ]


def test_the_recheck_uses_only_the_standard_library_and_no_structure_code() -> None:
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
    others = {name.split(".")[0] for name in imported} - {"rnp"}
    assert others <= set(sys.stdlib_module_names)


# --- a consistent case passes --------------------
def test_a_consistent_case_passes_and_is_recorded(tmp_path) -> None:
    case = make_case(tmp_path, rows=3, labels=("0.10", "0.05"))
    assert recheck(case) == {
        "rule": "case-binding-recheck-v1",
        "species": "Homo sapiens",
        "compounds_sha256": sha256_of(case.compounds),
        "submission_log_sha256": sha256_of(case.log),
        "rows": 3,
        "submission_status_counts": {"verified_kind_unstated": 3},
        "derived_columns": DERIVED_COLUMNS,
        "thresholds": {
            label: {"stage_table_sha256": sha256_of(case.stage_table(label))}
            for label in ("0.05", "0.10")
        },
    }


def test_every_export_kind_gets_its_status(tmp_path) -> None:
    kinds = ["native_export", "", "reconstructed_from_result_page"]
    case = make_case(tmp_path, kinds=kinds)
    assert recheck(case)["submission_status_counts"] == {
        "reconstructed": 1,
        "verified": 1,
        "verified_kind_unstated": 1,
    }


def test_the_core_cleaning_rules_are_followed(tmp_path) -> None:
    case = make_case(tmp_path, messy=True, group=True)
    assert recheck(case)["rows"] == 3


def test_a_log_without_an_export_kind_column_states_no_kind(tmp_path) -> None:
    case = make_case(tmp_path)

    def drop(header, rows) -> None:
        header.remove("export_kind")
        for row in rows:
            del row["export_kind"]

    edit_log(case, drop)
    reseal_inputs(case)
    assert recheck(case)["submission_status_counts"] == {"verified_kind_unstated": 3}


@pytest.mark.parametrize(
    "style", ["bom", "crlf", "blank_rows", "comma_log", "reordered", "short_rows"]
)
def test_the_tables_are_read_like_the_core_reads_them(tmp_path, style) -> None:
    case = make_case(tmp_path)
    for path in (case.compounds, case.log):
        text = path.read_bytes().decode("utf-8")
        lines = text.rstrip("\n").split("\n")
        if style == "bom":
            data = ("\ufeff" + text).encode("utf-8")
        elif style == "crlf":
            data = text.replace("\n", "\r\n").encode("utf-8")
        elif style == "blank_rows":
            data = ("\n".join([lines[0], "", *lines[1:], "", ""]) + "\n").encode("utf-8")
        elif style == "comma_log":
            data = (text.replace("\t", ",") if path == case.log else text).encode("utf-8")
        elif style == "short_rows":
            data = ("\n".join(line.rstrip("\t") for line in lines) + "\n").encode("utf-8")
        else:
            data = (
                "\n".join("\t".join(reversed(line.split("\t"))) for line in lines) + "\n"
            ).encode("utf-8")
        path.write_bytes(data)
    reseal_inputs(case)
    assert recheck(case)["rows"] == 3


# --- the stage table: every compared column --------------------
@pytest.mark.parametrize(
    "column,value",
    [
        ("name", "Other"),
        ("group", "g"),
        ("stp_file", "x.csv"),
        ("smiles", "CCCC"),
        ("submission_status", "verified"),
        ("export_kind", "native_export"),
        ("export_sha256", "0" * 64),
    ],
)
def test_a_changed_column_of_the_stage_table_is_named(tmp_path, column, value) -> None:
    case = make_case(tmp_path)
    derived = {
        "name": "Compound 2",
        "group": "all",
        "stp_file": "c2.csv",
        "smiles": "CCC",
        "submission_status": "verified_kind_unstated",
        "export_kind": "",
        "export_sha256": sha256_of(case.export(2)),
    }
    edit_stage(case, LABEL, lambda rows: rows[1].__setitem__(column, value))
    assert problems(case) == [stage_line(2, column, derived[column], value)]


def test_a_quarantined_row_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_stage(case, LABEL, lambda rows: rows[1].__setitem__("row_status", "quarantined"))
    assert problems(case) == [
        f"{LABEL}: {STAGE}: {entry(2)} row_status: 'quarantined', not 'accepted'",
        f"{LABEL}: {AUDIT}: summary.rows_accepted: expected 2 from {STAGE}, found 3",
        f"{LABEL}: {AUDIT}: summary.rows_quarantined: expected 1 from {STAGE}, found 0",
    ]


def test_an_unregistered_structure_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_stage(case, LABEL, lambda rows: rows[0].__setitem__("structure_status", "not_registered"))
    assert problems(case) == [
        f"{LABEL}: {STAGE}: {entry(1)} structure_status: 'not_registered', not 'registered'",
        f"{LABEL}: {REGISTERED}: {entry(1)} structure_status: "
        f"expected 'not_registered' from {STAGE}, found 'registered'",
    ]


def test_an_invalid_inchikey_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_stage(case, LABEL, lambda rows: rows[2].__setitem__("inchikey", "not-a-key"))
    assert problems(case) == [
        f"{LABEL}: {STAGE}: {entry(3)} inchikey: 'not-a-key' is not an InChIKey"
    ]


def test_a_repeated_compound_id_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_stage(case, LABEL, lambda rows: rows[1].__setitem__("compound_id", "CMP0001"))
    assert f"{LABEL}: {STAGE}: {entry(2)} compound_id: 'CMP0001' is empty or repeated" in problems(
        case
    )


@pytest.mark.parametrize("value", ["", "X1", "STR0001"])
def test_a_wrong_or_repeated_structure_id_is_refused(tmp_path, value) -> None:
    case = make_case(tmp_path)
    edit_stage(case, LABEL, lambda rows: rows[1].__setitem__("structure_id", value))
    assert (
        f"{LABEL}: {STAGE}: {entry(2)} structure_id: {value!r} is not a structure id or is repeated"
    ) in problems(case)


def test_a_dropped_or_added_stage_row_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_stage(case, LABEL, lambda rows: rows.pop())
    assert f"{LABEL}: {STAGE}: rows: expected 3 from the compound table, found 2" in problems(case)
    case = make_case(tmp_path / "more")
    edit_stage(case, LABEL, lambda rows: rows.append(dict(rows[-1])))
    assert f"{LABEL}: {STAGE}: rows: expected 3 from the compound table, found 4" in problems(case)


# --- the stage audit: every compared field --------------------
def audit_cases(case):
    compounds, log = sha256_of(case.compounds), sha256_of(case.log)
    table = sha256_of(case.stage_table(LABEL))
    zero = "0" * 64
    return [
        ("identity_mode", "name_only", "structure", "the case policy"),
        ("stage_status", "partial", "complete", "the case policy"),
        ("inputs.compounds.sha256", zero, compounds, "the inputs"),
        ("inputs.compounds.rows", 99, 3, "the inputs"),
        ("inputs.submission_log.sha256", zero, log, "the inputs"),
        ("inputs.submission_log.rows", 99, 3, "the inputs"),
        ("inputs.stp_dir.files_hashed", 99, 3, "the inputs"),
        ("compound_structures_sha256", zero, table, STAGE),
        ("summary.rows", 99, 3, "the inputs"),
        ("summary.rows_accepted", 99, 3, STAGE),
        ("summary.rows_quarantined", 1, 0, STAGE),
        ("summary.rows_name_only", 1, 0, "the case policy"),
        ("summary.submissions_verified", 99, 3, "the inputs"),
        ("summary.submissions_reconstructed", 1, 0, "the inputs"),
        ("summary.submissions_not_recorded", 1, 0, "the inputs"),
        ("summary.submissions_rejected", 1, 0, "the inputs"),
        ("summary.errors", 1, 0, "the case policy"),
    ]


@pytest.mark.parametrize("index", range(17))
def test_a_changed_field_of_the_stage_audit_is_named(tmp_path, index) -> None:
    case = make_case(tmp_path)
    field, wrong, right, source = audit_cases(case)[index]

    def change(audit) -> None:
        *path, last = field.split(".")
        node = audit
        for key in path:
            node = node[key]
        node[last] = wrong

    edit_audit(case, LABEL, change)
    assert problems(case) == [
        f"{LABEL}: {AUDIT}: {field}: expected {right!r} from {source}, found {wrong!r}"
    ]


def test_a_missing_field_of_the_stage_audit_is_found_as_none(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_audit(case, LABEL, lambda audit: audit["summary"].pop("errors"))
    assert problems(case) == [
        f"{LABEL}: {AUDIT}: summary.errors: expected 0 from the case policy, found None"
    ]


def test_the_verified_count_includes_the_kind_unstated(tmp_path) -> None:
    case = make_case(tmp_path, kinds=["native_export", "", "reconstructed_from_result_page"])
    edit_audit(case, LABEL, lambda audit: audit["summary"].__setitem__("submissions_verified", 1))
    assert problems(case) == [
        f"{LABEL}: {AUDIT}: summary.submissions_verified: expected 2 from the inputs, found 1"
    ]


# --- missing files --------------------
@pytest.mark.parametrize(
    "where,name",
    [
        ("stages", STAGE),
        ("stages", AUDIT),
        ("runs", REGISTERED),
        ("runs", INGEST),
    ],
)
def test_a_missing_file_is_named(tmp_path, where, name) -> None:
    case = make_case(tmp_path)
    directory = getattr(case, where)[LABEL]
    (directory / name).unlink()
    assert problems(case) == [f"{LABEL}: {name}: not found in {directory}"]


# --- the inputs --------------------
def test_a_changed_export_makes_the_submission_rejected(tmp_path) -> None:
    case = make_case(tmp_path)
    old = sha256_of(case.export(2))
    case.export(2).write_bytes(b"changed")
    assert problems(case) == [
        rejected_line(2, "result_sha256"),
        stage_line(2, "submission_status", "rejected", "verified_kind_unstated"),
        stage_line(2, "export_sha256", sha256_of(case.export(2)), old),
        f"{LABEL}: {AUDIT}: summary.submissions_verified: expected 2 from the inputs, found 3",
        f"{LABEL}: {AUDIT}: summary.submissions_rejected: expected 1 from the inputs, found 0",
    ]


@pytest.mark.parametrize(
    "column,value,reason",
    [
        ("compound", "Other name", "compound"),
        ("pubchem_cid", "1", "pubchem_cid"),
        ("submitted_structure", "CCCC", "submitted_structure"),
        ("species", "Mus musculus", "species"),
        ("result_sha256", "0" * 64, "result_sha256"),
    ],
)
def test_a_log_row_that_contradicts_the_inputs_is_rejected(tmp_path, column, value, reason) -> None:
    case = make_case(tmp_path)
    edit_log(case, lambda header, rows: rows[1].__setitem__(column, value))
    lines = problems(case)
    assert rejected_line(2, reason) in lines
    assert stage_line(2, "submission_status", "rejected", "verified_kind_unstated") in lines


def test_the_reasons_of_a_rejection_come_in_a_fixed_order(tmp_path) -> None:
    case = make_case(tmp_path)

    def change(header, rows) -> None:
        rows[1]["species"] = "Mus musculus"
        rows[1]["submitted_structure"] = "CCCC"
        rows[1]["compound"] = "Other name"

    edit_log(case, change)
    assert rejected_line(2, "compound, submitted_structure, species") in problems(case)


def test_a_compound_without_a_log_row_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    old = sha256_of(case.export(2))
    edit_log(case, lambda header, rows: rows.pop(1))
    reseal_inputs(case)
    audit = f"{LABEL}: {AUDIT}: "
    assert problems(case) == [
        f"log.tsv: {entry(2)} stp_file: no submission log row belongs to this compound",
        stage_line(2, "submission_status", "not_recorded", "verified_kind_unstated"),
        stage_line(2, "export_sha256", "", old),
        audit + "inputs.submission_log.rows: expected 2 from the inputs, found 3",
        audit + "inputs.stp_dir.files_hashed: expected 2 from the inputs, found 3",
        audit + "summary.submissions_verified: expected 2 from the inputs, found 3",
        audit + "summary.submissions_not_recorded: expected 1 from the inputs, found 0",
    ]


def test_a_log_row_without_a_compound_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_log(case, lambda header, rows: rows.append({**rows[0], "stp_file": "zzz.csv"}))
    lines = problems(case)
    assert "log.tsv: row 4 stp_file: no compound row has stp_file 'zzz.csv'" in lines
    assert (
        f"{LABEL}: {AUDIT}: inputs.submission_log.rows: expected 4 from the inputs, found 3"
        in lines
    )


def test_a_log_row_that_declares_no_hash_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_log(case, lambda header, rows: rows[1].__setitem__("result_sha256", ""))
    reseal_inputs(case)
    assert problems(case) == [f"log.tsv: {entry(2)} result_sha256: the log does not declare it"]


def test_a_missing_export_file_makes_the_submission_rejected(tmp_path) -> None:
    case = make_case(tmp_path)
    case.export(2).unlink()
    lines = problems(case)
    assert rejected_line(2, "stp_file") in lines
    assert (
        f"{LABEL}: {AUDIT}: inputs.stp_dir.files_hashed: expected 2 from the inputs, found 3"
        in lines
    )


def test_an_export_kind_the_rules_do_not_know_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_log(case, lambda header, rows: rows[1].__setitem__("export_kind", "weird"))
    reseal_inputs(case)
    assert f"log.tsv: {entry(2)} export_kind: 'weird' is not a known export kind" in problems(case)


def test_a_compound_without_a_structure_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_compounds(case, lambda header, rows: rows[1].__setitem__("smiles", ""))
    reseal_inputs(case)
    lines = problems(case)
    assert f"compounds.tsv: {entry(2)} smiles: empty, so no structure was submitted" in lines
    assert stage_line(2, "smiles", "", "CCC") in lines


def test_a_compound_table_changed_after_the_stage_is_noticed(tmp_path) -> None:
    case = make_case(tmp_path)
    old = sha256_of(case.compounds)

    def add_note(header, rows) -> None:
        header.append("note")
        for row in rows:
            row["note"] = "x"

    edit_compounds(case, add_note)
    assert problems(case) == [
        f"{LABEL}: {AUDIT}: inputs.compounds.sha256: "
        f"expected {sha256_of(case.compounds)!r} from the inputs, found {old!r}"
    ]


def test_a_log_changed_after_the_stage_is_noticed(tmp_path) -> None:
    case = make_case(tmp_path)
    old = sha256_of(case.log)

    def add_note(header, rows) -> None:
        header.append("note")
        for row in rows:
            row["note"] = "x"

    edit_log(case, add_note)
    assert problems(case) == [
        f"{LABEL}: {AUDIT}: inputs.submission_log.sha256: "
        f"expected {sha256_of(case.log)!r} from the inputs, found {old!r}"
    ]


def test_the_compound_table_is_compared_row_by_row_in_its_order(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_compounds(case, lambda header, rows: rows.insert(0, rows.pop(1)))
    reseal_inputs(case)
    lines = problems(case)
    assert stage_line(2, "name", "Compound 2", "Compound 1") in lines
    assert stage_line(2, "stp_file", "c2.csv", "c1.csv") in lines


# --- the registered table and the ingest audit --------------------
def test_a_changed_structure_id_in_the_registered_table_is_named(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_registered(case, LABEL, lambda rows: rows[0].__setitem__("structure_id", "STR0009"))
    assert problems(case) == [
        f"{LABEL}: {REGISTERED}: {entry(1)} structure_id: "
        f"expected 'STR0001' from {STAGE}, found 'STR0009'"
    ]


def test_a_changed_structure_status_in_the_registered_table_is_named(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_registered(case, LABEL, lambda rows: rows[2].__setitem__("structure_status", "x"))
    assert problems(case) == [
        f"{LABEL}: {REGISTERED}: {entry(3)} structure_status: "
        f"expected 'registered' from {STAGE}, found 'x'"
    ]


def test_a_changed_name_in_the_registered_table_is_named(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_registered(case, LABEL, lambda rows: rows[0].__setitem__("name", "Other"))
    assert problems(case) == [
        f"{LABEL}: {REGISTERED}: {entry(1)} name: "
        "expected 'Compound 1' from the inputs, found 'Other'"
    ]


def test_a_dropped_row_of_the_registered_table_is_named(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_registered(case, LABEL, lambda rows: rows.pop())
    assert problems(case) == [
        f"{LABEL}: {REGISTERED}: rows: expected 3 from the compound table, found 2"
    ]


def test_a_wrong_hash_of_the_registered_table_in_the_ingest_audit_is_named(tmp_path) -> None:
    case = make_case(tmp_path)
    actual = sha256_of(case.registered(LABEL))
    path = case.ingest_audit(LABEL)
    path.write_text(path.read_text(encoding="utf-8").replace(actual, "0" * 64), encoding="utf-8")
    assert problems(case) == [
        f"{LABEL}: {INGEST}: compounds_registered_sha256: "
        f"expected {actual!r} from {REGISTERED}, found {'0' * 64!r}"
    ]


# --- several thresholds --------------------
def test_the_stage_tables_of_the_thresholds_must_be_the_same(tmp_path) -> None:
    case = make_case(tmp_path, labels=("0.10", "0.05"))
    edit_stage(
        case,
        "0.10",
        lambda rows: rows[0].__setitem__("inchikey", "AAAAAAAAAAAAAB-UHFFFAOYSA-N"),
    )
    assert problems(case) == [
        f"0.10: {STAGE}: sha256: expected {sha256_of(case.stage_table('0.05'))!r} "
        f"from the stage of threshold 0.05, found {sha256_of(case.stage_table('0.10'))!r}"
    ]


def test_every_problem_of_every_threshold_is_reported_together(tmp_path) -> None:
    case = make_case(tmp_path, labels=("0.10", "0.05"))
    edit_log(case, lambda header, rows: rows[1].__setitem__("result_sha256", ""))
    reseal_inputs(case)
    edit_stage(case, "0.10", lambda rows: rows[0].__setitem__("name", "Other"))
    edit_stage(case, "0.05", lambda rows: rows[2].__setitem__("smiles", "CCCC"))
    assert problems(case) == [
        f"log.tsv: {entry(2)} result_sha256: the log does not declare it",
        f"0.05: {STAGE}: {entry(3)} smiles: expected 'CCN' from the inputs, found 'CCCC'",
        f"0.10: {STAGE}: {entry(1)} name: expected 'Compound 1' from the inputs, found 'Other'",
        f"0.10: {STAGE}: sha256: expected {sha256_of(case.stage_table('0.05'))!r} "
        f"from the stage of threshold 0.05, found {sha256_of(case.stage_table('0.10'))!r}",
    ]


# --- the inputs cannot be read --------------------
def test_a_log_without_a_required_column_is_named(tmp_path) -> None:
    case = make_case(tmp_path)

    def drop(header, rows) -> None:
        for column in ("species", "submitted_date"):
            header.remove(column)
            for row in rows:
                del row[column]

    edit_log(case, drop)
    with pytest.raises(AssertionError) as raised:
        recheck(case)
    assert (
        str(raised.value)
        == "log.tsv: the submission log lacks required column(s): species, submitted_date"
    )


def test_a_log_that_repeats_a_column_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    lines = case.log.read_text(encoding="utf-8").split("\n")
    lines[0] += "\tstp_file"
    case.log.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(AssertionError) as raised:
        recheck(case)
    assert str(raised.value) == "log.tsv: the header repeats a column name"


def test_a_log_that_repeats_an_export_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_log(case, lambda header, rows: rows.append(dict(rows[0])))
    with pytest.raises(AssertionError) as raised:
        recheck(case)
    assert str(raised.value) == "log.tsv: stp_file 'c1.csv' appears more than once"


def test_a_compound_table_without_a_smiles_column_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)

    def drop(header, rows) -> None:
        header.remove("smiles")
        for row in rows:
            del row["smiles"]

    edit_compounds(case, drop)
    with pytest.raises(AssertionError) as raised:
        recheck(case)
    assert str(raised.value) == "compounds.tsv: the compound table has no 'smiles' column"


def test_a_row_with_more_cells_than_the_header_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    with case.compounds.open("a", encoding="utf-8", newline="") as handle:
        handle.write("a\tb\tc\td\te\n")
    with pytest.raises(AssertionError) as raised:
        recheck(case)
    assert str(raised.value) == "compounds.tsv: a row has more cells than the header has columns"


def test_an_empty_table_is_refused(tmp_path) -> None:
    case = make_case(tmp_path)
    case.compounds.write_text("", encoding="utf-8")
    with pytest.raises(AssertionError) as raised:
        recheck(case)
    assert str(raised.value) == "compounds.tsv: the table has no header row"


def test_a_header_with_as_many_commas_as_tabs_is_read_with_tabs(tmp_path) -> None:
    case = make_case(tmp_path)
    lines = case.compounds.read_text(encoding="utf-8").split("\n")
    lines[0] = lines[0].replace("pubchem_cid", "pubchem_cid,x,y,z")  # three tabs, three commas
    case.compounds.write_text("\n".join(lines), encoding="utf-8")
    reseal_inputs(case)
    assert recheck(case)["rows"] == 3


def test_a_log_without_its_optional_columns_still_binds(tmp_path) -> None:
    case = make_case(tmp_path)

    def drop(header, rows) -> None:
        for column in ("compound", "pubchem_cid", "export_kind", "result_url", "job_id"):
            header.remove(column)
            for row in rows:
                del row[column]

    edit_log(case, drop)
    reseal_inputs(case)
    assert recheck(case)["submission_status_counts"] == {"verified_kind_unstated": 3}


def test_a_log_without_the_hash_column_declares_no_hash(tmp_path) -> None:
    case = make_case(tmp_path)

    def drop(header, rows) -> None:
        header.remove("result_sha256")
        for row in rows:
            del row["result_sha256"]

    edit_log(case, drop)
    reseal_inputs(case)
    assert problems(case) == [
        f"log.tsv: {entry(number)} result_sha256: the log does not declare it"
        for number in (1, 2, 3)
    ]


@pytest.mark.parametrize(
    "column,message",
    [
        ("compound_id", "compound_id: '' is empty or repeated"),
        ("structure_id", "structure_id: '' is not a structure id or is repeated"),
        ("inchikey", "inchikey: None is not an InChIKey"),
    ],
)
def test_a_missing_column_of_the_stage_table_is_named(tmp_path, column, message) -> None:
    case = make_case(tmp_path)

    def drop(header, rows) -> None:
        header.remove(column)
        for row in rows:
            del row[column]

    rewrite(case.stage_table(LABEL), drop)
    seal_stage(case, LABEL)
    lines = problems(case)
    for number in (1, 2, 3):
        assert f"{LABEL}: {STAGE}: {entry(number)} {message}" in lines


def test_a_changed_compound_id_in_the_registered_table_is_named(tmp_path) -> None:
    case = make_case(tmp_path)
    edit_registered(case, LABEL, lambda rows: rows[0].__setitem__("compound_id", "CMP0009"))
    assert problems(case) == [
        f"{LABEL}: {REGISTERED}: {entry(1)} compound_id: "
        f"expected 'CMP0001' from {STAGE}, found 'CMP0009'"
    ]


def test_a_missing_file_of_one_threshold_does_not_distort_the_report_of_the_others(
    tmp_path,
) -> None:
    case = make_case(tmp_path, labels=("0.10", "0.05"))
    case.stage_table("0.05").unlink()
    edit_stage(case, "0.10", lambda rows: rows[0].__setitem__("name", "Other"))
    assert problems(case) == [
        f"0.05: {STAGE}: not found in {case.stages['0.05']}",
        f"0.10: {STAGE}: {entry(1)} name: expected 'Compound 1' from the inputs, found 'Other'",
    ]


# --- the command line --------------------
def cli(case, tmp_path, *, with_recheck: bool = True) -> list[str]:
    genes = tmp_path / "disease_genes.txt"
    genes.write_text("CA2\n", encoding="utf-8")
    argv: list[str] = []
    for label, run in case.runs.items():
        argv += ["--run", f"{label}={run}"]
    argv += [
        "--background-dir",
        str(tmp_path / "backgrounds"),
        "--disease-genes",
        str(genes),
        "--hgnc-map",
        str(HGNC),
        "--out",
        str(tmp_path / "independent-check.json"),
    ]
    if with_recheck:
        argv += [
            "--compound-table",
            str(case.compounds),
            "--stp-dir",
            str(case.stp_dir),
            "--log",
            str(case.log),
            "--species",
            case.species,
        ]
        for label, stage in case.stages.items():
            argv += ["--stage", f"{label}={stage}"]
    return argv


def stubbed_main(monkeypatch):
    check = load_check()
    monkeypatch.setattr(
        check, "check_run", lambda label, run, background, disease, mapper: {"stub": label}
    )
    return check


def test_main_writes_the_binding_record_next_to_the_run_checks(tmp_path, monkeypatch) -> None:
    case = make_case(tmp_path / "c", labels=("0.10", "0.05"))
    check = stubbed_main(monkeypatch)
    assert check.main(cli(case, tmp_path)) == 0
    written = json.loads((tmp_path / "independent-check.json").read_text(encoding="utf-8"))
    assert sorted(written) == ["bindings", "disease_sha256", "hgnc_sha256", "runs"]
    assert written["runs"] == {"0.10": {"stub": "0.10"}, "0.05": {"stub": "0.05"}}
    assert written["bindings"] == recheck(case)


def test_main_without_the_recheck_options_writes_the_old_file(tmp_path, monkeypatch) -> None:
    case = make_case(tmp_path / "c", labels=("0.10", "0.05"))
    check = stubbed_main(monkeypatch)
    assert check.main(cli(case, tmp_path, with_recheck=False)) == 0
    written = json.loads((tmp_path / "independent-check.json").read_text(encoding="utf-8"))
    assert sorted(written) == ["disease_sha256", "hgnc_sha256", "runs"]


@pytest.mark.parametrize(
    "dropped",
    [
        ["--compound-table"],
        ["--stp-dir"],
        ["--log"],
        ["--species"],
        ["--stage"],
        ["--log", "--species"],
    ],
)
def test_main_refuses_a_partial_set_of_recheck_options(tmp_path, monkeypatch, dropped) -> None:
    case = make_case(tmp_path / "c", labels=("0.10", "0.05"))
    check = stubbed_main(monkeypatch)
    argv = cli(case, tmp_path)
    for option in dropped:
        while option in argv:
            position = argv.index(option)
            del argv[position : position + 2]
    with pytest.raises(SystemExit) as raised:
        check.main(argv)
    assert str(raised.value) == (
        "the binding recheck needs --compound-table, --stp-dir, --log, --species and --stage "
        f"together; missing: {', '.join(dropped)}"
    )
    assert not (tmp_path / "independent-check.json").exists()


def test_main_refuses_stages_that_do_not_match_the_runs(tmp_path, monkeypatch) -> None:
    case = make_case(tmp_path / "c", labels=("0.10", "0.05"))
    check = stubbed_main(monkeypatch)
    argv = cli(case, tmp_path)
    position = argv.index("--stage")
    del argv[position : position + 2]
    with pytest.raises(SystemExit) as raised:
        check.main(argv)
    assert str(raised.value) == (
        "--run labels ['0.05', '0.10'] and --stage labels ['0.05'] must be the same"
    )


def test_main_writes_nothing_when_a_binding_is_wrong(tmp_path, monkeypatch) -> None:
    case = make_case(tmp_path / "c")
    edit_stage(case, LABEL, lambda rows: rows[1].__setitem__("smiles", "CCCC"))
    check = stubbed_main(monkeypatch)
    with pytest.raises(AssertionError) as raised:
        check.main(cli(case, tmp_path))
    assert str(raised.value) == problems_text(case)
    assert not (tmp_path / "independent-check.json").exists()


def problems_text(case) -> str:
    return "\n".join(problems(case))


def test_the_seal_helpers_keep_a_case_consistent(tmp_path) -> None:
    case = make_case(tmp_path, labels=("0.10", "0.05"))
    edit_stage(
        case, "0.10", lambda rows: rows[0].__setitem__("stereo_status", "undefined"), seal=False
    )
    edit_registered(
        case, "0.10", lambda rows: rows[0].__setitem__("identity_basis", "x"), seal=False
    )
    seal_stage(case, "0.10")
    seal_registered(case, "0.10")
    # the stage table of 0.10 now differs from the one of 0.05 and nothing else is wrong
    assert len(problems(case)) == 1
