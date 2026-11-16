"""The selection library `rnp.selection`: the decision table, the derivation, ids and checks.

Nothing here needs RDKit, R or the network. The compounds stage is replaced by hand-made rows.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import re
import subprocess
import sys

import pytest
from selection_support import COLUMNS, decision, write_decisions

from rnp.errors import InputError
from rnp.selection import (
    DECISION_VALUES,
    INPUT_OPTIONAL,
    INPUT_REQUIRED,
    ISSUE_CODES,
    ROW_ISSUE_CODES,
    RULE_VERSION,
    SELECTION_COLUMNS,
    STATUS_VALUES,
    SUMMARY_COUNTS,
    DecisionRow,
    Decisions,
    SelectionIssue,
    canonical_codes,
    check_selection,
    decision_id,
    derive_selection,
    read_decisions,
    row_issue_codes,
    selected_rows,
    status_for,
    summarize,
    write_selection_table,
)


def read(tmp_path, rows, columns=None, **kwargs):
    return read_decisions(write_decisions(tmp_path / "d.tsv", rows, columns, **kwargs))


def read_text(tmp_path, text):
    path = tmp_path / "d.tsv"
    path.write_text(text, encoding="utf-8", newline="")
    return read_decisions(path).rows


def refused(tmp_path, rows=None, columns=None, text=None, **kwargs) -> InputError:
    path = tmp_path / "d.tsv"
    if text is None:
        write_decisions(path, rows, columns, **kwargs)
    else:
        path.write_text(text, encoding="utf-8", newline="")
    with pytest.raises(InputError) as caught:
        read_decisions(path)
    return caught.value


# --- the constants ----------------------------------------------------------------------------
def test_the_vocabularies_are_the_documented_ones():
    assert RULE_VERSION == "v0.2.0-selection-rules"
    assert DECISION_VALUES == ("include", "exclude", "needs_review")
    assert STATUS_VALUES == ("selected", "excluded", "needs_review", "quarantined")
    assert ROW_ISSUE_CODES == (
        "no_decision_recorded",
        "include_blocked_by_quarantine",
        "quarantine_resolved_by_exclusion",
    )
    assert ISSUE_CODES == (*ROW_ISSUE_CODES, "decision_without_compound", "no_compound_selected")
    assert INPUT_REQUIRED == ("compound", "decision", "reason_codes", "rules_version", "reviewer")
    assert INPUT_OPTIONAL == ("group", "evidence_refs")
    assert SUMMARY_COUNTS == (
        "candidates",
        "selected",
        "excluded",
        "needs_review",
        "quarantined",
        "decisions_recorded",
        "decisions_not_recorded",
        "decisions_without_compound",
        "warnings",
    )
    assert SELECTION_COLUMNS == [
        "decision_id",
        "compound_id",
        "group",
        "name",
        "stp_file",
        "structure_id",
        "compound_row_status",
        "decision",
        "decision_source",
        "selection_status",
        "reason_codes",
        "rules_version",
        "reviewer",
        "evidence_refs",
        "issue_codes",
    ]


def test_the_library_needs_no_rdkit():
    code = "import sys; sys.modules['rdkit'] = None; import rnp.selection; print('ok')"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


# --- reading the decision table ----------------------------------------------------------------
def test_a_table_is_read_and_cleaned(tmp_path):
    table = read(
        tmp_path,
        [
            decision("Quercetin", "include"),
            decision("Kaempferol", "exclude", reason="b_code;a_code;b_code", refs="PMID 1"),
        ],
    )
    assert table.path == tmp_path / "d.tsv"
    assert table.extra_columns == []
    first, second = table.rows
    assert first == DecisionRow(1, "Quercetin", "all", "include", "", "RA-v1", "Researcher", "")
    assert second == DecisionRow(
        2, "Kaempferol", "all", "exclude", "a_code;b_code", "RA-v1", "Researcher", "PMID 1"
    )
    assert first.key == ("quercetin", "all")


def test_the_cells_are_cleaned_before_they_are_checked(tmp_path):
    messy = decision(
        "  Quercetin   3-O-glucoside ",
        " include ",
        group="  g   1 ",
        reason="  ",
        rules="RA  v1 ",
        reviewer=" Dr   Li ",
        refs="  PMID   1 ",
    )
    row = read(tmp_path, [messy]).rows[0]
    assert (row.compound, row.group, row.decision, row.reason_codes) == (
        "Quercetin 3-O-glucoside",
        "g 1",
        "include",
        "",
    )
    assert (row.rules_version, row.reviewer, row.evidence_refs) == ("RA v1", "Dr Li", "PMID 1")
    assert row.key == ("quercetin3oglucoside", "g 1")


def test_the_optional_columns_may_be_missing_or_empty(tmp_path):
    required_only = [column for column in COLUMNS if column not in ("group", "evidence_refs")]
    row = read(tmp_path, [decision("Quercetin", "include")], required_only).rows[0]
    assert (row.group, row.evidence_refs) == ("all", "")
    empty = read(tmp_path, [decision("Quercetin", "include", group="")]).rows[0]
    assert empty.group == "all"


def test_the_decision_and_the_codes_are_stripped_of_the_spaces_around_them(tmp_path):
    row = read(tmp_path, [decision("Q", " exclude ", reason=" b_code;a_code ")]).rows[0]
    assert (row.decision, row.reason_codes) == ("exclude", "a_code;b_code")


def test_the_codes_are_sorted_without_repeats(tmp_path):
    row = read(tmp_path, [decision("Q", "exclude", reason="zeta;alpha;zeta;mid_2")]).rows[0]
    assert row.reason_codes == "alpha;mid_2;zeta"
    assert canonical_codes("") == ""
    assert canonical_codes("b;a;b") == "a;b"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"delimiter": ","},
        {"encoding": "utf-8-sig"},
        {"newline": "\r\n"},
    ],
    ids=["comma", "bom", "crlf"],
)
def test_the_table_may_be_comma_separated_have_a_bom_or_crlf(tmp_path, kwargs):
    row = read(tmp_path, [decision("Quercetin", "include")], **kwargs).rows[0]
    assert (row.compound, row.decision, row.rules_version) == ("Quercetin", "include", "RA-v1")


def test_blank_rows_are_skipped_and_the_row_numbers_count_the_others(tmp_path):
    header = "\t".join(COLUMNS)
    line = "\tall\tinclude\t\tRA-v1\tR\t"
    text = f"{header}\nA{line}\n\t\t\t\t\t\t\nB{line}\n\nC{line}\n"
    rows = read_text(tmp_path, text)
    assert [(row.row, row.compound) for row in rows] == [(1, "A"), (2, "B"), (3, "C")]


def test_unknown_columns_are_ignored_and_listed_in_header_order(tmp_path):
    columns = ["note", *COLUMNS, "ADMET"]
    table = read(tmp_path, [decision("Q", "include", note="x", ADMET="y")], columns)
    assert table.extra_columns == ["note", "ADMET"]
    assert table.rows[0] == DecisionRow(1, "Q", "all", "include", "", "RA-v1", "Researcher", "")


@pytest.mark.parametrize(
    ("drop", "listed"),
    [
        (["decision"], "decision"),
        (["reviewer", "compound"], "compound, reviewer"),
        (["rules_version", "reason_codes", "decision"], "decision, reason_codes, rules_version"),
    ],
)
def test_missing_required_columns_are_listed_in_the_documented_order(tmp_path, drop, listed):
    columns = [column for column in COLUMNS if column not in drop]
    error = refused(tmp_path, [decision("Q", "include")], columns)
    assert error.message == "d.tsv: the selection table lacks required column(s)"
    assert error.details == [listed]


def test_a_table_without_rows_is_refused(tmp_path):
    error = refused(tmp_path, [])
    assert error.message == "d.tsv: the selection table has no decisions"
    assert error.details == []


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("decision", "Include"),
        ("decision", "maybe"),
        ("decision", ""),
        ("decision", "include;exclude"),
        ("reason_codes", "Upper"),
        ("reason_codes", "9lives"),
        ("reason_codes", "a b"),
        ("reason_codes", "a;;b"),
        ("reason_codes", ";a"),
        ("reason_codes", "a;"),
        ("reason_codes", "a-b"),
        ("reason_codes", "a; b"),
        ("compound", ""),
        ("rules_version", ""),
        ("reviewer", ""),
    ],
)
def test_a_cell_that_breaks_the_schema_is_refused_with_its_row_and_column(tmp_path, column, value):
    good = decision("Quercetin", "include")
    bad = {**decision("Kaempferol", "include"), column: value}
    error = refused(tmp_path, [good, bad])
    assert error.message == "d.tsv: the selection table has invalid rows"
    assert error.details
    assert all(item.startswith("row 2: ") for item in error.details)
    assert any(item.startswith(f"row 2: {column}:") for item in error.details)


@pytest.mark.parametrize("value", ["exclude", "needs_review"])
def test_exclude_and_needs_review_need_a_reason_code(tmp_path, value):
    error = refused(tmp_path, [decision("Quercetin", value)])
    assert error.message == "d.tsv: the selection table has invalid rows"
    assert [item.split(":")[0] for item in error.details] == ["row 1"]
    assert "reason_codes" in error.details[0]


def test_every_problem_of_every_row_is_reported_in_one_error(tmp_path):
    error = refused(
        tmp_path,
        [decision("A", "maybe"), decision("B", "include"), decision("C", "exclude", reviewer="")],
    )
    assert [item.split(":")[0] for item in error.details] == ["row 1", "row 3", "row 3"]


def test_one_compound_decided_twice_is_refused_even_when_the_names_differ_in_case_or_marks(
    tmp_path,
):
    error = refused(
        tmp_path,
        [
            decision("Quercetin", "include"),
            decision("Kaempferol", "include"),
            decision("quercetin ", "include"),
            decision("Kaempferol", "include", group="other"),
            decision("KAEMPFEROL", "include", group="other"),
            decision("Quer-cetin", "include"),
        ],
    )
    assert error.message == "d.tsv: the selection table decides the same compound more than once"
    assert error.details == [
        "Quercetin (group all): rows 1, 3, 6",
        "Kaempferol (group other): rows 4, 5",
    ]


def test_the_duplicates_are_listed_in_the_order_of_their_first_rows(tmp_path):
    rows = [
        decision("A", "include", group="g1"),
        decision("B", "include", group="g2"),
        decision("B", "include", group="g2"),
        *[decision(f"Other {n}", "include") for n in range(4, 10)],
        decision("A", "include", group="g1"),
    ]
    error = refused(tmp_path, rows)
    assert error.details == ["A (group g1): rows 1, 10", "B (group g2): rows 2, 3"]


def test_the_same_name_in_two_groups_is_two_decisions(tmp_path):
    table = read(
        tmp_path,
        [decision("Q", "include", group="g1"), decision("Q", "exclude", reason="x", group="g2")],
    )
    assert [row.key for row in table.rows] == [("q", "g1"), ("q", "g2")]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "d.tsv: table has no header row"),
        ("\n\n", "d.tsv: table has no header row"),
        ("compound\tcompound\tdecision\n", "d.tsv: the header repeats a column name"),
        (
            "compound\tdecision\treason_codes\trules_version\treviewer\nA\tinclude\t\tv\tr\textra\n",
            "d.tsv: some rows have more cells than the header",
        ),
    ],
)
def test_a_table_that_cannot_be_read_is_refused(tmp_path, text, message):
    assert refused(tmp_path, text=text).message == message


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(InputError) as caught:
        read_decisions(tmp_path / "nowhere.tsv")
    assert caught.value.message == f"table not found: {tmp_path / 'nowhere.tsv'}"


def test_the_value_objects_are_frozen(tmp_path):
    table = read(tmp_path, [decision("Q", "include")])
    result = derive_selection([stage_row(1)], table)
    for value, name in (
        (table, "rows"),
        (table.rows[0], "decision"),
        (result, "rows"),
        (result.issues[0] if result.issues else SelectionIssue("x", "y", 1, "", "m"), "code"),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(value, name, "changed")


# --- the decision id ---------------------------------------------------------------------------
FIELDS = {
    "compound_id": "CMP0001",
    "structure_id": "STR0001",
    "decision": "include",
    "decision_source": "recorded",
    "reason_codes": "",
    "rules_version": "RA-v1",
    "reviewer": "Researcher",
    "evidence_refs": "",
}


def test_the_decision_id_is_the_first_12_hex_digits_of_the_hash_of_the_joined_fields():
    joined = "\x1f".join(FIELDS.values()).encode("utf-8")
    assert decision_id(**FIELDS) == "DEC-" + hashlib.sha256(joined).hexdigest()[:12]
    assert decision_id(**FIELDS) == "DEC-7ef4b5cc1654"


@pytest.mark.parametrize("field", list(FIELDS))
def test_a_change_of_any_field_gives_a_new_id(field):
    assert decision_id(**{**FIELDS, field: FIELDS[field] + "x"}) != decision_id(**FIELDS)


def test_fields_cannot_run_into_each_other():
    left = decision_id(**{**FIELDS, "reviewer": "a", "evidence_refs": "bc"})
    right = decision_id(**{**FIELDS, "reviewer": "ab", "evidence_refs": "c"})
    assert left != right


def test_ids_are_well_formed_and_text_is_hashed_as_utf8():
    value = decision_id(**{**FIELDS, "reviewer": "李 Wei"})
    assert re.fullmatch(r"DEC-[0-9a-f]{12}", value)
    joined = "\x1f".join({**FIELDS, "reviewer": "李 Wei"}.values()).encode("utf-8")
    assert value == "DEC-" + hashlib.sha256(joined).hexdigest()[:12]


# --- the status and issue tables ----------------------------------------------------------------
STATUS = [
    ("accepted", "include", "selected"),
    ("accepted", "exclude", "excluded"),
    ("accepted", "needs_review", "needs_review"),
    ("accepted", None, "needs_review"),
    ("name_only", "include", "selected"),
    ("name_only", "exclude", "excluded"),
    ("name_only", "needs_review", "needs_review"),
    ("name_only", None, "needs_review"),
    ("quarantined", "include", "quarantined"),
    ("quarantined", "exclude", "excluded"),
    ("quarantined", "needs_review", "quarantined"),
    ("quarantined", None, "quarantined"),
]
CODES = {
    ("accepted", "include"): [],
    ("accepted", "exclude"): [],
    ("accepted", "needs_review"): [],
    ("accepted", None): ["no_decision_recorded"],
    ("name_only", "include"): [],
    ("name_only", "exclude"): [],
    ("name_only", "needs_review"): [],
    ("name_only", None): ["no_decision_recorded"],
    ("quarantined", "include"): ["include_blocked_by_quarantine"],
    ("quarantined", "exclude"): ["quarantine_resolved_by_exclusion"],
    ("quarantined", "needs_review"): [],
    ("quarantined", None): ["no_decision_recorded"],
}


@pytest.mark.parametrize(("row_status", "value", "status"), STATUS)
def test_the_status_of_a_candidate(row_status, value, status):
    assert status_for(row_status, value) == status


@pytest.mark.parametrize(("key", "codes"), list(CODES.items()))
def test_the_issue_codes_of_a_candidate(key, codes):
    assert row_issue_codes(*key) == codes


# --- the derivation ----------------------------------------------------------------------------
def stage_row(number, row_status="accepted", group="all", name=None):
    return {
        "compound_id": f"CMP{number:04d}",
        "group": group,
        "name": name or f"Compound {number}",
        "stp_file": f"c{number}.csv",
        "row_status": row_status,
        "structure_status": {
            "accepted": "registered",
            "name_only": "name_only",
            "quarantined": "not_registered",
        }[row_status],
        "structure_id": f"STR{number:04d}" if row_status == "accepted" else "",
        "smiles": "",
        "inchikey": "",
        "stereo_status": "",
        "submission_status": "not_applicable",
        "export_kind": "",
        "export_sha256": "",
        "issue_codes": "",
    }


def decisions_of(*rows, extra=()):
    return Decisions(path=None, rows=list(rows), extra_columns=list(extra))


def entry(
    row, compound, value, *, group="all", reason="", rules="RA-v1", who="Researcher", refs=""
):
    return DecisionRow(row, compound, group, value, reason, rules, who, refs)


def test_every_candidate_gets_a_row_in_the_order_of_the_stage():
    stage = [stage_row(1), stage_row(2, "quarantined"), stage_row(3), stage_row(4)]
    result = derive_selection(
        stage,
        decisions_of(
            entry(1, "Compound 3", "exclude", reason="no_fit", refs="PMID 7"),
            entry(2, "Compound 1", "include"),
            entry(3, "Compound 2", "include"),
        ),
    )
    rows = result.rows
    assert [row["compound_id"] for row in rows] == ["CMP0001", "CMP0002", "CMP0003", "CMP0004"]
    assert all(list(row) == SELECTION_COLUMNS for row in rows)
    assert [row["selection_status"] for row in rows] == [
        "selected",
        "quarantined",
        "excluded",
        "needs_review",
    ]
    assert [row["decision_source"] for row in rows] == ["recorded"] * 3 + ["not_recorded"]
    third = rows[2]
    assert (third["decision"], third["reason_codes"], third["evidence_refs"]) == (
        "exclude",
        "no_fit",
        "PMID 7",
    )
    assert (third["rules_version"], third["reviewer"]) == ("RA-v1", "Researcher")
    assert (third["name"], third["stp_file"], third["group"]) == ("Compound 3", "c3.csv", "all")
    assert (rows[0]["structure_id"], rows[1]["compound_row_status"]) == ("STR0001", "quarantined")
    generated = rows[3]
    assert generated["decision"] == "needs_review"
    assert [
        generated[key] for key in ("reason_codes", "rules_version", "reviewer", "evidence_refs")
    ] == [""] * 4
    for row in rows:
        assert row["decision_id"] == decision_id(
            compound_id=row["compound_id"],
            structure_id=row["structure_id"],
            decision=row["decision"],
            decision_source=row["decision_source"],
            reason_codes=row["reason_codes"],
            rules_version=row["rules_version"],
            reviewer=row["reviewer"],
            evidence_refs=row["evidence_refs"],
        )


def test_the_issue_codes_are_listed_in_the_rows_and_as_issues():
    stage = [
        stage_row(1, "quarantined"),
        stage_row(2, "quarantined"),
        stage_row(3, "accepted"),
        stage_row(4, "quarantined"),
    ]
    result = derive_selection(
        stage,
        decisions_of(
            entry(1, "Compound 1", "include"),
            entry(2, "Compound 2", "exclude", reason="r"),
            entry(3, "Ghost", "include", group="g9"),
        ),
    )
    assert [row["issue_codes"] for row in result.rows] == [
        "include_blocked_by_quarantine",
        "quarantine_resolved_by_exclusion",
        "no_decision_recorded",
        "no_decision_recorded",
    ]
    assert [issue.as_dict() for issue in result.issues] == [
        {
            "level": "warning",
            "code": "include_blocked_by_quarantine",
            "source": "compounds",
            "row": 1,
            "compound_id": "CMP0001",
            "message": "'Compound 1' (group 'all') is decided include, but the compounds stage "
            "quarantined it, so it is not selected",
        },
        {
            "level": "warning",
            "code": "quarantine_resolved_by_exclusion",
            "source": "compounds",
            "row": 2,
            "compound_id": "CMP0002",
            "message": "'Compound 2' (group 'all') was quarantined by the compounds stage and "
            "is decided exclude: the exclusion stands",
        },
        {
            "level": "warning",
            "code": "no_decision_recorded",
            "source": "compounds",
            "row": 3,
            "compound_id": "CMP0003",
            "message": "no decision is recorded for 'Compound 3' (group 'all'); "
            "it is held for review",
        },
        {
            "level": "warning",
            "code": "no_decision_recorded",
            "source": "compounds",
            "row": 4,
            "compound_id": "CMP0004",
            "message": "no decision is recorded for 'Compound 4' (group 'all'); "
            "it is held for review",
        },
        {
            "level": "warning",
            "code": "decision_without_compound",
            "source": "selection",
            "row": 3,
            "compound_id": "",
            "message": "decision row 3 names 'Ghost' (group 'g9'), which is not a candidate of "
            "this run",
        },
        {
            "level": "warning",
            "code": "no_compound_selected",
            "source": "selection",
            "row": None,
            "compound_id": "",
            "message": "no compound is selected",
        },
    ]


def test_a_decision_is_matched_by_the_name_key_and_the_exact_group():
    stage = [
        stage_row(1, name="Quercetin 3-O-glucoside", group="g1"),
        stage_row(2, name="Quercetin 3-O-glucoside", group="g2"),
    ]
    result = derive_selection(
        stage,
        decisions_of(
            entry(1, "quercetin 3 o GLUCOSIDE", "include", group="g1"),
            entry(2, "Quercetin 3-O-glucoside", "exclude", group="g2", reason="dup"),
        ),
    )
    assert [row["selection_status"] for row in result.rows] == ["selected", "excluded"]
    assert [issue.code for issue in result.issues] == []
    unmatched = derive_selection(
        stage, decisions_of(entry(1, "Quercetin 3-O-glucoside", "include", group="G1"))
    )
    assert {row["decision_source"] for row in unmatched.rows} == {"not_recorded"}
    assert [issue.code for issue in unmatched.issues if issue.source == "selection"] == [
        "decision_without_compound",
        "no_compound_selected",
    ]


def test_no_compound_selected_is_reported_only_when_nothing_is_selected():
    stage = [stage_row(1), stage_row(2)]
    some = derive_selection(stage, decisions_of(entry(1, "Compound 1", "include")))
    assert "no_compound_selected" not in {issue.code for issue in some.issues}
    none = derive_selection(stage, decisions_of(entry(1, "Compound 1", "exclude", reason="r")))
    assert [issue.code for issue in none.issues] == ["no_decision_recorded", "no_compound_selected"]


def test_name_only_candidates_have_no_structure_id():
    stage = [stage_row(1, "name_only"), stage_row(2, "name_only")]
    result = derive_selection(stage, decisions_of(entry(1, "Compound 1", "include")))
    assert [row["structure_id"] for row in result.rows] == ["", ""]
    assert [row["compound_row_status"] for row in result.rows] == ["name_only"] * 2
    assert [row["selection_status"] for row in result.rows] == ["selected", "needs_review"]


def test_the_derivation_is_deterministic_and_leaves_its_inputs_alone():
    stage = [stage_row(1), stage_row(2)]
    before = copy.deepcopy(stage)
    decisions = decisions_of(entry(1, "Compound 1", "include"))
    first = derive_selection(stage, decisions)
    second = derive_selection(stage, decisions)
    assert first == second
    assert stage == before


def test_decisions_that_are_not_unique_per_compound_are_a_programming_error():
    stage = [stage_row(1)]
    twice = decisions_of(entry(1, "Compound 1", "include"), entry(2, "compound 1", "include"))
    with pytest.raises(ValueError, match="not unique"):
        derive_selection(stage, twice)


# --- the selected list and the summary -----------------------------------------------------------
def derived(*statuses):
    stage, rows = [], []
    for number, status in enumerate(statuses, start=1):
        stage.append(stage_row(number, "quarantined" if status == "quarantined" else "accepted"))
        if status in ("selected", "excluded", "needs_review"):
            value = {"selected": "include", "excluded": "exclude", "needs_review": "needs_review"}[
                status
            ]
            rows.append(
                entry(
                    len(rows) + 1,
                    f"Compound {number}",
                    value,
                    reason="" if value == "include" else "r",
                )
            )
    return stage, decisions_of(*rows)


def test_the_selected_rows_are_the_selected_candidates_in_order():
    stage, decisions = derived("selected", "excluded", "selected", "needs_review", "quarantined")
    table = derive_selection(stage, decisions).rows
    chosen = selected_rows(table)
    assert [row["compound_id"] for row in chosen] == ["CMP0001", "CMP0003"]
    assert chosen[0] is table[0]
    assert selected_rows([]) == []


def test_the_summary_counts_the_table_and_the_issues():
    stage, decisions = derived("selected", "selected", "excluded", "needs_review", "quarantined")
    decisions = decisions_of(
        *decisions.rows,
        entry(9, "Ghost", "include", rules="RB-v2"),
        entry(10, "Ghost 2", "include", rules="RA-v1"),
    )
    result = derive_selection(stage, decisions)
    summary = summarize(result.rows, result.issues)
    assert summary == {
        "candidates": 5,
        "selected": 2,
        "excluded": 1,
        "needs_review": 1,
        "quarantined": 1,
        "decisions_recorded": 4,
        "decisions_not_recorded": 1,
        "decisions_without_compound": 2,
        "warnings": 3,
        "rules_versions": ["RA-v1"],
    }


def test_the_rule_versions_are_those_of_the_recorded_decisions_sorted_once_each():
    stage = [stage_row(n) for n in range(1, 5)]
    decisions = decisions_of(
        entry(1, "Compound 1", "include", rules="RB-v2"),
        entry(2, "Compound 2", "include", rules="RA-v1"),
        entry(3, "Compound 3", "include", rules="RB-v2"),
    )
    result = derive_selection(stage, decisions)
    assert summarize(result.rows, result.issues)["rules_versions"] == ["RA-v1", "RB-v2"]


# --- the checks ---------------------------------------------------------------------------------
def sound():
    stage = [stage_row(1), stage_row(2, "quarantined"), stage_row(3), stage_row(4)]
    decisions = decisions_of(
        entry(1, "Compound 1", "include"),
        entry(2, "Compound 2", "include"),
        entry(3, "Compound 3", "exclude", reason="r"),
        entry(4, "Ghost", "include"),
    )
    result = derive_selection(stage, decisions)
    table = result.rows
    return stage, table, selected_rows(table), result.issues, summarize(table, result.issues)


def check(stage, table, selected, issues, summary):
    return check_selection(table, selected, stage, issues=issues, summary=summary)


def test_a_sound_selection_has_no_problems():
    assert check(*sound()) == []


def test_a_table_with_another_number_of_rows_is_refused_at_once():
    stage, table, selected, issues, summary = sound()
    assert check(stage, table[:-1], selected, issues, summary) == [
        "the table has 3 rows for 4 compounds of the stage"
    ]


def tampered(edit):
    stage, table, selected, issues, summary = sound()
    table = copy.deepcopy(table)
    edit(table, stage, issues, summary)
    selected = selected_rows(table) if table else selected
    return check(stage, table, selected, issues, summary)


@pytest.mark.parametrize(
    ("column", "value", "fragment"),
    [
        ("compound_id", "CMP9999", "row 1 (CMP0001): compound_id is 'CMP9999'"),
        ("group", "other", "row 1 (CMP0001): group is 'other'"),
        ("name", "Other", "row 1 (CMP0001): name is 'Other'"),
        ("stp_file", "x.csv", "row 1 (CMP0001): stp_file is 'x.csv'"),
        ("structure_id", "STR0099", "row 1 (CMP0001): structure_id is 'STR0099'"),
        ("compound_row_status", "name_only", "row 1 (CMP0001): compound_row_status is 'name_only'"),
        (
            "selection_status",
            "excluded",
            "row 1 (CMP0001): selection_status is 'excluded', expected 'selected'",
        ),
        (
            "issue_codes",
            "no_decision_recorded",
            "row 1 (CMP0001): issue_codes is 'no_decision_recorded', expected ''",
        ),
        ("decision_id", "DEC-000000000000", "row 1 (CMP0001): decision_id is 'DEC-000000000000'"),
    ],
)
def test_a_tampered_row_is_named_with_its_column(column, value, fragment):
    def edit(table, stage, issues, summary):
        table[0][column] = value

    problems = tampered(edit)
    assert any(problem.startswith(fragment) for problem in problems), problems


def test_a_decision_changed_without_its_id_is_found():
    def edit(table, stage, issues, summary):
        table[3]["reviewer"] = "Someone else"

    problems = tampered(edit)
    assert any(problem.startswith("row 4 (CMP0004): decision_id is ") for problem in problems)


def test_repeated_ids_are_found():
    def edit(table, stage, issues, summary):
        table[1]["decision_id"] = table[0]["decision_id"]

    problems = tampered(edit)
    assert f"decision_id {sound()[1][0]['decision_id']} appears 2 times" in problems


def test_a_selected_list_that_is_not_the_selected_rows_is_found():
    stage, table, selected, issues, summary = sound()
    assert "the selected list is not the selected rows of the table, in order" in check(
        stage, table, [], issues, summary
    )
    assert "the selected list is not the selected rows of the table, in order" in check(
        stage, table, [*selected, table[3]], issues, summary
    )


def test_issues_that_do_not_match_the_table_are_found():
    stage, table, selected, issues, summary = sound()
    without_one = [issue for issue in issues if issue.code != "include_blocked_by_quarantine"]
    assert "the compound issues of the audit do not match the issue_codes of the table" in check(
        stage, table, selected, without_one, summary
    )


@pytest.mark.parametrize("field", [*SUMMARY_COUNTS, "rules_versions"])
def test_a_summary_that_disagrees_with_the_table_is_found(field):
    stage, table, selected, issues, summary = sound()
    summary = dict(summary)
    summary[field] = ["x"] if field == "rules_versions" else summary[field] + 1
    problems = check(stage, table, selected, issues, summary)
    assert any(problem.startswith(f"summary.{field} is ") for problem in problems), problems


# --- writing the table --------------------------------------------------------------------------
def test_the_table_is_written_in_the_fixed_column_order_with_lf_and_no_bom(tmp_path):
    stage = [stage_row(1), stage_row(2)]
    rows = derive_selection(stage, decisions_of(entry(1, "Compound 1", "include"))).rows
    path = tmp_path / "t.tsv"
    write_selection_table(path, rows)
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    lines = raw.decode("utf-8").split("\n")
    assert lines[0] == "\t".join(SELECTION_COLUMNS)
    assert lines[1].split("\t") == [rows[0][column] for column in SELECTION_COLUMNS]
    assert lines[-1] == ""
    assert len(lines) == 4


def test_an_empty_list_is_written_as_the_header_alone(tmp_path):
    path = tmp_path / "t.tsv"
    write_selection_table(path, [])
    assert path.read_bytes() == ("\t".join(SELECTION_COLUMNS) + "\n").encode("utf-8")
