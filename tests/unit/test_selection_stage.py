"""The selection stage `run_selection`: outputs, audit, manifest, errors and what it never touches.

The compounds stage is produced by `run_compounds` with fakes (no RDKit, no network). With the
scenario MIXED the candidates are Compound 1 (accepted), Compound 2 and 3 (quarantined), Compound 4
(accepted); see selection_support.
"""

from __future__ import annotations

import jsonschema
import pytest
from selection_support import (
    ALL_FOUR,
    EVERYTHING_DECIDED,
    LATER,
    build,
    decision,
    decisions_path,
    read_json,
    read_tsv,
    select,
    setup,
    snapshot,
    stage,
    write_decisions,
)
from structures_support import NOW

from rnp.config import load_schema
from rnp.errors import InputError
from rnp.provenance import sha256_file
from rnp.selection import SELECTION_COLUMNS, decision_id

SUMMARY_KEYS = [
    "status",
    "stage_status",
    "identity_mode",
    "run_id",
    "run_dir",
    "summary",
    "unresolved",
]
TABLE = [
    (
        "CMP0001",
        "Compound 1",
        "c1.csv",
        "STR0001",
        "accepted",
        "include",
        "recorded",
        "selected",
        "",
        "",
        "",
    ),
    (
        "CMP0002",
        "Compound 2",
        "c2.csv",
        "STR0002",
        "quarantined",
        "include",
        "recorded",
        "quarantined",
        "",
        "",
        "include_blocked_by_quarantine",
    ),
    (
        "CMP0003",
        "Compound 3",
        "c3.csv",
        "",
        "quarantined",
        "exclude",
        "recorded",
        "excluded",
        "bad_data;no_structure",
        "notes.pdf",
        "quarantine_resolved_by_exclusion",
    ),
    (
        "CMP0004",
        "Compound 4",
        "c4.csv",
        "STR0003",
        "accepted",
        "needs_review",
        "recorded",
        "needs_review",
        "check_identity",
        "",
        "",
    ),
]


def expected_rows(table=TABLE):
    rows = []
    for (
        cid,
        name,
        stp,
        structure,
        row_status,
        value,
        source,
        status,
        reasons,
        refs,
        issues,
    ) in table:
        row = {
            "compound_id": cid,
            "group": "all",
            "name": name,
            "stp_file": stp,
            "structure_id": structure,
            "compound_row_status": row_status,
            "decision": value,
            "decision_source": source,
            "selection_status": status,
            "reason_codes": reasons,
            "rules_version": "RA-v1",
            "reviewer": "Researcher",
            "evidence_refs": refs,
            "issue_codes": issues,
        }
        row["decision_id"] = decision_id(
            **{
                key: row[key]
                for key in (
                    "compound_id",
                    "structure_id",
                    "decision",
                    "decision_source",
                    "reason_codes",
                    "rules_version",
                    "reviewer",
                    "evidence_refs",
                )
            }
        )
        rows.append({column: row[column] for column in SELECTION_COLUMNS})
    return rows


def run_all_four(tmp_path, **kwargs):
    config, compounds = setup(tmp_path, ALL_FOUR)
    return config, compounds, select(config, compounds, **kwargs)


def test_the_runner_needs_no_rdkit():
    import subprocess
    import sys

    code = "import sys; sys.modules['rdkit'] = None; import rnp.analysis.selection; print('ok')"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


# --- the outputs ------------------------------------------------------------------------------
def test_a_run_with_every_status(tmp_path):
    config, compounds, summary = run_all_four(tmp_path)
    assert list(summary) == SUMMARY_KEYS
    assert summary["status"] == "partial"
    assert summary["stage_status"] == "partial"
    assert summary["identity_mode"] == "structure"
    assert summary["run_id"] == "sel_selection"
    run_dir = tmp_path / "results" / "sel_selection"
    assert summary["run_dir"] == str(run_dir)
    assert summary["summary"] == {
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
    }
    assert summary["unresolved"] == [
        {
            "compound_id": "CMP0002",
            "selection_status": "quarantined",
            "issue_codes": ["include_blocked_by_quarantine"],
        },
        {"compound_id": "CMP0004", "selection_status": "needs_review", "issue_codes": []},
    ]
    assert sorted(path.name for path in run_dir.iterdir()) == [
        "run_manifest.json",
        "selected_compounds.tsv",
        "selection_audit.json",
        "selection_decisions.tsv",
    ]
    table = read_tsv(run_dir / "selection_decisions.tsv")
    assert table == expected_rows()
    assert (run_dir / "selection_decisions.tsv").read_text(encoding="utf-8").split("\n")[
        0
    ] == "\t".join(SELECTION_COLUMNS)
    assert read_tsv(run_dir / "selected_compounds.tsv") == [expected_rows()[0]]


def test_a_run_in_which_everything_is_decided_is_complete(tmp_path):
    config, compounds = setup(tmp_path, EVERYTHING_DECIDED)
    summary = select(config, compounds)
    assert (summary["status"], summary["stage_status"], summary["unresolved"]) == (
        "ok",
        "complete",
        [],
    )
    assert summary["summary"]["selected"] == 2 and summary["summary"]["excluded"] == 2
    run_dir = tmp_path / "results" / "sel_selection"
    assert [row["compound_id"] for row in read_tsv(run_dir / "selected_compounds.tsv")] == [
        "CMP0001",
        "CMP0004",
    ]
    manifest = read_json(run_dir / "run_manifest.json")
    assert (manifest["stage_status"], manifest["exit_code"]) == ("complete", 0)


def test_a_partial_run_is_marked_in_its_manifest(tmp_path):
    _, _, summary = run_all_four(tmp_path)
    manifest = read_json(tmp_path / "results" / "sel_selection" / "run_manifest.json")
    assert (manifest["stage_status"], manifest["exit_code"]) == ("partial", 3)


def test_a_name_only_stage_is_selected_without_structure_ids(tmp_path):
    rows = [
        decision("Compound 1", "include"),
        decision("Compound 2", "exclude", reason="not_wanted"),
        decision("Compound 3", "needs_review", reason="ask"),
    ]
    config, compounds = setup(tmp_path, rows, mode="name")
    summary = select(config, compounds)
    assert summary["identity_mode"] == "name_only"
    table = read_tsv(tmp_path / "results" / "sel_selection" / "selection_decisions.tsv")
    assert [row["structure_id"] for row in table] == ["", "", ""]
    assert [row["compound_row_status"] for row in table] == ["name_only"] * 3
    assert [row["selection_status"] for row in table] == ["selected", "excluded", "needs_review"]
    audit = read_json(tmp_path / "results" / "sel_selection" / "selection_audit.json")
    assert audit["identity_mode"] == "name_only"
    assert audit["inputs"]["compounds_stage"]["stage_status"] == "complete"


def test_a_candidate_without_a_decision_is_held_for_review(tmp_path):
    rows = [decision("Compound 1", "include"), decision("Ghost", "include")]
    config, compounds = setup(tmp_path, rows, mode="name")
    summary = select(config, compounds)
    table = read_tsv(tmp_path / "results" / "sel_selection" / "selection_decisions.tsv")
    assert [row["selection_status"] for row in table] == [
        "selected",
        "needs_review",
        "needs_review",
    ]
    assert [row["decision_source"] for row in table] == ["recorded", "not_recorded", "not_recorded"]
    assert [row["issue_codes"] for row in table] == [
        "",
        "no_decision_recorded",
        "no_decision_recorded",
    ]
    assert summary["summary"]["decisions_not_recorded"] == 2
    assert summary["summary"]["decisions_without_compound"] == 1
    audit = read_json(tmp_path / "results" / "sel_selection" / "selection_audit.json")
    assert [(issue["code"], issue["source"], issue["row"]) for issue in audit["issues"]] == [
        ("no_decision_recorded", "compounds", 2),
        ("no_decision_recorded", "compounds", 3),
        ("decision_without_compound", "selection", 2),
    ]


def test_nothing_selected_is_complete_with_a_warning_and_an_empty_list(tmp_path):
    rows = [decision(f"Compound {n}", "exclude", reason="r") for n in (1, 2, 3)]
    config, compounds = setup(tmp_path, rows, mode="name")
    summary = select(config, compounds)
    assert summary["stage_status"] == "complete"
    assert summary["summary"]["selected"] == 0
    run_dir = tmp_path / "results" / "sel_selection"
    assert (run_dir / "selected_compounds.tsv").read_text(encoding="utf-8") == (
        "\t".join(SELECTION_COLUMNS) + "\n"
    )
    audit = read_json(run_dir / "selection_audit.json")
    assert [issue["code"] for issue in audit["issues"]] == ["no_compound_selected"]
    assert audit["issues"][0]["row"] is None


def test_the_audit(tmp_path):
    config, compounds, summary = run_all_four(tmp_path)
    run_dir = tmp_path / "results" / "sel_selection"
    audit = read_json(run_dir / "selection_audit.json")
    jsonschema.validate(audit, load_schema("selection_audit"))
    assert audit["schema_version"] == "1.0"
    assert audit["generated_by"] == "rnp compounds select"
    assert (audit["stage_status"], audit["identity_mode"]) == ("partial", "structure")
    assert audit["config"] == {"path": str(config), "sha256": sha256_file(config)}
    assert audit["inputs"] == {
        "compounds_stage": {
            "dir": str(compounds),
            "audit_sha256": sha256_file(compounds / "compounds_audit.json"),
            "table_sha256": sha256_file(compounds / "compound_structures.tsv"),
            "stage_status": "partial",
        },
        "selection": {
            "path": str(decisions_path(tmp_path)),
            "sha256": sha256_file(decisions_path(tmp_path)),
            "rows": 4,
        },
    }
    assert audit["rule_versions"] == {"selection": "v0.2.0-selection-rules"}
    assert audit["summary"] == summary["summary"]
    assert [
        (issue["code"], issue["source"], issue["row"], issue["compound_id"])
        for issue in audit["issues"]
    ] == [
        ("include_blocked_by_quarantine", "compounds", 2, "CMP0002"),
        ("quarantine_resolved_by_exclusion", "compounds", 3, "CMP0003"),
    ]
    assert all(issue["level"] == "warning" and issue["message"] for issue in audit["issues"])
    assert audit["notes"] == []
    assert audit["selection_decisions_sha256"] == sha256_file(run_dir / "selection_decisions.tsv")
    assert audit["selected_compounds_sha256"] == sha256_file(run_dir / "selected_compounds.tsv")
    assert sorted(audit) == sorted(
        [
            "schema_version",
            "generated_by",
            "stage_status",
            "identity_mode",
            "config",
            "inputs",
            "rule_versions",
            "summary",
            "issues",
            "notes",
            "selection_decisions_sha256",
            "selected_compounds_sha256",
        ]
    )


def test_the_manifest(tmp_path):
    config, compounds, _ = run_all_four(tmp_path)
    manifest = read_json(tmp_path / "results" / "sel_selection" / "run_manifest.json")
    jsonschema.validate(manifest, load_schema("run_manifest"))
    assert manifest["command"] == "compounds select"
    assert manifest["run_id"] == "sel_selection"
    assert manifest["args"] == {
        "config": str(config),
        "compounds": str(compounds),
        "selection": str(decisions_path(tmp_path)),
    }
    assert manifest["parents"] == [
        {
            "stage": "ingest compounds",
            "dir": str(compounds),
            "audit": "compounds_audit.json",
            "audit_sha256": sha256_file(compounds / "compounds_audit.json"),
            "stage_status": "partial",
            "status_override": False,
        }
    ]
    assert [item["path"].replace("\\", "/").rsplit("/", 1)[-1] for item in manifest["inputs"]] == [
        "run.yaml",
        "decisions.tsv",
        "compounds_audit.json",
        "compound_structures.tsv",
    ]
    assert all(item["sha256"] == sha256_file(item["path"]) for item in manifest["inputs"])
    assert manifest["overwritten"] is False
    assert (manifest["started_at_utc"], manifest["finished_at_utc"]) == (NOW, NOW)


def test_the_default_run_id_is_the_clock_and_the_config_hash(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    summary = select(config, compounds, run_id=None)
    assert summary["run_id"] == f"20261110T010000Z_{sha256_file(config)[:8]}_selection"


def test_the_compounds_stage_may_be_given_as_text(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    assert select(config, str(compounds))["stage_status"] == "partial"


def test_columns_that_are_not_known_are_ignored_and_named_in_the_audit(tmp_path):
    from selection_support import COLUMNS

    rows = [decision(f"Compound {n}", "include", note="x", ADMET="y") for n in (1, 2, 3)]
    config = build(tmp_path, rows, mode="name", columns=[*COLUMNS, "note", "ADMET"])
    compounds = stage(config)
    select(config, compounds)
    audit = read_json(tmp_path / "results" / "sel_selection" / "selection_audit.json")
    assert audit["notes"] == [
        {
            "code": "extra_columns_ignored",
            "message": "ignored columns of the selection table: note, ADMET",
        }
    ]


def test_the_rule_versions_of_the_decisions_are_listed_once_each_and_sorted(tmp_path):
    rows = [
        decision("Compound 1", "include", rules="RB-v2"),
        decision("Compound 2", "include", rules="RA-v1"),
        decision("Compound 3", "include", rules="RB-v2"),
    ]
    config, compounds = setup(tmp_path, rows, mode="name")
    assert select(config, compounds)["summary"]["rules_versions"] == ["RA-v1", "RB-v2"]


# --- determinism and side effects ---------------------------------------------------------------
def test_the_same_inputs_give_the_same_bytes_whatever_the_run_id_and_the_clock(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    select(config, compounds, run_id="one")
    select(config, compounds, run_id="two", now=lambda: LATER)
    first = tmp_path / "results" / "one_selection"
    second = tmp_path / "results" / "two_selection"
    for name in ("selection_decisions.tsv", "selected_compounds.tsv", "selection_audit.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    assert read_json(first / "run_manifest.json")["finished_at_utc"] == NOW
    assert read_json(second / "run_manifest.json")["finished_at_utc"] == LATER


def test_the_stage_writes_nothing_but_its_own_directory(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    before = snapshot(tmp_path)
    select(config, compounds)
    after = snapshot(tmp_path)
    added = sorted(set(after) - set(before))
    assert added == [
        "results/sel_selection/run_manifest.json",
        "results/sel_selection/selected_compounds.tsv",
        "results/sel_selection/selection_audit.json",
        "results/sel_selection/selection_decisions.tsv",
    ]
    assert {name: data for name, data in after.items() if name in before} == before


def test_new_decisions_make_a_new_run_of_this_stage_only(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    select(config, compounds, run_id="first")
    before = snapshot(tmp_path / "results")
    write_decisions(decisions_path(tmp_path), EVERYTHING_DECIDED)
    second = select(config, compounds, run_id="second")
    assert second["stage_status"] == "complete"
    after = snapshot(tmp_path / "results")
    assert {name: data for name, data in after.items() if name in before} == before
    assert sorted(set(after) - set(before)) == [
        "second_selection/run_manifest.json",
        "second_selection/selected_compounds.tsv",
        "second_selection/selection_audit.json",
        "second_selection/selection_decisions.tsv",
    ]
    old = read_tsv(tmp_path / "results" / "first_selection" / "selection_decisions.tsv")
    new = read_tsv(tmp_path / "results" / "second_selection" / "selection_decisions.tsv")
    assert [row["selection_status"] for row in old] != [row["selection_status"] for row in new]
    assert old[0]["decision_id"] == new[0]["decision_id"]
    assert old[1]["decision_id"] != new[1]["decision_id"]


# --- refusals ----------------------------------------------------------------------------------
def nothing_selected_was_written(tmp_path):
    results = tmp_path / "results"
    return not any(path.name.endswith("_selection") for path in results.iterdir())


def test_inputs_selection_must_be_set(tmp_path):
    config, compounds = setup(tmp_path, None)
    with pytest.raises(InputError) as caught:
        select(config, compounds)
    assert caught.value.message == (
        "inputs.selection is not set: rnp compounds select needs the table of decisions"
    )
    assert caught.value.details == [
        "add inputs.selection to the run config before the first rnp ingest compounds run: "
        "the stages are tied together by the hash of the run config"
    ]
    assert nothing_selected_was_written(tmp_path)


def test_adding_inputs_selection_after_the_compounds_stage_changes_the_config_hash(tmp_path):
    config, compounds = setup(tmp_path, None)
    write_decisions(decisions_path(tmp_path), ALL_FOUR)
    with config.open("a", encoding="utf-8") as handle:
        handle.write(f"# selection: {decisions_path(tmp_path)}\n")
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "  disease_genes:",
            f"  selection: {decisions_path(tmp_path).as_posix()}\n  disease_genes:",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(InputError) as caught:
        select(config, compounds)
    assert caught.value.message == "run config changed since the compounds stage"


def test_the_decision_table_must_exist(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    decisions_path(tmp_path).unlink()
    with pytest.raises(InputError) as caught:
        select(config, compounds)
    assert caught.value.message == f"inputs.selection is not a file: {decisions_path(tmp_path)}"
    assert nothing_selected_was_written(tmp_path)


def test_an_invalid_decision_table_writes_nothing(tmp_path):
    config, compounds = setup(tmp_path, [decision("Compound 1", "maybe")])
    with pytest.raises(InputError) as caught:
        select(config, compounds)
    assert caught.value.message == "decisions.tsv: the selection table has invalid rows"
    assert nothing_selected_was_written(tmp_path)


def test_a_stage_of_a_changed_compound_table_is_refused(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    with (tmp_path / "inputs" / "compounds.tsv").open("a", encoding="utf-8") as handle:
        handle.write("Another\tall\tother.csv\tCCO\t\n")
    with pytest.raises(InputError) as caught:
        select(config, compounds)
    assert caught.value.message == "the compound table changed since the compounds stage"
    assert caught.value.details == ["re-run rnp ingest compounds so the structures match the table"]
    assert nothing_selected_was_written(tmp_path)


def test_a_stage_of_another_run_config_is_refused(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    with config.open("a", encoding="utf-8") as handle:
        handle.write("# edited\n")
    with pytest.raises(InputError) as caught:
        select(config, compounds)
    assert caught.value.message == "run config changed since the compounds stage"
    assert nothing_selected_was_written(tmp_path)


def test_an_edited_stage_table_is_refused(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    with (compounds / "compound_structures.tsv").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(InputError) as caught:
        select(config, compounds)
    assert caught.value.message == "compound_structures.tsv does not match its audit"
    assert nothing_selected_was_written(tmp_path)


def test_a_missing_or_foreign_stage_directory_is_refused(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    with pytest.raises(InputError) as caught:
        select(config, tmp_path / "nowhere")
    assert caught.value.message == f"compounds stage directory not found: {tmp_path / 'nowhere'}"
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(InputError) as caught:
        select(config, empty)
    assert caught.value.message == f"compounds audit not found: {empty / 'compounds_audit.json'}"


def test_an_existing_run_directory_needs_force(tmp_path):
    config, compounds = setup(tmp_path, ALL_FOUR)
    select(config, compounds)
    with pytest.raises(InputError) as caught:
        select(config, compounds)
    assert "already exists" in caught.value.message
    again = select(config, compounds, force=True)
    assert again["run_id"] == "sel_selection"
    manifest = read_json(tmp_path / "results" / "sel_selection" / "run_manifest.json")
    assert manifest["overwritten"] is True
