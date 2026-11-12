"""`ingest stp --compounds DIR`: the decisions of the compounds stage, applied while it is current.

The compounds stage runs first (`rnp ingest compounds`); `ingest stp` then reads its directory: a
quarantined compound's export is quarantined too, and in structure mode the registered table gets
the columns `structure_id` and `structure_status`. A stage that is not current (changed audit or
table, changed compound table, run config, compound identities or export files) is refused before
anything is written. The structure describer is the fake of structures_support: no RDKit needed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from compounds_support import NAME_COLUMNS
from ingest_link_support import (
    CLEAN,
    MIXED,
    build,
    compounds_stage,
    export_text,
    ingest,
    read_tsv,
)

from rnp.cli import main
from rnp.config import load_schema
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


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def mixed(tmp_path):
    config = build(tmp_path, MIXED)
    return config, compounds_stage(config)


# --- what the stage decides ----------------------------------------------------------------------
def test_the_decisions_of_the_compounds_stage_are_applied(tmp_path):
    config, stage = mixed(tmp_path)
    summary = ingest(config, stage)
    assert list(summary) == SUMMARY_KEYS
    assert summary["status"] == "partial"
    assert summary["stage_status"] == "partial"
    assert summary["run_id"] == "i1"
    assert summary["quarantine"] == [
        {"path": "c2.csv", "sha256": sha256(export_text(2)), "reason": "compound_quarantined"},
        {"path": "c3.csv", "sha256": sha256(export_text(3)), "reason": "compound_quarantined"},
    ]
    assert summary["missing_exports"] == []
    assert summary["summary"] == {
        "files": 4,
        "files_bound": 2,
        "files_quarantined": 2,
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


def test_the_export_of_a_quarantined_compound_gives_no_target(tmp_path):
    config, stage = mixed(tmp_path)
    run_dir = Path(ingest(config, stage)["run_dir"])
    targets = read_tsv(run_dir / "targets.tsv")
    assert {row["source_file"] for row in targets} == {"c1.csv", "c4.csv"}
    assert sorted(row["common_name"] for row in targets) == ["CA2", "EGFR", "TNF"]


def test_the_audit_says_why_the_export_was_not_used(tmp_path):
    config, stage = mixed(tmp_path)
    audit = read_json(Path(ingest(config, stage)["run_dir"]) / "stp_audit.json")
    jsonschema.validate(audit, load_schema("stp_audit"))
    assert audit["schema_version"] == "1.1"
    assert "parents" not in audit
    entries = {entry["path"]: entry for entry in audit["files"]}
    assert sorted(entries) == ["c1.csv", "c2.csv", "c3.csv", "c4.csv"]
    for name, compound_id in (("c2.csv", "CMP0002"), ("c3.csv", "CMP0003")):
        entry = entries[name]
        assert entry["status"] == "quarantined"
        assert entry["reason"] == "compound_quarantined"
        assert entry["format"] == "csv"
        assert entry["compound_id"] == compound_id
        assert entry["group"] == "all"
        assert (entry["rows_total"], entry["rows_used"]) == (0, 0)
    assert entries["c1.csv"]["status"] == "ok" and entries["c4.csv"]["status"] == "ok"
    assert [note["code"] for note in audit["notes"]][-1] == "compounds_stage_applied"
    assert str(stage) in audit["notes"][-1]["message"]


def test_the_registered_table_gets_the_structure_columns(tmp_path):
    config, stage = mixed(tmp_path)
    run_dir = Path(ingest(config, stage)["run_dir"])
    path = run_dir / "compounds_registered.tsv"
    assert path.read_text(encoding="utf-8").splitlines()[0] == "\t".join(
        [*REGISTERED_COLUMNS, "structure_id", "structure_status"]
    )
    rows = read_tsv(path)
    assert [(r["compound_id"], r["structure_id"], r["structure_status"]) for r in rows] == [
        ("CMP0001", "STR0001", "registered"),
        ("CMP0002", "STR0002", "registered"),
        ("CMP0003", "", "not_registered"),
        ("CMP0004", "STR0003", "registered"),
    ]
    audit = read_json(run_dir / "stp_audit.json")
    assert audit["compounds_registered_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert audit["summary"]["compounds_registered"] == 4


def test_the_manifest_names_the_compounds_stage_as_its_parent(tmp_path):
    config, stage = mixed(tmp_path)
    run_dir = Path(ingest(config, stage)["run_dir"])
    manifest = read_json(run_dir / "run_manifest.json")
    jsonschema.validate(manifest, load_schema("run_manifest"))
    audit = stage / "compounds_audit.json"
    assert manifest["command"] == "ingest stp"
    assert manifest["stage_status"] == "partial" and manifest["exit_code"] == 3
    assert manifest["parents"] == [
        {
            "stage": "ingest compounds",
            "dir": str(stage),
            "audit": "compounds_audit.json",
            "audit_sha256": hashlib.sha256(audit.read_bytes()).hexdigest(),
            "stage_status": "partial",
            "status_override": False,
        }
    ]
    assert manifest["args"]["compounds"] == str(stage)
    names = [Path(item["path"]).name for item in manifest["inputs"]]
    assert names == [
        "run.yaml",
        "compounds.tsv",
        "c1.csv",
        "c2.csv",
        "c3.csv",
        "c4.csv",
        "compounds_audit.json",
        "compound_structures.tsv",
    ]
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 0


def test_the_identity_registry_is_written_as_without_the_option(tmp_path):
    config, stage = mixed(tmp_path)
    registry = tmp_path / "results" / "registry" / "compound_registry.tsv"
    ingest(config, stage)
    assert [row["compound_id"] for row in read_tsv(registry)] == [
        "CMP0001",
        "CMP0002",
        "CMP0003",
        "CMP0004",
    ]


def test_a_clean_stage_changes_nothing_but_the_two_columns(tmp_path):
    config = build(tmp_path, CLEAN)
    stage = compounds_stage(config)
    linked = ingest(config, stage)
    plain = ingest(config, run_id="plain")
    assert linked["stage_status"] == plain["stage_status"] == "complete"
    assert linked["summary"] == plain["summary"]
    assert linked["quarantine"] == plain["quarantine"] == []
    linked_dir, plain_dir = Path(linked["run_dir"]), Path(plain["run_dir"])
    assert (linked_dir / "targets.tsv").read_bytes() == (plain_dir / "targets.tsv").read_bytes()
    kept = [
        {key: row[key] for key in REGISTERED_COLUMNS}
        for row in read_tsv(linked_dir / "compounds_registered.tsv")
    ]
    assert kept == read_tsv(plain_dir / "compounds_registered.tsv")
    audits = [read_json(directory / "stp_audit.json") for directory in (linked_dir, plain_dir)]
    for audit in audits:
        for key in ("notes", "compounds_registered_sha256"):
            audit.pop(key)
    assert audits[0] == audits[1]


def test_a_name_only_stage_is_accepted_and_adds_no_columns(tmp_path):
    config = build(tmp_path, [("", None), ("", None)], columns=NAME_COLUMNS)
    stage = compounds_stage(config)
    summary = ingest(config, stage)
    assert summary["stage_status"] == "complete"
    assert summary["quarantine"] == []
    run_dir = Path(summary["run_dir"])
    header = (run_dir / "compounds_registered.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "\t".join(REGISTERED_COLUMNS)
    manifest = read_json(run_dir / "run_manifest.json")
    assert [(p["stage"], p["stage_status"]) for p in manifest["parents"]] == [
        ("ingest compounds", "complete")
    ]


def test_the_directory_may_be_given_as_text(tmp_path):
    config, stage = mixed(tmp_path)
    assert ingest(config, str(stage))["stage_status"] == "partial"


def test_an_export_of_a_quarantined_compound_may_change_after_the_stage(tmp_path):
    config, stage = mixed(tmp_path)
    (tmp_path / "inputs" / "stp" / "c2.csv").write_bytes(export_text(4).encode("utf-8"))
    summary = ingest(config, stage)
    assert summary["stage_status"] == "partial"
    assert summary["quarantine"][0] == {
        "path": "c2.csv",
        "sha256": sha256(export_text(4)),
        "reason": "compound_quarantined",
    }


def test_when_every_compound_is_quarantined_nothing_is_usable(tmp_path):
    config = build(tmp_path, [("", None), ("", None)])
    stage = compounds_stage(config)
    with pytest.raises(RnpError) as caught:
        ingest(config, stage)
    assert caught.value.exit_code == 2
    assert caught.value.message == "ingest produced no usable export"
    assert not (tmp_path / "results" / "i1").exists()


# --- a stage that is not current is refused ------------------------------------------------------
def refused(tmp_path, config, stage, fragment):
    registry = tmp_path / "results" / "registry" / "compound_registry.tsv"
    before = registry.read_bytes()
    with pytest.raises(RnpError) as caught:
        ingest(config, stage)
    assert caught.value.exit_code == 2
    assert fragment in caught.value.message
    assert not (tmp_path / "results" / "i1").exists()
    assert registry.read_bytes() == before
    return caught.value


def test_a_directory_that_does_not_exist_is_refused(tmp_path):
    config, _ = mixed(tmp_path)
    refused(tmp_path, config, tmp_path / "nowhere", "compounds stage directory not found")


def test_a_file_instead_of_a_directory_is_refused(tmp_path):
    config, _ = mixed(tmp_path)
    refused(tmp_path, config, tmp_path / "run.yaml", "compounds stage directory not found")


def test_a_stage_without_its_audit_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    (stage / "compounds_audit.json").unlink()
    refused(tmp_path, config, stage, "compounds audit not found")


def test_an_audit_that_does_not_fit_its_schema_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    audit = read_json(stage / "compounds_audit.json")
    audit["identity_mode"] = "something else"
    (stage / "compounds_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    refused(tmp_path, config, stage, "compounds audit")


def test_a_stage_without_its_table_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    (stage / "compound_structures.tsv").unlink()
    refused(tmp_path, config, stage, "compounds stage table not found")


def test_a_table_that_changed_after_the_stage_wrote_it_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    table = stage / "compound_structures.tsv"
    text = table.read_text(encoding="utf-8").replace("not_registered", "registered")
    table.write_bytes(text.encode("utf-8"))
    refused(tmp_path, config, stage, "compound_structures.tsv does not match its audit")


def retable(stage, change):
    """Rewrite the stage table and keep the audit consistent with it: a stage edited with care."""
    table = stage / "compound_structures.tsv"
    table.write_bytes(change(table.read_text(encoding="utf-8")).encode("utf-8"))
    audit = read_json(stage / "compounds_audit.json")
    audit["compound_structures_sha256"] = hashlib.sha256(table.read_bytes()).hexdigest()
    (stage / "compounds_audit.json").write_text(json.dumps(audit), encoding="utf-8")


def test_a_table_with_rows_that_do_not_fit_their_schema_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    retable(stage, lambda text: text.replace("accepted", "weird", 1))
    error = refused(tmp_path, config, stage, "compound_structures.tsv is not valid")
    assert error.details[0].startswith("row 1: ")


def test_a_table_with_another_number_of_rows_than_the_compound_table_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    retable(stage, lambda text: "\n".join(text.split("\n")[:-2]) + "\n")
    error = refused(
        tmp_path, config, stage, "the compounds stage does not match the compound table"
    )
    assert error.details == ["3 rows in the stage, 4 compounds now"]


@pytest.mark.parametrize(
    "kind, status", [("unstated", "verified_kind_unstated"), ("reconstructed", "reconstructed")]
)
def test_the_export_of_every_kind_of_verified_submission_is_checked_again(tmp_path, kind, status):
    config = build(tmp_path, [("CCO", kind), ("CCN", None)])
    stage = compounds_stage(config)
    assert read_tsv(stage / "compound_structures.tsv")[0]["submission_status"] == status
    (tmp_path / "inputs" / "stp" / "c1.csv").write_bytes(export_text(3).encode("utf-8"))
    refused(tmp_path, config, stage, "an export changed since the compounds stage")


def test_a_compound_table_that_changed_after_the_stage_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    with (tmp_path / "inputs" / "compounds.tsv").open("ab") as handle:
        handle.write(b"Compound 5\tall\tc5.csv\tCCCCC\t\n")
    refused(tmp_path, config, stage, "the compound table changed since the compounds stage")


def test_a_run_config_that_changed_after_the_stage_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data["thresholds"]["stp_probability"] = 0.2
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    refused(tmp_path, config, stage, "run config changed since the compounds stage")


def test_compound_identities_that_changed_after_the_stage_are_refused(tmp_path):
    config, stage = mixed(tmp_path)
    registry = tmp_path / "results" / "registry" / "compound_registry.tsv"
    text = registry.read_text(encoding="utf-8").replace("CMP0001", "CMP0007", 1)
    registry.write_bytes(text.encode("utf-8"))
    error = refused(
        tmp_path, config, stage, "the compounds stage does not match the compound identities"
    )
    assert error.details[0].startswith("row 1: compound_id is ")
    assert "'CMP0007'" in error.details[0] and "'CMP0001'" in error.details[0]


def test_an_export_that_changed_after_the_stage_checked_it_is_refused(tmp_path):
    config, stage = mixed(tmp_path)
    (tmp_path / "inputs" / "stp" / "c1.csv").write_bytes(export_text(3).encode("utf-8"))
    error = refused(tmp_path, config, stage, "an export changed since the compounds stage")
    assert error.details[0].startswith("c1.csv: ")
    assert sha256(export_text(3)) in error.details[0]
    assert sha256(export_text(1)) in error.details[0]


def test_a_directory_without_a_compounds_stage_is_refused(tmp_path):
    config, _ = mixed(tmp_path)
    refused(tmp_path, config, tmp_path / "results", "compounds audit not found")
