"""`stp_audit.schema.json` 1.2: the audit written when a selection stage is applied.

Version 1.1 audits (every audit written without `--selection`) stay valid. Version 1.2 adds the file
status `not_selected` and the summary count `files_not_selected`: a 1.2 audit must have the count,
and a 1.1 audit must have neither the count nor a `not_selected` file. The top level stays closed.
"""

from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator

from rnp.config import load_schema

FILE = {
    "path": "c1.csv",
    "format": "csv",
    "sha256": "d" * 64,
    "status": "ok",
    "rows_total": 3,
    "rows_valid": 3,
    "rows_invalid": 0,
    "rows_below_threshold": 0,
    "rows_used": 3,
    "warnings": [],
    "errors": [],
}
NOT_SELECTED = {
    **FILE,
    "path": "c2.csv",
    "status": "not_selected",
    "compound_id": "CMP0002",
    "group": "all",
    "reason": "compound_excluded",
    "rows_total": 0,
    "rows_valid": 0,
    "rows_used": 0,
}
OLD_STATUSES = [
    "ok",
    "partial",
    "below_threshold",
    "invalid_rows",
    "no_predictions",
    "error",
    "quarantined",
]


def audit(version: str = "1.1") -> dict:
    """A small valid audit of the given version (1.2 has a file that was not selected)."""
    summary = {
        "files": 1,
        "files_bound": 1,
        "files_quarantined": 0,
        "files_missing": 0,
        "rows_total": 3,
        "rows_valid": 3,
        "rows_invalid": 0,
        "rows_below_threshold": 0,
        "rows_used": 3,
        "compounds_registered": 1,
        "warnings": 0,
        "errors": 0,
    }
    files = [copy.deepcopy(FILE)]
    if version == "1.2":
        files.append(copy.deepcopy(NOT_SELECTED))
        summary = {**summary, "files": 2, "files_not_selected": 1}
    return {
        "schema_version": version,
        "generated_by": "rnp ingest stp",
        "stage_status": "complete",
        "config": {"path": "run.yaml", "sha256": "a" * 64},
        "thresholds": {"stp_probability": 0.1},
        "files": files,
        "quarantine": [],
        "missing_exports": [],
        "summary": summary,
        "registry": {"path": "registry.tsv", "rule_version": "v1", "entries": 2},
        "notes": [],
        "targets_sha256": "b" * 64,
        "compounds_registered_sha256": "c" * 64,
    }


def problems(document) -> list[str]:
    validator = Draft202012Validator(load_schema("stp_audit"))
    return sorted(error.message for error in validator.iter_errors(document))


def test_the_schema_is_a_valid_json_schema():
    Draft202012Validator.check_schema(load_schema("stp_audit"))


@pytest.mark.parametrize("version", ["1.1", "1.2"])
def test_an_audit_of_either_version_is_valid(version):
    assert problems(audit(version)) == []


@pytest.mark.parametrize("status", OLD_STATUSES)
@pytest.mark.parametrize("version", ["1.1", "1.2"])
def test_the_old_file_statuses_are_valid_in_both_versions(version, status):
    document = audit(version)
    document["files"][0]["status"] = status
    assert problems(document) == []


def test_the_status_not_selected_is_valid_in_1_2():
    document = audit("1.2")
    assert document["files"][1]["status"] == "not_selected"
    assert problems(document) == []


@pytest.mark.parametrize("status", ["selected", "excluded", "Not_selected", "not selected", ""])
def test_other_file_statuses_are_refused(status):
    document = audit("1.2")
    document["files"][1]["status"] = status
    assert problems(document) != []


def test_a_1_2_audit_without_the_count_is_refused():
    document = audit("1.2")
    del document["summary"]["files_not_selected"]
    assert problems(document) != []


def test_a_1_1_audit_with_the_count_is_refused():
    document = audit("1.1")
    document["summary"]["files_not_selected"] = 0
    assert problems(document) != []


def test_a_1_1_audit_with_a_file_that_was_not_selected_is_refused():
    document = audit("1.1")
    document["files"].append(copy.deepcopy(NOT_SELECTED))
    assert problems(document) != []


@pytest.mark.parametrize("value", [-1, 1.5, "1", None, True])
def test_the_count_is_a_non_negative_integer(value):
    document = audit("1.2")
    document["summary"]["files_not_selected"] = value
    assert problems(document) != []


@pytest.mark.parametrize("value", ["1.0", "1.3", "2.0", "1.2.0", "", 1.1, 1.2, None])
def test_other_versions_are_refused(value):
    document = audit("1.2")
    document["schema_version"] = value
    assert problems(document) != []


def test_a_missing_version_is_refused():
    document = audit("1.2")
    del document["schema_version"]
    assert problems(document) != []


@pytest.mark.parametrize("version", ["1.1", "1.2"])
def test_the_top_level_stays_closed(version):
    document = audit(version)
    document["parents"] = []
    assert problems(document) != []


@pytest.mark.parametrize("version", ["1.1", "1.2"])
@pytest.mark.parametrize(
    "key",
    ["generated_by", "config", "thresholds", "files", "summary", "registry", "targets_sha256"],
)
def test_the_required_keys_are_still_required(version, key):
    document = audit(version)
    del document[key]
    assert problems(document) != []
