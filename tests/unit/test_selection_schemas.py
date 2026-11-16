"""The three schemas of the selection stage and the `inputs.selection` key of the run schema.

Every constraint has a good and a bad example. A bad example differs from a good one in the one
thing that is under test, so a constraint that is missing from a schema makes its test fail.
"""

from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator

from rnp.config import load_schema

BASE_ID = "https://github.com/zym137706-ops/reproducible-network-pharmacology/schemas/"
SCHEMAS = ["selection_input_row", "selection_decisions_row", "selection_audit"]


def problems(name: str, instance) -> list[str]:
    validator = Draft202012Validator(load_schema(name))
    return [error.message for error in validator.iter_errors(instance)]


def with_(base: dict, **changes):
    return {**base, **changes}


def without(base: dict, key: str):
    return {name: value for name, value in base.items() if name != key}


# --- all three ---------------------------------------------------------------------------------
@pytest.mark.parametrize("name", SCHEMAS)
def test_a_schema_is_a_closed_draft_2020_12_object_with_the_repository_id(name):
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == f"{BASE_ID}{name}.schema.json"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["title"] and schema["description"]
    assert sorted(schema["required"]) == sorted(schema["properties"])


# --- the input row -----------------------------------------------------------------------------
INPUT_GOOD = {
    "compound": "Quercetin",
    "group": "all",
    "decision": "include",
    "reason_codes": "",
    "rules_version": "RA-v1",
    "reviewer": "Researcher",
    "evidence_refs": "",
}
INPUT_COLUMNS = list(INPUT_GOOD)


def test_the_input_row_has_the_seven_cells_in_order():
    schema = load_schema("selection_input_row")
    assert list(schema["properties"]) == INPUT_COLUMNS
    assert schema["required"] == INPUT_COLUMNS
    assert schema["properties"]["decision"] == {"enum": ["include", "exclude", "needs_review"]}


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"compound": "Quercetin 3-O-glucoside (isomer 2)"},
        {"group": "ginseng leaf"},
        {"decision": "exclude", "reason_codes": "no_fit"},
        {"decision": "needs_review", "reason_codes": "a;b_2;c3"},
        {"decision": "include", "reason_codes": "documented_but_kept"},
        {"reason_codes": "z;a"},
        {"rules_version": "RA oral 2026-11 v1"},
        {"evidence_refs": "PMID 123; table S2"},
        {"compound": "槲皮素"},
    ],
    ids=lambda changes: ",".join(changes) or "base",
)
def test_good_input_rows(changes):
    assert problems("selection_input_row", with_(INPUT_GOOD, **changes)) == []


@pytest.mark.parametrize("key", INPUT_COLUMNS)
def test_every_input_cell_is_required(key):
    assert problems("selection_input_row", without(INPUT_GOOD, key))


def test_an_input_row_has_no_other_cells():
    assert problems("selection_input_row", with_(INPUT_GOOD, note="x"))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("compound", ""),
        ("compound", " Quercetin"),
        ("compound", "Quercetin "),
        ("compound", "a\tb"),
        ("compound", "a\nb"),
        ("compound", 1),
        ("group", ""),
        ("group", " g"),
        ("group", "g\t1"),
        ("decision", "Include"),
        ("decision", "INCLUDE"),
        ("decision", ""),
        ("decision", "maybe"),
        ("decision", None),
        ("reason_codes", "Upper"),
        ("reason_codes", "9lives"),
        ("reason_codes", "a b"),
        ("reason_codes", "a;;b"),
        ("reason_codes", ";a"),
        ("reason_codes", "a;"),
        ("reason_codes", "a-b"),
        ("reason_codes", "a; b"),
        ("reason_codes", "_a"),
        ("reason_codes", "é"),
        ("rules_version", ""),
        ("rules_version", " v1"),
        ("rules_version", "v1 "),
        ("reviewer", ""),
        ("reviewer", "a\tb"),
        ("evidence_refs", " x"),
        ("evidence_refs", "x "),
        ("evidence_refs", "a\tb"),
    ],
)
def test_bad_input_cells(key, value):
    assert problems("selection_input_row", with_(INPUT_GOOD, **{key: value}))


@pytest.mark.parametrize("value", ["exclude", "needs_review"])
def test_exclude_and_needs_review_need_a_reason_code_but_include_does_not(value):
    assert problems("selection_input_row", with_(INPUT_GOOD, decision=value, reason_codes=""))
    assert (
        problems("selection_input_row", with_(INPUT_GOOD, decision=value, reason_codes="why")) == []
    )
    assert (
        problems("selection_input_row", with_(INPUT_GOOD, decision="include", reason_codes=""))
        == []
    )


# --- the decisions row -------------------------------------------------------------------------
ROW_GOOD = {
    "decision_id": "DEC-0123456789ab",
    "compound_id": "CMP0001",
    "group": "all",
    "name": "Quercetin",
    "stp_file": "q.csv",
    "structure_id": "STR0001",
    "compound_row_status": "accepted",
    "decision": "include",
    "decision_source": "recorded",
    "selection_status": "selected",
    "reason_codes": "",
    "rules_version": "RA-v1",
    "reviewer": "Researcher",
    "evidence_refs": "",
    "issue_codes": "",
}
ROW_COLUMNS = list(ROW_GOOD)
NOT_RECORDED = {
    "decision": "needs_review",
    "decision_source": "not_recorded",
    "selection_status": "needs_review",
    "reason_codes": "",
    "rules_version": "",
    "reviewer": "",
    "evidence_refs": "",
    "issue_codes": "no_decision_recorded",
}
QUARANTINED = {"compound_row_status": "quarantined", "structure_id": ""}


def test_the_decisions_row_has_the_fifteen_columns_in_order():
    schema = load_schema("selection_decisions_row")
    assert list(schema["properties"]) == ROW_COLUMNS
    assert schema["required"] == ROW_COLUMNS


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"compound_row_status": "name_only", "structure_id": ""},
        {"decision": "exclude", "selection_status": "excluded", "reason_codes": "no_fit"},
        {"decision": "needs_review", "selection_status": "needs_review", "reason_codes": "ask"},
        {
            "decision": "include",
            "selection_status": "quarantined",
            **QUARANTINED,
            "issue_codes": "include_blocked_by_quarantine",
        },
        {
            "decision": "exclude",
            "selection_status": "excluded",
            "reason_codes": "bad",
            **QUARANTINED,
            "issue_codes": "quarantine_resolved_by_exclusion",
        },
        {
            "decision": "needs_review",
            "selection_status": "quarantined",
            "reason_codes": "ask",
            **QUARANTINED,
        },
        NOT_RECORDED,
        {**NOT_RECORDED, "compound_row_status": "name_only", "structure_id": ""},
        {**NOT_RECORDED, "selection_status": "quarantined", **QUARANTINED},
        {"stp_file": ""},
        {"evidence_refs": "PMID 1", "reason_codes": "a;b"},
    ],
    ids=lambda changes: "+".join(
        str(changes.get(key, ""))
        for key in ("selection_status", "decision_source", "compound_row_status")
    ),
)
def test_good_decisions_rows(changes):
    assert problems("selection_decisions_row", with_(ROW_GOOD, **changes)) == []


@pytest.mark.parametrize("key", ROW_COLUMNS)
def test_every_column_is_required(key):
    assert problems("selection_decisions_row", without(ROW_GOOD, key))


def test_a_decisions_row_has_no_other_columns():
    assert problems("selection_decisions_row", with_(ROW_GOOD, note="x"))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("decision_id", ""),
        ("decision_id", "DEC-"),
        ("decision_id", "DEC-123"),
        ("decision_id", "dec-0123456789ab"),
        ("decision_id", "DEC-0123456789AB"),
        ("decision_id", "DEC-0123456789abc"),
        ("decision_id", "X-0123456789ab"),
        ("compound_id", ""),
        ("compound_id", "CMP 1"),
        ("group", ""),
        ("name", " Quercetin"),
        ("name", ""),
        ("stp_file", " q.csv"),
        ("structure_id", "STR1"),
        ("structure_id", "str0001"),
        ("compound_row_status", "other"),
        ("decision", "maybe"),
        ("decision_source", "x"),
        ("selection_status", "unknown"),
        ("reason_codes", "Upper"),
        ("reason_codes", "a;;b"),
        ("rules_version", " v1"),
        ("reviewer", "a\tb"),
        ("evidence_refs", "a\tb"),
        ("issue_codes", "unknown_code"),
        ("issue_codes", "no_decision_recorded;"),
        ("issue_codes", ";no_decision_recorded"),
        ("issue_codes", "decision_without_compound"),
        ("issue_codes", "no_compound_selected"),
    ],
)
def test_bad_decisions_cells(key, value):
    assert problems("selection_decisions_row", with_(ROW_GOOD, **{key: value}))


def test_an_issue_code_list_may_hold_several_codes():
    codes = "include_blocked_by_quarantine;no_decision_recorded"
    assert problems("selection_decisions_row", with_(ROW_GOOD, issue_codes=codes)) == []


BAD_COMBINATIONS = {
    "recorded without a rules version": {"rules_version": ""},
    "recorded without a reviewer": {"reviewer": ""},
    "recorded exclude without a reason": {
        "decision": "exclude",
        "selection_status": "excluded",
        "reason_codes": "",
    },
    "recorded needs_review without a reason": {
        "decision": "needs_review",
        "selection_status": "needs_review",
        "reason_codes": "",
    },
    "not recorded but include": {
        **NOT_RECORDED,
        "decision": "include",
        "selection_status": "selected",
    },
    "not recorded with a reason": {**NOT_RECORDED, "reason_codes": "x"},
    "not recorded with a rules version": {**NOT_RECORDED, "rules_version": "RA-v1"},
    "not recorded with a reviewer": {**NOT_RECORDED, "reviewer": "R"},
    "not recorded with evidence": {**NOT_RECORDED, "evidence_refs": "e"},
    "not recorded without its issue": {**NOT_RECORDED, "issue_codes": ""},
    "not recorded with another issue": {
        **NOT_RECORDED,
        "issue_codes": "include_blocked_by_quarantine",
    },
    "selected but exclude": {"decision": "exclude", "reason_codes": "x"},
    "selected but needs_review": {"decision": "needs_review", "reason_codes": "x"},
    "selected but quarantined row": {**QUARANTINED},
    "excluded but include": {"selection_status": "excluded"},
    "excluded but needs_review": {
        "decision": "needs_review",
        "selection_status": "excluded",
        "reason_codes": "x",
    },
    "needs_review but include": {"selection_status": "needs_review"},
    "needs_review but exclude": {
        "decision": "exclude",
        "selection_status": "needs_review",
        "reason_codes": "x",
    },
    "needs_review but quarantined row": {
        "decision": "needs_review",
        "selection_status": "needs_review",
        "reason_codes": "x",
        **QUARANTINED,
    },
    "quarantined but accepted row": {"selection_status": "quarantined"},
    "quarantined but exclude": {
        "decision": "exclude",
        "selection_status": "quarantined",
        "reason_codes": "x",
        **QUARANTINED,
    },
    "name_only with a structure id": {"compound_row_status": "name_only"},
    "accepted without a structure id": {"structure_id": ""},
}


@pytest.mark.parametrize("changes", list(BAD_COMBINATIONS.values()), ids=list(BAD_COMBINATIONS))
def test_bad_combinations(changes):
    assert problems("selection_decisions_row", with_(ROW_GOOD, **changes))


# --- the audit ---------------------------------------------------------------------------------
HASH = "a" * 64
AUDIT_GOOD = {
    "schema_version": "1.0",
    "generated_by": "rnp compounds select",
    "stage_status": "partial",
    "identity_mode": "structure",
    "config": {"path": "/x/run.yaml", "sha256": HASH},
    "inputs": {
        "compounds_stage": {
            "dir": "/x/results/c_compounds",
            "audit_sha256": HASH,
            "table_sha256": "b" * 64,
            "stage_status": "partial",
        },
        "selection": {"path": "/x/decisions.tsv", "sha256": "c" * 64, "rows": 4},
    },
    "rule_versions": {"selection": "v0.2.0-selection-rules"},
    "summary": {
        "candidates": 4,
        "selected": 1,
        "excluded": 1,
        "needs_review": 1,
        "quarantined": 1,
        "decisions_recorded": 4,
        "decisions_not_recorded": 0,
        "decisions_without_compound": 0,
        "warnings": 2,
        "rules_versions": ["RA-v1"],
    },
    "issues": [
        {
            "level": "warning",
            "code": "include_blocked_by_quarantine",
            "source": "compounds",
            "row": 2,
            "compound_id": "CMP0002",
            "message": "blocked",
        }
    ],
    "notes": [{"code": "extra_columns_ignored", "message": "ignored columns: note"}],
    "selection_decisions_sha256": "d" * 64,
    "selected_compounds_sha256": "e" * 64,
}


def edited(*path, value):
    document = copy.deepcopy(AUDIT_GOOD)
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return document


def issue(**changes):
    base = AUDIT_GOOD["issues"][0]
    return {**base, **changes}


def test_the_audit_has_its_twelve_keys():
    schema = load_schema("selection_audit")
    assert sorted(schema["required"]) == sorted(AUDIT_GOOD)
    assert problems("selection_audit", AUDIT_GOOD) == []


@pytest.mark.parametrize(
    "document",
    [
        edited("stage_status", value="complete"),
        edited("identity_mode", value="name_only"),
        edited("inputs", "compounds_stage", "stage_status", value="complete"),
        edited("summary", "rules_versions", value=[]),
        edited("summary", "rules_versions", value=["RA-v1", "RB-v2"]),
        edited("summary", "selected", value=0),
        edited("issues", value=[]),
        edited("notes", value=[]),
        edited("issues", value=[issue(code="no_decision_recorded")]),
        edited("issues", value=[issue(code="quarantine_resolved_by_exclusion")]),
        edited(
            "issues",
            value=[
                issue(code="decision_without_compound", source="selection", row=3, compound_id="")
            ],
        ),
        edited(
            "issues",
            value=[
                issue(code="no_compound_selected", source="selection", row=None, compound_id="")
            ],
        ),
    ],
    ids=lambda document: "variant",
)
def test_good_audits(document):
    assert problems("selection_audit", document) == []


@pytest.mark.parametrize("key", list(AUDIT_GOOD))
def test_every_audit_key_is_required(key):
    assert problems("selection_audit", without(AUDIT_GOOD, key))


def test_an_audit_has_no_other_keys():
    assert problems("selection_audit", with_(AUDIT_GOOD, extra=1))


BAD_AUDITS = {
    "schema version": edited("schema_version", value="1.1"),
    "generator": edited("generated_by", value="rnp ingest compounds"),
    "stage status": edited("stage_status", value="failed"),
    "identity mode": edited("identity_mode", value="mixed"),
    "config path empty": edited("config", "path", value=""),
    "config hash short": edited("config", "sha256", value="abc"),
    "config hash upper": edited("config", "sha256", value="A" * 64),
    "stage dir empty": edited("inputs", "compounds_stage", "dir", value=""),
    "stage audit hash": edited("inputs", "compounds_stage", "audit_sha256", value="z" * 64),
    "stage table hash": edited("inputs", "compounds_stage", "table_sha256", value=""),
    "compounds stage status": edited("inputs", "compounds_stage", "stage_status", value="failed"),
    "no selection in the inputs": edited(
        "inputs", value={"compounds_stage": AUDIT_GOOD["inputs"]["compounds_stage"]}
    ),
    "selection rows zero": edited("inputs", "selection", "rows", value=0),
    "selection hash": edited("inputs", "selection", "sha256", value="1"),
    "selection extra": edited("inputs", "selection", "extra", value=1),
    "rule version without the suffix": edited("rule_versions", "selection", value="v0.2.0"),
    "rule version without v": edited("rule_versions", "selection", value="0.2.0-selection-rules"),
    "rule versions extra": edited("rule_versions", "other", value="x"),
    "no candidates": edited("summary", "candidates", value=0),
    "negative count": edited("summary", "selected", value=-1),
    "float count": edited("summary", "excluded", value=1.5),
    "missing count": {**AUDIT_GOOD, "summary": without(AUDIT_GOOD["summary"], "warnings")},
    "summary extra": edited("summary", "extra", value=1),
    "repeated rule version": edited("summary", "rules_versions", value=["RA-v1", "RA-v1"]),
    "blank rule version": edited("summary", "rules_versions", value=[" RA-v1"]),
    "issue level": edited("issues", value=[issue(level="error")]),
    "issue code": edited("issues", value=[issue(code="stereo_undefined")]),
    "issue source": edited("issues", value=[issue(source="registry")]),
    "issue row zero": edited("issues", value=[issue(row=0)]),
    "issue row text": edited("issues", value=[issue(row="2")]),
    "issue message empty": edited("issues", value=[issue(message="")]),
    "issue without compound id": edited("issues", value=[without(issue(), "compound_id")]),
    "issue extra": edited("issues", value=[issue(extra=1)]),
    "note without message": edited("notes", value=[{"code": "x"}]),
    "note with empty code": edited("notes", value=[{"code": "", "message": "m"}]),
    "decisions hash": edited("selection_decisions_sha256", value="d" * 63),
    "selected hash": edited("selected_compounds_sha256", value="E" * 64),
}


@pytest.mark.parametrize("document", list(BAD_AUDITS.values()), ids=list(BAD_AUDITS))
def test_bad_audits(document):
    assert problems("selection_audit", document)


# --- the run schema ----------------------------------------------------------------------------
RUN_BASE = {
    "project": "p",
    "species": "Homo_sapiens",
    "inputs": {"compounds": "c.tsv", "stp_dir": "stp", "disease_genes": "d.txt"},
    "thresholds": {"stp_probability": 0.1},
    "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
    "outputs": {"dir": "results"},
}


def run_problems(**inputs) -> list[str]:
    config = copy.deepcopy(RUN_BASE)
    config["inputs"].update(inputs)
    return problems("run", config)


def test_the_run_schema_describes_inputs_selection():
    prop = load_schema("run")["properties"]["inputs"]["properties"]["selection"]
    assert prop["type"] == "string" and prop["minLength"] == 1 and prop["description"]


@pytest.mark.parametrize(
    "value", ["decisions.tsv", "../choices/decisions.csv", "C:/data/decisions.tsv"]
)
def test_inputs_selection_is_a_path(value):
    assert run_problems(selection=value) == []


@pytest.mark.parametrize("value", ["", 1, None, ["decisions.tsv"], {"path": "d.tsv"}])
def test_inputs_selection_must_be_a_non_empty_string(value):
    assert run_problems(selection=value)


def test_a_config_without_inputs_selection_is_still_valid_and_other_keys_are_still_closed():
    assert run_problems() == []
    assert run_problems(selections="decisions.tsv")
