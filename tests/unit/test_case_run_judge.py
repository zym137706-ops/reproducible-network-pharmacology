"""The case policy: what the case entry makes of a finished `rnp ingest compounds` run.

`judge_stage(args, returncode, stderr, stage_dir)` reads the audit and the table of a compounds
stage and either returns the structure record for the provenance or raises ValueError naming every
problem. The stages here are made by hand (case_run_support.write_stage), so nothing needs RDKit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from case_run_support import (
    ERROR_CODES,
    TOOLKIT,
    case_args,
    load_run,
    stage_issue,
    stage_row,
    write_stage,
)

from rnp.analysis.compounds_link import CHECKED_SUBMISSIONS
from rnp.config import load_schema

FATAL_FIELDS = {
    "missing_structure": "smiles",
    "invalid_smiles": "smiles",
    "submission_structure_mismatch": "submitted_structure",
    "submission_hash_mismatch": "result_sha256",
    "submission_species_mismatch": "species",
    "submission_export_missing": "stp_file",
    "submission_name_mismatch": "compound",
    "submission_cid_mismatch": "pubchem_cid",
    "submission_record_missing": "stp_file",
    "submission_hash_not_declared": "result_sha256",
    "log_row_without_compound": "stp_file",
}
RECORDED = [
    "shared_structure",
    "same_connectivity_different_stereo",
    "stereo_undefined",
    "multi_fragment",
    "charged_structure",
    "smiles_whitespace_trimmed",
    "structure_changed",
    "structure_reactivated",
    "submission_export_reconstructed",
]
UNCHECKED = ["not_recorded", "rejected", "not_checked", "not_applicable"]


def judge(tmp_path: Path, rows, issues=(), *, mode="structure", returncode=0, stderr=""):
    run = load_run()
    args = case_args(tmp_path / "case")
    stage = write_stage(tmp_path / "stage", rows, list(issues), mode=mode)
    return args, run.judge_stage(args, returncode, stderr, stage)


def test_a_clean_stage_gives_the_structure_record(tmp_path: Path) -> None:
    rows = [stage_row(1), stage_row(2, "verified_kind_unstated"), stage_row(3, "reconstructed")]
    issues = [stage_issue("stereo_undefined", 2), stage_issue("submission_export_reconstructed", 3)]
    _, record = judge(tmp_path, rows, issues)
    assert record == {
        "mode": "structure",
        "toolkit": TOOLKIT,
        "rows": 3,
        "submission_status_counts": {
            "reconstructed": 1,
            "verified": 1,
            "verified_kind_unstated": 1,
        },
        "issue_code_counts": {"stereo_undefined": 1, "submission_export_reconstructed": 1},
    }


def test_the_counts_are_sorted_and_count_repeats(tmp_path: Path) -> None:
    rows = [stage_row(number) for number in (1, 2, 3)]
    issues = [stage_issue("multi_fragment", n) for n in (1, 2, 3)] + [
        stage_issue("charged_structure")
    ]
    _, record = judge(tmp_path, rows, issues)
    assert list(record["issue_code_counts"]) == ["charged_structure", "multi_fragment"]
    assert record["issue_code_counts"] == {"charged_structure": 1, "multi_fragment": 3}
    assert record["submission_status_counts"] == {"verified": 3}


@pytest.mark.parametrize("code", RECORDED)
def test_a_recorded_code_is_counted_and_does_not_stop_the_run(tmp_path: Path, code: str) -> None:
    _, record = judge(tmp_path, [stage_row(1)], [stage_issue(code)])
    assert record["issue_code_counts"] == {code: 1}


@pytest.mark.parametrize("code", sorted(FATAL_FIELDS))
def test_a_fatal_code_stops_the_run_and_names_the_field(tmp_path: Path, code: str) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    rows = [stage_row(1), stage_row(2)]
    number = 0 if code == "log_row_without_compound" else 2
    stage = write_stage(tmp_path / "stage", rows, [stage_issue(code, number)])
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, 3 if code in ERROR_CODES else 0, "", stage)
    message = str(caught.value)
    assert FATAL_FIELDS[code] in message
    assert code in message
    if number:
        assert "Compound 2" in message
        assert "Compound 1" not in message
    else:
        assert "entry" not in message  # no compound is named when the code is about no compound
    where = args.compounds if stage_issue(code)["source"] == "compounds" else args.log
    assert str(where) in message
    entry = "entry 'Compound 2' " if number else ""
    text = stage_issue(code, number)["message"]
    assert message == f"{where}: {entry}{FATAL_FIELDS[code]}: {text} [{code}]"


def test_every_problem_is_reported_not_only_the_first(tmp_path: Path) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    rows = [
        stage_row(1),
        stage_row(2, "rejected", row_status="quarantined"),
        stage_row(3, "rejected"),
    ]
    issues = [
        stage_issue("submission_structure_mismatch", 2),
        stage_issue("submission_hash_mismatch", 3),
        stage_issue("submission_cid_mismatch", 3),
    ]
    stage = write_stage(tmp_path / "stage", rows, issues)
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, 3, "", stage)
    message = str(caught.value)
    for field in ("submitted_structure", "result_sha256", "pubchem_cid"):
        assert field in message
    assert message.count("Compound 3") >= 2
    assert len(message.splitlines()) == 3


@pytest.mark.parametrize("status", UNCHECKED)
def test_a_submission_that_was_not_checked_stops_the_run(tmp_path: Path, status: str) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    stage = write_stage(tmp_path / "stage", [stage_row(1), stage_row(2, status)])
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, 0, "", stage)
    message = str(caught.value)
    assert "submission_status" in message
    assert status in message
    assert "Compound 2" in message
    assert "Compound 1" not in message


def test_a_compound_with_a_fatal_issue_is_not_reported_twice(tmp_path: Path) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    rows = [stage_row(1), stage_row(2, "rejected", row_status="quarantined")]
    stage = write_stage(tmp_path / "stage", rows, [stage_issue("submission_hash_mismatch", 2)])
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, 3, "", stage)
    assert "submission_status" not in str(caught.value)
    assert len(str(caught.value).splitlines()) == 1


def test_a_stage_in_name_only_mode_is_not_a_verification(tmp_path: Path) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    rows = [stage_row(1, "not_applicable", row_status="name_only", structure_status="name_only")]
    stage = write_stage(tmp_path / "stage", rows, mode="name_only")
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, 0, "", stage)
    assert "structure mode" in str(caught.value)
    assert "smiles" in str(caught.value)


def test_a_table_level_rejection_is_passed_on_with_the_words_of_the_core(tmp_path: Path) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    text = "error: LOG.tsv: the submission log has invalid rows\n  - row 1: species: 'x'"
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, 2, text + "\n", tmp_path / "no-stage")
    assert str(caught.value) == f"rnp ingest compounds rejected the inputs (exit 2): {text}"
    assert not (tmp_path / "no-stage").exists()
    with pytest.raises(ValueError) as padded:
        run.judge_stage(args, 2, "  " + text + "  " + chr(10) * 2, tmp_path / "no-stage")
    assert str(padded.value) == str(caught.value)


@pytest.mark.parametrize("code", [1, 4, 130])
def test_any_other_exit_code_is_a_failure_of_the_command(tmp_path: Path, code: int) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    stage = write_stage(tmp_path / "stage", [stage_row(1)])
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, code, "  unexpected error: boom  " + chr(10), stage)
    assert str(caught.value) == f"rnp ingest compounds failed (exit {code}): unexpected error: boom"


@pytest.mark.parametrize("missing", ["both", "audit", "table"])
@pytest.mark.parametrize("returncode", [0, 3])
def test_a_run_that_wrote_no_complete_stage_is_an_error(
    tmp_path: Path, returncode, missing
) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    stage = write_stage(tmp_path / "stage", [stage_row(1)])
    if missing in ("both", "audit"):
        (stage / "compounds_audit.json").unlink()
    if missing in ("both", "table"):
        (stage / "compound_structures.tsv").unlink()
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, returncode, "", stage)
    assert str(stage) in str(caught.value)
    with pytest.raises(ValueError):
        run.judge_stage(args, returncode, "", tmp_path / "missing")


def test_a_code_the_policy_does_not_know_is_refused(tmp_path: Path) -> None:
    run = load_run()
    args = case_args(tmp_path / "case")
    issue = stage_issue("shared_structure")
    issue["code"] = "a_code_of_a_later_release"
    stage = write_stage(tmp_path / "stage", [stage_row(1)], [issue])
    with pytest.raises(ValueError) as caught:
        run.judge_stage(args, 0, "", stage)
    assert "a_code_of_a_later_release" in str(caught.value)


# --- the policy covers the vocabulary of the core --------------------
def schema_codes() -> set[str]:
    defs = load_schema("compounds_audit")["$defs"]
    return set(defs["issue_error"]["properties"]["code"]["enum"]) | set(
        defs["issue_warning"]["properties"]["code"]["enum"]
    )


def test_the_policy_classifies_every_code_of_the_audit_schema() -> None:
    run = load_run()
    assert set(run.ISSUE_POLICY) == schema_codes()
    assert set(run.ISSUE_POLICY.values()) == {"fatal", "recorded"}


def test_every_error_code_of_the_core_is_fatal_for_the_case() -> None:
    run = load_run()
    errors = set(
        load_schema("compounds_audit")["$defs"]["issue_error"]["properties"]["code"]["enum"]
    )
    assert errors == ERROR_CODES
    assert {code for code in errors if run.ISSUE_POLICY[code] != "fatal"} == set()


def test_the_fatal_warnings_are_the_ones_that_mean_an_unchecked_submission() -> None:
    run = load_run()
    fatal = {code for code, policy in run.ISSUE_POLICY.items() if policy == "fatal"}
    assert fatal == set(FATAL_FIELDS)
    assert {code for code, policy in run.ISSUE_POLICY.items() if policy == "recorded"} == set(
        RECORDED
    )


def test_every_fatal_code_names_a_column_of_the_inputs() -> None:
    run = load_run()
    assert run.ISSUE_FIELD == FATAL_FIELDS


def test_the_policy_classifies_every_submission_status_of_the_table_schema() -> None:
    run = load_run()
    statuses = set(
        load_schema("compound_structures_row")["properties"]["submission_status"]["enum"]
    )
    assert set(run.SUBMISSION_POLICY) == statuses
    assert set(run.SUBMISSION_POLICY.values()) == {"accepted", "rejected"}


def test_the_case_accepts_the_submissions_that_the_stage_link_accepts() -> None:
    run = load_run()
    accepted = {status for status, policy in run.SUBMISSION_POLICY.items() if policy == "accepted"}
    assert accepted == set(CHECKED_SUBMISSIONS)
    assert set(UNCHECKED) == set(run.SUBMISSION_POLICY) - accepted


def test_the_constants_that_the_provenance_records() -> None:
    run = load_run()
    assert run.POLICY_VERSION == "case-log-policy-v2"
    assert run.VERIFIED_BY == "rnp ingest compounds"
    assert run.STAGE_RUN_ID == "run"
    assert run.STAGE_DIR_NAME == "run_compounds"
    assert run.STAGE_AUDIT_NAME == "compounds_audit.json"
    assert run.STAGE_TABLE_NAME == "compound_structures.tsv"
