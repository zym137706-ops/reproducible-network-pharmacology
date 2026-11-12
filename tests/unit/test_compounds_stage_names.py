"""The compounds stage in name-only mode: a compound table without a smiles column.

The stage registers the compound identities, writes `compound_structures.tsv`,
`compounds_audit.json` and `run_manifest.json` into `<outputs.dir>/<run id>_compounds/` and
persists the identity registry.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from compounds_support import (
    NAME_COLUMNS,
    TABLE_COLUMNS,
    compound_row,
    read_json,
    run,
    write_config,
)
from jsonschema import Draft202012Validator
from structures_support import NOW

from rnp.analysis import compounds as stage_module
from rnp.config import load_config, load_schema
from rnp.errors import InputError, SchemaViolation
from rnp.io.tables import read_table

SUMMARY_FIELDS = [
    "rows",
    "rows_accepted",
    "rows_quarantined",
    "rows_name_only",
    "structures_new",
    "structures_reused",
    "structures_superseded",
    "submissions_verified",
    "submissions_reconstructed",
    "submissions_not_recorded",
    "submissions_rejected",
    "errors",
    "warnings",
]


def three():
    return [compound_row(1), compound_row(2), compound_row(3)]


def set_up(tmp_path, rows=None, columns=None, **kwargs):
    config = write_config(
        tmp_path, rows if rows is not None else three(), columns=columns or NAME_COLUMNS, **kwargs
    )
    return config, tmp_path / "results" / "r1_compounds"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_name_only_run_returns_its_summary_and_writes_three_files(tmp_path):
    config, run_dir = set_up(tmp_path)
    summary = run(config)
    assert list(summary) == [
        "status",
        "stage_status",
        "identity_mode",
        "run_id",
        "run_dir",
        "summary",
        "quarantine",
    ]
    assert summary["status"] == "ok"
    assert summary["stage_status"] == "complete"
    assert summary["identity_mode"] == "name_only"
    assert summary["run_id"] == "r1_compounds"
    assert Path(summary["run_dir"]).resolve() == run_dir.resolve()
    assert summary["quarantine"] == []
    assert list(summary["summary"]) == SUMMARY_FIELDS
    assert summary["summary"] == {
        "rows": 3,
        "rows_accepted": 0,
        "rows_quarantined": 0,
        "rows_name_only": 3,
        "structures_new": 0,
        "structures_reused": 0,
        "structures_superseded": 0,
        "submissions_verified": 0,
        "submissions_reconstructed": 0,
        "submissions_not_recorded": 0,
        "submissions_rejected": 0,
        "errors": 0,
        "warnings": 0,
    }
    assert sorted(path.name for path in run_dir.iterdir()) == [
        "compound_structures.tsv",
        "compounds_audit.json",
        "run_manifest.json",
    ]


def test_the_table_has_one_name_only_row_per_compound(tmp_path):
    config, run_dir = set_up(tmp_path)
    run(config)
    table = run_dir / "compound_structures.tsv"
    raw = table.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n") and not raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8").splitlines()[0] == "\t".join(TABLE_COLUMNS)
    rows = read_table(table)
    assert [row["compound_id"] for row in rows] == ["CMP0001", "CMP0002", "CMP0003"]
    assert rows[1] == {
        "compound_id": "CMP0002",
        "group": "all",
        "name": "Compound 2",
        "stp_file": "c2.xlsx",
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
    }


def test_the_audit_of_a_name_only_run(tmp_path):
    config, run_dir = set_up(tmp_path)
    run(config)
    audit = read_json(run_dir / "compounds_audit.json")
    Draft202012Validator(load_schema("compounds_audit")).validate(audit)
    assert list(audit) == [
        "schema_version",
        "generated_by",
        "stage_status",
        "identity_mode",
        "config",
        "inputs",
        "toolkit",
        "rule_versions",
        "summary",
        "issues",
        "registries",
        "notes",
        "compound_structures_sha256",
    ]
    assert audit["schema_version"] == "1.0"
    assert audit["generated_by"] == "rnp ingest compounds"
    assert audit["stage_status"] == "complete"
    assert audit["identity_mode"] == "name_only"
    assert audit["config"] == {"path": str(load_config(config).path), "sha256": sha256(config)}
    compounds = tmp_path / "inputs" / "compounds.tsv"
    assert audit["inputs"] == {
        "compounds": {"path": str(compounds), "sha256": sha256(compounds), "rows": 3},
        "submission_log": None,
        "stp_dir": None,
    }
    assert audit["toolkit"] is None
    assert audit["rule_versions"] == {
        "compound_identity": "v0.1.0-name-registry",
        "structure_identity": None,
        "submission_binding": None,
    }
    assert list(audit["summary"]) == SUMMARY_FIELDS
    assert audit["issues"] == []
    registry = tmp_path / "results" / "registry" / "compound_registry.tsv"
    assert audit["registries"] == {
        "compound_registry": {
            "path": str(registry),
            "rule_version": "v0.1.0-name-registry",
            "entries": 3,
        },
        "structure_registry": None,
    }
    assert [note["code"] for note in audit["notes"]] == [
        "compound_registered",
        "compound_registered",
        "compound_registered",
        "registry_created",
    ]
    assert audit["compound_structures_sha256"] == sha256(run_dir / "compound_structures.tsv")


def test_the_manifest_of_a_name_only_run(tmp_path):
    config, run_dir = set_up(tmp_path)
    run(config)
    manifest = read_json(run_dir / "run_manifest.json")
    Draft202012Validator(load_schema("run_manifest")).validate(manifest)
    assert manifest["command"] == "ingest compounds"
    assert manifest["run_id"] == "r1_compounds"
    assert manifest["stage_status"] == "complete"
    assert manifest["exit_code"] == 0
    assert manifest["parents"] == []
    assert manifest["overwritten"] is False
    assert manifest["started_at_utc"] == NOW and manifest["finished_at_utc"] == NOW
    assert manifest["args"] == {
        "config": str(load_config(config).path),
        "identity_mode": "name_only",
        "species": "Homo_sapiens",
        "allow_filename_match": False,
        "submission_log": None,
    }
    assert [Path(item["path"]).name for item in manifest["inputs"]] == ["run.yaml", "compounds.tsv"]
    assert manifest["inputs"][1]["sha256"] == sha256(tmp_path / "inputs" / "compounds.tsv")


def test_the_identity_registry_is_persisted_after_the_run(tmp_path):
    config, _ = set_up(tmp_path)
    run(config)
    registry = tmp_path / "results" / "registry"
    rows = read_table(registry / "compound_registry.tsv")
    assert [row["compound_id"] for row in rows] == ["CMP0001", "CMP0002", "CMP0003"]
    assert [row["name"] for row in rows] == ["Compound 1", "Compound 2", "Compound 3"]
    assert {row["status"] for row in rows} == {"active"}
    assert {row["rule_version"] for row in rows} == {"v0.1.0-name-registry"}
    assert not (registry / "structure_registry.tsv").exists()


def test_a_second_run_reuses_the_identities_and_registers_nothing_new(tmp_path):
    config, run_dir = set_up(tmp_path)
    run(config)
    first = read_table(run_dir / "compound_structures.tsv")
    summary = run(config, run_id="r2")
    second_dir = tmp_path / "results" / "r2_compounds"
    assert read_table(second_dir / "compound_structures.tsv") == first
    assert read_json(second_dir / "compounds_audit.json")["notes"] == []
    assert summary["summary"]["rows_name_only"] == 3
    assert run_dir.is_dir()


def test_a_new_compound_gets_the_next_identity(tmp_path):
    config, _ = set_up(tmp_path)
    run(config)
    write_config(tmp_path, [*three(), compound_row(4)], columns=NAME_COLUMNS)
    run(config, run_id="r2")
    rows = read_table(tmp_path / "results" / "r2_compounds" / "compound_structures.tsv")
    assert [row["compound_id"] for row in rows] == ["CMP0001", "CMP0002", "CMP0003", "CMP0004"]


def test_the_same_inputs_give_the_same_table_and_audit(tmp_path):
    config, _ = set_up(tmp_path)
    run(config, run_id="a")
    first = tmp_path / "results" / "a_compounds"
    shutil.rmtree(tmp_path / "results" / "registry")
    run(config, run_id="b")
    second = tmp_path / "results" / "b_compounds"
    for name in ("compound_structures.tsv", "compounds_audit.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


@pytest.mark.parametrize("key", ["submission_log", "structure_registry"])
def test_name_only_mode_refuses_inputs_that_need_structures(tmp_path, key):
    config, _ = set_up(tmp_path, inputs={key: str(tmp_path / "x.tsv")})
    with pytest.raises(InputError) as caught:
        run(config)
    assert key in " ".join([caught.value.message, *caught.value.details])
    assert caught.value.exit_code == 2
    assert not (tmp_path / "results").exists()


def test_name_only_mode_names_every_input_that_needs_structures(tmp_path):
    config, _ = set_up(
        tmp_path,
        inputs={
            "submission_log": str(tmp_path / "x.tsv"),
            "structure_registry": str(tmp_path / "y.tsv"),
        },
    )
    with pytest.raises(InputError) as caught:
        run(config)
    assert caught.value.message == (
        "the compound table has no smiles column, so the stage runs in name-only mode"
    )
    tail = "is only used in structure mode: remove it or add a smiles column"
    assert caught.value.details == [
        f"inputs.submission_log {tail}",
        f"inputs.structure_registry {tail}",
    ]


@pytest.mark.parametrize(
    "rows",
    [
        [compound_row(1), compound_row(1, stp_file="other.xlsx")],
        [compound_row(1, stp_file=""), compound_row(2)],
        [compound_row(1), compound_row(2, stp_file="c1.xlsx")],
        [],
    ],
    ids=["duplicate_name", "no_stp_file", "shared_export", "empty_table"],
)
def test_a_table_level_problem_writes_nothing(tmp_path, rows):
    config, _ = set_up(tmp_path, rows)
    with pytest.raises(InputError):
        run(config)
    assert not (tmp_path / "results").exists()


def test_the_filename_compatibility_mode_is_accepted(tmp_path):
    config, run_dir = set_up(
        tmp_path,
        [compound_row(1, stp_file=""), compound_row(2, stp_file="")],
        inputs={"allow_filename_match": True},
    )
    summary = run(config)
    assert summary["stage_status"] == "complete"
    assert [row["stp_file"] for row in read_table(run_dir / "compound_structures.tsv")] == ["", ""]


def test_an_existing_run_directory_is_not_replaced_without_force(tmp_path):
    config, run_dir = set_up(tmp_path)
    run(config)
    registry = tmp_path / "results" / "registry" / "compound_registry.tsv"
    before = registry.read_bytes()
    (run_dir / "marker.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(InputError):
        run(config)
    assert (run_dir / "marker.txt").exists()
    assert registry.read_bytes() == before
    run(config, force=True)
    assert not (run_dir / "marker.txt").exists()
    assert read_json(run_dir / "run_manifest.json")["overwritten"] is True


def test_a_failing_run_leaves_no_directory_and_no_registry(tmp_path, monkeypatch):
    config, _ = set_up(tmp_path)

    def explode(path, rows):
        raise RuntimeError("boom")

    monkeypatch.setattr(stage_module, "write_structures_table", explode)
    with pytest.raises(RuntimeError):
        run(config)
    assert not any((tmp_path / "results").rglob("*"))


def test_the_default_run_id_names_the_time_the_config_and_the_stage(tmp_path):
    config, _ = set_up(tmp_path)
    summary = run(config, run_id=None)
    assert summary["run_id"] == f"20261110T010000Z_{sha256(config)[:8]}_compounds"
    assert (tmp_path / "results" / summary["run_id"]).is_dir()


def test_an_explicit_run_id_gets_the_stage_suffix(tmp_path):
    config, _ = set_up(tmp_path)
    assert run(config, run_id="abc")["run_id"] == "abc_compounds"
    assert (tmp_path / "results" / "abc_compounds").is_dir()


def test_the_identity_registry_can_be_placed_elsewhere(tmp_path):
    elsewhere = tmp_path / "elsewhere" / "ids.tsv"
    config, run_dir = set_up(tmp_path, inputs={"compound_registry": str(elsewhere)})
    run(config)
    assert len(read_table(elsewhere)) == 3
    assert not (tmp_path / "results" / "registry").exists()
    audit = read_json(run_dir / "compounds_audit.json")
    assert audit["registries"]["compound_registry"]["path"] == str(elsewhere)


def test_an_explicit_compound_id_is_kept(tmp_path):
    rows = [compound_row(1, compound_id="CMP0100"), compound_row(2, compound_id="CMP0101")]
    config, run_dir = set_up(tmp_path, rows, columns=[*NAME_COLUMNS, "compound_id"])
    run(config)
    table = read_table(run_dir / "compound_structures.tsv")
    assert [row["compound_id"] for row in table] == ["CMP0100", "CMP0101"]


def test_two_rows_that_resolve_to_one_identity_write_nothing(tmp_path):
    config, _ = set_up(tmp_path)
    run(config)
    registry = tmp_path / "results" / "registry" / "compound_registry.tsv"
    before = registry.read_bytes()
    # Compound 1 is now bound to another export and Compound 4 takes over its old export: the
    # first row matches the registered identity by name, the second one by export file.
    set_up(tmp_path, [compound_row(1, stp_file="other.xlsx"), compound_row(4, stp_file="c1.xlsx")])
    with pytest.raises(InputError) as caught:
        run(config, run_id="r2")
    assert caught.value.exit_code == 2
    assert caught.value.message == "the identity registry gave one compound_id to more than one row"
    assert caught.value.details == ["CMP0001: rows 1, 2"]
    assert registry.read_bytes() == before
    assert sorted(path.name for path in (tmp_path / "results").iterdir()) == [
        "r1_compounds",
        "registry",
    ]


def test_a_table_without_a_group_column_puts_every_compound_in_the_group_all(tmp_path):
    config, run_dir = set_up(tmp_path, columns=["name", "stp_file"])
    run(config)
    table = read_table(run_dir / "compound_structures.tsv")
    assert {row["group"] for row in table} == {"all"}


def test_an_inconsistency_found_by_the_self_check_is_an_internal_error(tmp_path, monkeypatch):
    config, _ = set_up(tmp_path)
    monkeypatch.setattr(
        stage_module, "check_summary", lambda *args, **kwargs: ["the parts disagree"]
    )
    with pytest.raises(SchemaViolation) as caught:
        run(config)
    assert caught.value.exit_code == 1
    assert caught.value.message == "the compounds stage is internally inconsistent"
    assert not (tmp_path / "results").exists()
