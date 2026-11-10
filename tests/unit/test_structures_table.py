"""The compound_structures table, the audit summary, the cross-table checks (docs/upstream.md, 8.5).

The scenario below has one compound for every row status; nothing here needs RDKit.
"""

from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator
from structures_support import (
    LATER,
    NOW,
    STRUCTURES_COLUMNS,
    SUMMARY_FIELDS,
    TOOLKIT_VERSION,
    Describer,
    compound,
    fake_key,
    log_row,
    write_export,
    write_log,
)

from rnp.config import load_schema
from rnp.errors import InputError, SchemaViolation
from rnp.io.tables import read_table
from rnp.structures import (
    STRUCTURES_COLUMNS as PACKAGE_COLUMNS,
)
from rnp.structures import (
    SUMMARY_FIELDS as PACKAGE_SUMMARY_FIELDS,
)
from rnp.structures import (
    Issue,
    LogRow,
    bind_submissions,
    build_name_only_rows,
    build_structure_rows,
    check_issues,
    check_summary,
    check_table,
    collect_issues,
    read_registry,
    read_submission_log,
    register_structures,
    summarize,
    write_registry,
    write_structures_table,
)
from rnp.structures.checks import raise_if_problems

ROW_VALIDATOR = Draft202012Validator(load_schema("compound_structures_row"))
OVERRIDES = {"CCCC": {"stereo_status": "undefined", "stereo_elements_total": 1}}


def pipeline(tmp_path, registry=None, now=NOW):
    """Six compounds, one of every kind; returns everything the later stages work from."""
    stp = tmp_path / "stp"
    digests = {number: write_export(stp, f"c{number}.xlsx") for number in range(1, 8)}
    rows = [
        compound(1, "CCO"),  # verified
        compound(2, "CCN"),  # no log row: not recorded
        compound(3, "CCC"),  # the declared hash is wrong: rejected
        compound(4, ""),  # no structure
        compound(5, "!bad"),  # not a structure
        compound(6, "CCCC"),  # reconstructed, stereo undefined
    ]
    registration = register_structures(
        rows,
        registry or [],
        toolkit_version=TOOLKIT_VERSION,
        now=now,
        describe=Describer(OVERRIDES),
    )
    log = [
        LogRow(1, log_row(1, digests[1])),
        LogRow(2, log_row(3, "0" * 64, submitted_structure="CCC")),
        LogRow(
            3,
            log_row(
                6,
                digests[6],
                submitted_structure="CCCC",
                export_kind="reconstructed_from_result_page",
                job_id="job-1",
                result_rows="30",
            ),
        ),
        LogRow(4, log_row(9, "z" * 64, stp_file="stray.xlsx")),
    ]
    binding = bind_submissions(
        rows, registration.outcomes, log, stp_dir=stp, species="Homo_sapiens"
    )
    table = build_structure_rows(rows, registration, binding)
    issues = collect_issues(registration, binding)
    return rows, registration, binding, table, issues, digests


def expected_table(digests):
    def row(number, name, **fields):
        base = {
            "compound_id": f"CMP{number:04d}",
            "group": "all",
            "name": f"Compound {number}",
            "stp_file": f"c{number}.xlsx",
            "row_status": "accepted",
            "structure_status": "registered",
            "structure_id": "",
            "smiles": "",
            "inchikey": "",
            "stereo_status": "none_present",
            "submission_status": "verified",
            "export_kind": "",
            "export_sha256": "",
            "issue_codes": "",
        }
        base.update(fields)
        if base["smiles"]:
            base["inchikey"] = fake_key(base["smiles"])
        return base

    return [
        row(
            1, "", structure_id="STR0001", smiles="CCO", export_kind="native_export",
            export_sha256=digests[1],
        ),
        row(
            2, "", structure_id="STR0002", smiles="CCN", submission_status="not_recorded",
            issue_codes="submission_record_missing",
        ),
        row(
            3, "", structure_id="STR0003", smiles="CCC", row_status="quarantined",
            submission_status="rejected", export_sha256=digests[3],
            issue_codes="submission_hash_mismatch",
        ),
        row(
            4, "", row_status="quarantined", structure_status="not_registered",
            stereo_status="", submission_status="not_checked", issue_codes="missing_structure",
        ),
        row(
            5, "", row_status="quarantined", structure_status="not_registered",
            stereo_status="", submission_status="not_checked", issue_codes="invalid_smiles",
        ),
        row(
            6, "", structure_id="STR0004", smiles="CCCC", stereo_status="undefined",
            submission_status="reconstructed", export_kind="reconstructed_from_result_page",
            export_sha256=digests[6],
            issue_codes="stereo_undefined;submission_export_reconstructed",
        ),
    ]  # fmt: skip


def view(issue):
    return (issue.source, issue.row, issue.level, issue.code, issue.compound_id)


def test_the_columns_are_the_schema_columns():
    assert STRUCTURES_COLUMNS == PACKAGE_COLUMNS
    assert SUMMARY_FIELDS == PACKAGE_SUMMARY_FIELDS
    assert list(load_schema("compound_structures_row")["properties"]) == STRUCTURES_COLUMNS


# --- the rows -------------------------------------------------------------------------------------
def test_every_kind_of_row_is_built_as_documented(tmp_path):
    _, _, _, table, _, digests = pipeline(tmp_path)
    assert table == expected_table(digests)


def test_every_row_has_the_columns_in_order_and_fits_the_schema(tmp_path):
    _, _, _, table, _, _ = pipeline(tmp_path)
    for row in table:
        assert list(row) == STRUCTURES_COLUMNS
        assert [e.message for e in ROW_VALIDATOR.iter_errors(row)] == []


def test_the_rows_keep_the_input_order(tmp_path):
    rows, _, _, table, _, _ = pipeline(tmp_path)
    assert [r["compound_id"] for r in table] == [item.compound_id for item in rows]


def test_issue_codes_are_sorted_unique_and_leave_out_strays(tmp_path):
    _, _, _, table, _, _ = pipeline(tmp_path)
    for row in table:
        codes = row["issue_codes"].split(";") if row["issue_codes"] else []
        assert codes == sorted(set(codes))
        assert "log_row_without_compound" not in codes


def test_a_structure_that_is_in_the_registry_but_a_rejected_submission_is_quarantined(tmp_path):
    _, _, _, table, _, digests = pipeline(tmp_path)
    rejected = table[2]
    assert rejected["row_status"] == "quarantined"
    assert rejected["structure_status"] == "registered" and rejected["structure_id"] == "STR0003"
    assert rejected["submission_status"] == "rejected" and rejected["export_sha256"] == digests[3]


def test_name_mode_rows_carry_no_structure_and_no_submission():
    rows = [compound(1, "CCO"), compound(2, "this is ignored", group="Group B", stp_file="")]
    table = build_name_only_rows(rows)
    assert table == [
        {
            "compound_id": "CMP0001",
            "group": "all",
            "name": "Compound 1",
            "stp_file": "c1.xlsx",
            "row_status": "name_only",
            "structure_status": "name_only",
            "structure_id": "",
            "smiles": "",
            "inchikey": "",
            "stereo_status": "",
            "submission_status": "not_applicable",
            "export_kind": "",
            "export_sha256": "",
            "issue_codes": "",
        },
        {
            "compound_id": "CMP0002",
            "group": "Group B",
            "name": "Compound 2",
            "stp_file": "",
            "row_status": "name_only",
            "structure_status": "name_only",
            "structure_id": "",
            "smiles": "",
            "inchikey": "",
            "stereo_status": "",
            "submission_status": "not_applicable",
            "export_kind": "",
            "export_sha256": "",
            "issue_codes": "",
        },
    ]
    assert all(not list(ROW_VALIDATOR.iter_errors(row)) for row in table)
    assert build_name_only_rows([]) == []


def test_a_row_that_does_not_fit_the_schema_is_an_internal_error():
    with pytest.raises(SchemaViolation) as caught:
        build_name_only_rows([compound(1, "CCO", name="")])
    assert caught.value.exit_code == 1


def test_a_structure_that_does_not_fit_the_schema_is_an_internal_error(tmp_path):
    rows, registration, binding, _, _, _ = pipeline(tmp_path)
    registration.outcomes[0].structure["inchikey"] = "bad"
    with pytest.raises(SchemaViolation):
        build_structure_rows(rows, registration, binding)


def test_the_parts_must_line_up(tmp_path):
    rows, registration, binding, _, _, _ = pipeline(tmp_path)
    with pytest.raises(ValueError):
        build_structure_rows(rows[:-1], registration, binding)
    registration.outcomes.pop()
    with pytest.raises(ValueError):
        build_structure_rows(rows, registration, binding)


# --- the issues and the summary -------------------------------------------------------------------
def test_all_issues_of_a_run_in_the_audit_order(tmp_path):
    _, _, _, _, issues, _ = pipeline(tmp_path)
    assert [view(i) for i in issues] == [
        ("compounds", 2, "warning", "submission_record_missing", "CMP0002"),
        ("compounds", 4, "error", "missing_structure", "CMP0004"),
        ("compounds", 5, "error", "invalid_smiles", "CMP0005"),
        ("compounds", 6, "warning", "stereo_undefined", "CMP0006"),
        ("submission_log", 2, "error", "submission_hash_mismatch", "CMP0003"),
        ("submission_log", 3, "warning", "submission_export_reconstructed", "CMP0006"),
        ("submission_log", 4, "warning", "log_row_without_compound", ""),
    ]


def test_the_summary_counts(tmp_path):
    _, registration, _, table, issues, _ = pipeline(tmp_path)
    summary = summarize(table, registration, issues)
    assert list(summary) == SUMMARY_FIELDS
    assert summary == {
        "rows": 6,
        "rows_accepted": 3,
        "rows_quarantined": 3,
        "rows_name_only": 0,
        "structures_new": 4,
        "structures_reused": 0,
        "structures_superseded": 0,
        "submissions_verified": 1,
        "submissions_reconstructed": 1,
        "submissions_not_recorded": 1,
        "submissions_rejected": 1,
        "errors": 3,
        "warnings": 4,
    }


def test_the_summary_counts_a_kind_unstated_export_as_verified(tmp_path):
    table = [
        {"row_status": "accepted", "submission_status": "verified"},
        {"row_status": "accepted", "submission_status": "verified_kind_unstated"},
        {"row_status": "quarantined", "submission_status": "not_checked"},
    ]
    summary = summarize(table, None, [])
    assert summary["submissions_verified"] == 2
    assert (
        summary["rows"] == 3 and summary["rows_accepted"] == 2 and summary["rows_quarantined"] == 1
    )


def test_the_summary_of_a_name_mode_run():
    rows = [compound(1, "CCO"), compound(2, "CCN")]
    summary = summarize(build_name_only_rows(rows), None, [])
    assert list(summary) == SUMMARY_FIELDS
    assert summary["rows"] == 2 and summary["rows_name_only"] == 2
    assert all(
        value == 0 for name, value in summary.items() if name not in ("rows", "rows_name_only")
    )


def test_a_second_run_reuses_the_registered_structures(tmp_path):
    first = pipeline(tmp_path / "one")
    second = pipeline(tmp_path / "two", registry=first[1].registry, now=LATER)
    _, registration, _, table, issues, digests = second
    assert (registration.new, registration.reused, registration.superseded) == (0, 4, 0)
    assert table == expected_table(digests)
    assert summarize(table, registration, issues)["structures_reused"] == 4
    assert [r["structure_id"] for r in registration.registry] == [
        "STR0001",
        "STR0002",
        "STR0003",
        "STR0004",
    ]
    assert {r["last_seen_utc"] for r in registration.registry} == {LATER}


def test_the_same_inputs_give_the_same_outputs(tmp_path):
    one = pipeline(tmp_path / "one")
    two = pipeline(tmp_path / "two")
    assert one[3] == two[3]
    assert [view(i) for i in one[4]] == [view(i) for i in two[4]]
    assert one[1].registry == two[1].registry


# --- writing the table ----------------------------------------------------------------------------
def test_the_table_file_is_tab_separated_lf_with_the_columns_in_order(tmp_path):
    _, _, _, table, _, _ = pipeline(tmp_path)
    path = tmp_path / "out" / "compound_structures.tsv"
    write_structures_table(path, table)
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    lines = raw.decode("utf-8").splitlines()
    assert lines[0] == "\t".join(STRUCTURES_COLUMNS)
    assert len(lines) == 1 + len(table)
    assert read_table(path) == table
    assert sorted(p.name for p in path.parent.iterdir()) == ["compound_structures.tsv"]


def test_an_empty_table_is_just_the_header(tmp_path):
    write_structures_table(tmp_path / "t.tsv", [])
    assert (tmp_path / "t.tsv").read_text(encoding="utf-8") == "\t".join(STRUCTURES_COLUMNS) + "\n"


def test_a_row_that_does_not_fit_is_never_written(tmp_path):
    _, _, _, table, _, _ = pipeline(tmp_path)
    table[0]["row_status"] = "perhaps"
    with pytest.raises(SchemaViolation):
        write_structures_table(tmp_path / "t.tsv", table)
    assert not (tmp_path / "t.tsv").exists()


# --- the checks -----------------------------------------------------------------------------------
def test_a_consistent_run_has_no_problems(tmp_path):
    rows, registration, _, table, issues, _ = pipeline(tmp_path)
    assert check_table(table, registration.registry, rows) == []
    summary = summarize(table, registration, issues)
    errors = sum(1 for i in issues if i.level == "error")
    assert check_summary(summary, table, errors, len(issues) - errors) == []


def tampered(tmp_path, change):
    rows, registration, _, table, _, _ = pipeline(tmp_path)
    table = copy.deepcopy(table)
    registry = copy.deepcopy(registration.registry)
    change(table, registry)
    return check_table(table, registry, rows)


def test_a_missing_table_row_is_found(tmp_path):
    problems = tampered(tmp_path, lambda table, registry: table.pop())
    assert any("5 table rows for 6 input rows" in p for p in problems)


def test_a_reordered_table_is_found(tmp_path):
    def swap(table, registry):
        table[0], table[1] = table[1], table[0]

    problems = tampered(tmp_path, swap)
    assert any("row 1" in p and "CMP0002" in p for p in problems)


def test_a_structure_id_that_is_not_in_the_registry_is_found(tmp_path):
    problems = tampered(tmp_path, lambda table, registry: registry.pop(0))
    assert any("STR0001 is not in the registry" in p for p in problems)


def test_a_structure_of_another_compound_is_found(tmp_path):
    problems = tampered(tmp_path, lambda table, registry: table[0].update(structure_id="STR0002"))
    assert any("STR0002 belongs to CMP0002" in p for p in problems)


def test_a_structure_that_is_no_longer_current_is_found(tmp_path):
    def retire(table, registry):
        registry[0].update(status="superseded", superseded_by="STR0004")

    problems = tampered(tmp_path, retire)
    assert any("STR0001 is not the current structure" in p for p in problems)


@pytest.mark.parametrize("column", ["smiles", "inchikey", "stereo_status"])
def test_a_column_that_differs_from_the_registry_is_found(tmp_path, column):
    other = {"smiles": "CCCCC", "inchikey": fake_key("zzz"), "stereo_status": "defined"}[column]
    problems = tampered(tmp_path, lambda table, registry: table[0].update({column: other}))
    assert any(f"{column} differs from the registry" in p for p in problems)


def test_unsorted_or_repeated_issue_codes_are_found(tmp_path):
    def unsort(table, registry):
        table[5]["issue_codes"] = "submission_export_reconstructed;stereo_undefined"

    def repeat(table, registry):
        table[5]["issue_codes"] = "stereo_undefined;stereo_undefined"

    for change in (unsort, repeat):
        assert any(
            "not sorted and unique" in p for p in tampered(tmp_path / change.__name__, change)
        )


def test_the_summary_is_checked_against_the_table(tmp_path):
    rows, registration, _, table, issues, _ = pipeline(tmp_path)
    summary = summarize(table, registration, issues)
    errors = sum(1 for i in issues if i.level == "error")
    warnings = len(issues) - errors
    counted = [
        "rows",
        "rows_accepted",
        "rows_quarantined",
        "rows_name_only",
        "submissions_verified",
        "submissions_reconstructed",
        "submissions_not_recorded",
        "submissions_rejected",
    ]
    for name in counted:
        wrong = dict(summary, **{name: summary[name] + 1})
        problems = check_summary(wrong, table, errors, warnings)
        assert len(problems) == 1 and name in problems[0], (name, problems)
    assert any("summary.errors" in p for p in check_summary(summary, table, errors + 1, warnings))
    assert any("summary.warnings" in p for p in check_summary(summary, table, errors, warnings + 1))
    assert check_summary({}, table, errors, warnings)


def test_the_summary_check_covers_name_mode_and_the_unstated_export_kind():
    name_rows = build_name_only_rows([compound(1, "CCO"), compound(2, "CCN")])
    summary = summarize(name_rows, None, [])
    assert check_summary(summary, name_rows, 0, 0) == []
    problems = check_summary(dict(summary, rows_name_only=1), name_rows, 0, 0)
    assert len(problems) == 1 and "rows_name_only" in problems[0]
    table = [
        {"row_status": "accepted", "submission_status": "verified"},
        {"row_status": "accepted", "submission_status": "verified_kind_unstated"},
        {"row_status": "quarantined", "submission_status": "not_checked"},
    ]
    assert check_summary(summarize(table, None, []), table, 0, 0) == []


def test_the_issues_of_a_consistent_run_agree_with_the_table(tmp_path):
    rows, _, _, table, issues, _ = pipeline(tmp_path)
    assert check_issues(table, issues) == []
    assert check_issues(build_name_only_rows(rows), []) == []


def test_an_issue_for_a_compound_without_a_row_is_found(tmp_path):
    _, _, _, table, issues, _ = pipeline(tmp_path)
    stray = Issue("warning", "multi_fragment", "compounds", 9, "CMP0099", "stray")
    problems = check_issues(table, [*issues, stray])
    assert len(problems) == 1 and "CMP0099" in problems[0] and "no table row" in problems[0]


def test_issue_codes_that_the_issues_do_not_explain_are_found(tmp_path):
    _, _, _, table, issues, _ = pipeline(tmp_path)
    kept = [issue for issue in issues if issue.code != "stereo_undefined"]
    problems = check_issues(table, kept)
    assert len(problems) == 1 and problems[0].startswith("row 6 (CMP0006): ")
    assert "issue_codes" in problems[0] and "stereo_undefined" in problems[0]
    extra = Issue("warning", "multi_fragment", "compounds", 1, "CMP0001", "2 fragments")
    problems = check_issues(table, [*issues, extra])
    assert len(problems) == 1 and problems[0].startswith("row 1 (CMP0001): ")
    assert "multi_fragment" in problems[0]


def test_a_quarantined_row_needs_an_error_and_an_error_needs_a_quarantined_row(tmp_path):
    _, _, _, table, issues, _ = pipeline(tmp_path)

    def with_level(code, level):
        return [
            Issue(level, i.code, i.source, i.row, i.compound_id, i.message) if i.code == code else i
            for i in issues
        ]

    problems = check_issues(table, with_level("submission_hash_mismatch", "warning"))
    assert len(problems) == 1 and problems[0].startswith("row 3 (CMP0003): ")
    assert "quarantined" in problems[0]
    problems = check_issues(table, with_level("stereo_undefined", "error"))
    assert len(problems) == 1 and problems[0].startswith("row 6 (CMP0006): ")
    assert "error" in problems[0] and "accepted" in problems[0]


def test_raise_if_problems():
    raise_if_problems([], "all fine")
    with pytest.raises(InputError) as caught:
        raise_if_problems(["one", "two"], "not consistent")
    assert caught.value.message == "not consistent" and caught.value.details == ["one", "two"]
    assert caught.value.exit_code == 2


# --- the whole flow through files -----------------------------------------------------------------
def test_the_library_flow_through_files(tmp_path):
    stp = tmp_path / "stp"
    digest = write_export(stp, "c1.xlsx")
    log_path = write_log(
        tmp_path / "log.tsv",
        [log_row(1, digest), log_row(2, "0" * 64, submitted_structure="CCN")],
    )
    rows = [compound(1, "CCO"), compound(2, "CCN"), compound(3, "")]
    registry_path = tmp_path / "registry" / "structure_registry.tsv"

    def run_once(now, tag):
        registry = read_registry(registry_path)
        registration = register_structures(
            rows, registry, toolkit_version=TOOLKIT_VERSION, now=now, describe=Describer()
        )
        binding = bind_submissions(
            rows,
            registration.outcomes,
            read_submission_log(log_path),
            stp_dir=stp,
            species="Homo_sapiens",
        )
        table = build_structure_rows(rows, registration, binding)
        issues = collect_issues(registration, binding)
        summary = summarize(table, registration, issues)
        errors = sum(1 for i in issues if i.level == "error")
        assert check_table(table, registration.registry, rows) == []
        assert check_summary(summary, table, errors, len(issues) - errors) == []
        write_registry(registry_path, registration.registry)
        write_structures_table(tmp_path / f"table-{tag}.tsv", table)
        return registration, table, summary

    first = run_once(NOW, "first")
    second = run_once(LATER, "second")
    assert (first[0].new, first[0].reused) == (2, 0)
    assert (second[0].new, second[0].reused) == (0, 2)
    assert first[1] == second[1]
    assert first[2]["rows_accepted"] == 1 and first[2]["rows_quarantined"] == 2
    again = read_registry(registry_path)
    assert [r["last_seen_utc"] for r in again] == [LATER, LATER]
    assert [r["first_seen_utc"] for r in again] == [NOW, NOW]
