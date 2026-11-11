"""The compounds stage in structure mode: a compound table with a smiles column.

The RDKit adapter is replaced by the fake `Describer` of structures_support, so none of these
tests needs RDKit. The scenario has one compound of every kind (compounds_support.six_compounds).
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import pytest
from compounds_support import (
    STRUCTURE_COLUMNS,
    TABLE_COLUMNS,
    compound_row,
    read_json,
    run,
    six_compounds,
    six_log,
    write_config,
    write_exports,
)
from jsonschema import Draft202012Validator
from structures_support import (
    LATER,
    NOW,
    TOOLKIT_VERSION,
    fake_key,
    log_row,
    write_text,
    write_tsv,
)

from rnp.analysis import compounds as stage_module
from rnp.analysis.compounds import run_compounds
from rnp.config import load_config, load_schema
from rnp.errors import InputError, SchemaViolation
from rnp.io.tables import read_table
from rnp.structures import ChemUnavailable, read_registry

SUMMARY = {
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_rows(digests):
    def row(number, group, **fields):
        base = {
            "compound_id": f"CMP{number:04d}",
            "group": group,
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
            1, "g1", structure_id="STR0001", smiles="CCO", export_kind="native_export",
            export_sha256=digests[1],
        ),
        row(
            2, "g1", structure_id="STR0002", smiles="CCN", submission_status="not_recorded",
            issue_codes="submission_record_missing",
        ),
        row(
            3, "g2", structure_id="STR0003", smiles="CCC", row_status="quarantined",
            submission_status="rejected", export_sha256=digests[3],
            issue_codes="submission_hash_mismatch",
        ),
        row(
            4, "g2", row_status="quarantined", structure_status="not_registered",
            stereo_status="", submission_status="not_checked", issue_codes="missing_structure",
        ),
        row(
            5, "g2", row_status="quarantined", structure_status="not_registered",
            stereo_status="", submission_status="not_checked", issue_codes="invalid_smiles",
        ),
        row(
            6, "g1", structure_id="STR0004", smiles="CCCC", stereo_status="undefined",
            submission_status="reconstructed", export_kind="reconstructed_from_result_page",
            export_sha256=digests[6],
            issue_codes="stereo_undefined;submission_export_reconstructed",
        ),
    ]  # fmt: skip


def view(issue):
    return (issue["source"], issue["row"], issue["level"], issue["code"], issue["compound_id"])


def six(tmp_path, **kwargs):
    digests = write_exports(tmp_path)
    config = write_config(tmp_path, six_compounds(), log_rows=six_log(digests), **kwargs)
    return config, digests, tmp_path / "results" / "r1_compounds"


def two(tmp_path, log_rows=None, numbers=(1, 2), **kwargs):
    digests = write_exports(tmp_path, numbers)
    rows = [compound_row(1, "CCO"), compound_row(2, "CCN")]
    config = write_config(
        tmp_path, rows, log_rows=log_rows(digests) if log_rows else None, **kwargs
    )
    return config, digests, tmp_path / "results" / "r1_compounds"


# --- the scenario with a log: table, summary, audit and manifest ----------------------------------
def test_the_table_of_the_scenario(tmp_path):
    config, digests, run_dir = six(tmp_path)
    run(config)
    table = run_dir / "compound_structures.tsv"
    assert table.read_bytes().decode("utf-8").splitlines()[0] == "\t".join(TABLE_COLUMNS)
    assert read_table(table) == expected_rows(digests)


def test_the_summary_of_the_scenario(tmp_path):
    config, _, run_dir = six(tmp_path)
    summary = run(config)
    assert summary["status"] == "partial"
    assert summary["stage_status"] == "partial"
    assert summary["identity_mode"] == "structure"
    assert summary["run_id"] == "r1_compounds"
    assert Path(summary["run_dir"]).resolve() == run_dir.resolve()
    assert summary["summary"] == SUMMARY
    assert summary["quarantine"] == [
        {"compound_id": "CMP0003", "issue_codes": ["submission_hash_mismatch"]},
        {"compound_id": "CMP0004", "issue_codes": ["missing_structure"]},
        {"compound_id": "CMP0005", "issue_codes": ["invalid_smiles"]},
    ]


def test_the_audit_of_the_scenario(tmp_path):
    config, digests, run_dir = six(tmp_path)
    run(config)
    audit = read_json(run_dir / "compounds_audit.json")
    Draft202012Validator(load_schema("compounds_audit")).validate(audit)
    assert audit["stage_status"] == "partial"
    assert audit["identity_mode"] == "structure"
    assert audit["config"]["sha256"] == sha256(config)
    inputs = tmp_path / "inputs"
    assert audit["inputs"] == {
        "compounds": {
            "path": str(inputs / "compounds.tsv"),
            "sha256": sha256(inputs / "compounds.tsv"),
            "rows": 6,
        },
        "submission_log": {
            "path": str(inputs / "log.tsv"),
            "sha256": sha256(inputs / "log.tsv"),
            "rows": 4,
        },
        "stp_dir": {"path": str(inputs / "stp"), "files_hashed": 3},
    }
    assert audit["toolkit"] == {"name": "rdkit", "version": TOOLKIT_VERSION}
    assert audit["rule_versions"] == {
        "compound_identity": "v0.1.0-name-registry",
        "structure_identity": "v0.2.0-structure-registry",
        "submission_binding": "v0.2.0-submission-binding",
    }
    assert audit["summary"] == SUMMARY
    assert [view(issue) for issue in audit["issues"]] == [
        ("compounds", 2, "warning", "submission_record_missing", "CMP0002"),
        ("compounds", 4, "error", "missing_structure", "CMP0004"),
        ("compounds", 5, "error", "invalid_smiles", "CMP0005"),
        ("compounds", 6, "warning", "stereo_undefined", "CMP0006"),
        ("submission_log", 2, "error", "submission_hash_mismatch", "CMP0003"),
        ("submission_log", 3, "warning", "submission_export_reconstructed", "CMP0006"),
        ("submission_log", 4, "warning", "log_row_without_compound", ""),
    ]
    assert list(audit["issues"][0]) == ["level", "code", "source", "row", "compound_id", "message"]
    assert all(issue["message"] for issue in audit["issues"])
    registries = tmp_path / "results" / "registry"
    assert audit["registries"] == {
        "compound_registry": {
            "path": str(registries / "compound_registry.tsv"),
            "rule_version": "v0.1.0-name-registry",
            "entries": 6,
        },
        "structure_registry": {
            "path": str(registries / "structure_registry.tsv"),
            "rule_version": "v0.2.0-structure-registry",
            "entries": 4,
        },
    }
    assert [note["code"] for note in audit["notes"]] == ["compound_registered"] * 6 + [
        "registry_created"
    ]
    assert audit["compound_structures_sha256"] == sha256(run_dir / "compound_structures.tsv")
    assert digests[1] in (run_dir / "compound_structures.tsv").read_text(encoding="utf-8")


def test_the_manifest_of_the_scenario(tmp_path):
    config, _, run_dir = six(tmp_path)
    run(config)
    manifest = read_json(run_dir / "run_manifest.json")
    Draft202012Validator(load_schema("run_manifest")).validate(manifest)
    assert manifest["command"] == "ingest compounds"
    assert manifest["run_id"] == "r1_compounds"
    assert manifest["stage_status"] == "partial"
    assert manifest["exit_code"] == 3
    assert manifest["parents"] == []
    assert manifest["args"] == {
        "config": str(load_config(config).path),
        "identity_mode": "structure",
        "species": "Homo_sapiens",
        "allow_filename_match": False,
        "submission_log": str(tmp_path / "inputs" / "log.tsv"),
    }
    assert [Path(item["path"]).name for item in manifest["inputs"]] == [
        "run.yaml",
        "compounds.tsv",
        "log.tsv",
        "c1.xlsx",
        "c3.xlsx",
        "c6.xlsx",
    ]


def test_the_registries_are_persisted(tmp_path):
    config, _, _ = six(tmp_path)
    run(config)
    registries = tmp_path / "results" / "registry"
    structures = read_registry(registries / "structure_registry.tsv")
    assert [(row["structure_id"], row["compound_id"], row["smiles"]) for row in structures] == [
        ("STR0001", "CMP0001", "CCO"),
        ("STR0002", "CMP0002", "CCN"),
        ("STR0003", "CMP0003", "CCC"),
        ("STR0004", "CMP0006", "CCCC"),
    ]
    assert {row["first_seen_utc"] for row in structures} == {NOW}
    assert {row["last_seen_utc"] for row in structures} == {NOW}
    assert {row["toolkit_version"] for row in structures} == {TOOLKIT_VERSION}
    assert {row["status"] for row in structures} == {"current"}
    identities = read_table(registries / "compound_registry.tsv")
    assert [row["compound_id"] for row in identities] == [f"CMP{n:04d}" for n in range(1, 7)]


# --- a second run ---------------------------------------------------------------------------------
def test_a_second_run_reuses_the_structures(tmp_path):
    config, _, run_dir = six(tmp_path)
    run(config)
    summary = run(config, run_id="r2", now=lambda: LATER)
    second = tmp_path / "results" / "r2_compounds"
    assert read_table(second / "compound_structures.tsv") == read_table(
        run_dir / "compound_structures.tsv"
    )
    assert summary["summary"]["structures_new"] == 0
    assert summary["summary"]["structures_reused"] == 4
    assert read_json(second / "compounds_audit.json")["notes"] == []
    structures = read_registry(tmp_path / "results" / "registry" / "structure_registry.tsv")
    assert {row["first_seen_utc"] for row in structures} == {NOW}
    assert {row["last_seen_utc"] for row in structures} == {LATER}


def test_a_changed_structure_supersedes_the_old_one_and_the_old_submission_is_refused(tmp_path):
    config, digests, _ = six(tmp_path)
    run(config)
    rows = six_compounds()
    rows[0]["smiles"] = "CCCO"
    write_tsv(
        tmp_path / "inputs" / "compounds.tsv",
        STRUCTURE_COLUMNS,
        [{column: row[column] for column in STRUCTURE_COLUMNS} for row in rows],
    )
    summary = run(config, run_id="r2", now=lambda: LATER)
    table = read_table(tmp_path / "results" / "r2_compounds" / "compound_structures.tsv")
    assert table[0] == {
        "compound_id": "CMP0001",
        "group": "g1",
        "name": "Compound 1",
        "stp_file": "c1.xlsx",
        "row_status": "quarantined",
        "structure_status": "registered",
        "structure_id": "STR0005",
        "smiles": "CCCO",
        "inchikey": fake_key("CCCO"),
        "stereo_status": "none_present",
        "submission_status": "rejected",
        "export_kind": "",
        "export_sha256": digests[1],
        "issue_codes": "structure_changed;submission_structure_mismatch",
    }
    assert summary["summary"] == {
        "rows": 6,
        "rows_accepted": 2,
        "rows_quarantined": 4,
        "rows_name_only": 0,
        "structures_new": 1,
        "structures_reused": 3,
        "structures_superseded": 1,
        "submissions_verified": 0,
        "submissions_reconstructed": 1,
        "submissions_not_recorded": 1,
        "submissions_rejected": 2,
        "errors": 4,
        "warnings": 5,
    }
    registry = {
        row["structure_id"]: row
        for row in read_registry(tmp_path / "results" / "registry" / "structure_registry.tsv")
    }
    assert (registry["STR0001"]["status"], registry["STR0001"]["superseded_by"]) == (
        "superseded",
        "STR0005",
    )
    assert (registry["STR0005"]["status"], registry["STR0005"]["smiles"]) == ("current", "CCCO")


# --- without a submission log ---------------------------------------------------------------------
def test_without_a_log_every_registered_structure_is_not_recorded_and_that_is_no_error(tmp_path):
    config, _, run_dir = two(tmp_path)
    summary = run(config)
    assert summary["stage_status"] == "complete"
    assert summary["status"] == "ok"
    assert summary["quarantine"] == []
    table = read_table(run_dir / "compound_structures.tsv")
    assert [(r["row_status"], r["submission_status"]) for r in table] == [
        ("accepted", "not_recorded"),
        ("accepted", "not_recorded"),
    ]
    audit = read_json(run_dir / "compounds_audit.json")
    Draft202012Validator(load_schema("compounds_audit")).validate(audit)
    assert audit["inputs"]["submission_log"] is None
    assert audit["inputs"]["stp_dir"] is None
    assert audit["rule_versions"]["submission_binding"] is None
    assert audit["rule_versions"]["structure_identity"] == "v0.2.0-structure-registry"
    assert audit["summary"]["submissions_not_recorded"] == 2
    assert (audit["summary"]["errors"], audit["summary"]["warnings"]) == (0, 2)
    manifest = read_json(run_dir / "run_manifest.json")
    assert [Path(item["path"]).name for item in manifest["inputs"]] == ["run.yaml", "compounds.tsv"]


def test_only_the_exports_that_were_checked_are_hashed(tmp_path):
    config, digests, run_dir = two(
        tmp_path,
        log_rows=lambda d: [log_row(1, d[1]), log_row(2, "a" * 64, submitted_structure="CCN")],
        numbers=(1,),
    )
    summary = run(config)
    audit = read_json(run_dir / "compounds_audit.json")
    assert audit["inputs"]["stp_dir"]["files_hashed"] == 1
    assert summary["quarantine"] == [
        {"compound_id": "CMP0002", "issue_codes": ["submission_export_missing"]}
    ]
    manifest = read_json(run_dir / "run_manifest.json")
    assert [Path(item["path"]).name for item in manifest["inputs"]][-1] == "c1.xlsx"


# --- what the stage hands to the library ----------------------------------------------------------
def test_the_smiles_cell_reaches_the_library_unchanged(tmp_path):
    write_exports(tmp_path)
    config = write_config(tmp_path, [compound_row(1, " CCO ")])
    run(config)
    run_dir = tmp_path / "results" / "r1_compounds"
    (row,) = read_table(run_dir / "compound_structures.tsv")
    assert row["smiles"] == "CCO"
    issues = read_json(run_dir / "compounds_audit.json")["issues"]
    assert "smiles_whitespace_trimmed" in [issue["code"] for issue in issues]


@pytest.mark.parametrize(
    "compound_cid, log_cid, status, code",
    [
        ("702", "702", "verified", None),
        ("702", "703", "rejected", "submission_cid_mismatch"),
        ("702", "", "verified", None),
        ("", "703", "verified", None),
        (" 702 ", "702", "verified", None),
    ],
)
def test_the_pubchem_cid_is_compared_when_both_sides_have_one(
    tmp_path, compound_cid, log_cid, status, code
):
    digests = write_exports(tmp_path)
    config = write_config(
        tmp_path,
        [compound_row(1, "CCO", pubchem_cid=compound_cid)],
        log_rows=[log_row(1, digests[1], pubchem_cid=log_cid)],
    )
    run(config)
    (row,) = read_table(tmp_path / "results" / "r1_compounds" / "compound_structures.tsv")
    assert row["submission_status"] == status
    assert (code in row["issue_codes"].split(";")) if code else row["issue_codes"] == ""


@pytest.mark.parametrize(
    "run_species, log_species, status",
    [
        ("Homo_sapiens", "Homo sapiens", "verified"),
        ("Mus_musculus", "Mus musculus", "verified"),
        ("Mus_musculus", "Homo sapiens", "rejected"),
        ("Homo_sapiens", "Mus musculus", "rejected"),
    ],
)
def test_the_species_of_the_log_must_be_the_species_of_the_run(
    tmp_path, run_species, log_species, status
):
    digests = write_exports(tmp_path)
    config = write_config(
        tmp_path,
        [compound_row(1, "CCO")],
        log_rows=[log_row(1, digests[1], species=log_species)],
        species=run_species,
    )
    run(config)
    (row,) = read_table(tmp_path / "results" / "r1_compounds" / "compound_structures.tsv")
    assert row["submission_status"] == status
    assert ("submission_species_mismatch" in row["issue_codes"]) == (status == "rejected")


def test_a_smiles_column_without_any_structure_quarantines_every_row(tmp_path):
    write_exports(tmp_path)
    config = write_config(tmp_path, [compound_row(1), compound_row(2)])
    summary = run(config)
    assert summary["identity_mode"] == "structure"
    assert summary["stage_status"] == "partial"
    assert summary["summary"]["rows_quarantined"] == 2
    assert [item["issue_codes"] for item in summary["quarantine"]] == [
        ["missing_structure"],
        ["missing_structure"],
    ]


# --- where the registry lives ---------------------------------------------------------------------
def test_the_structure_registry_can_be_placed_elsewhere(tmp_path):
    elsewhere = tmp_path / "elsewhere" / "structures.tsv"
    config, _, run_dir = two(tmp_path, inputs={"structure_registry": str(elsewhere)})
    run(config)
    assert len(read_registry(elsewhere)) == 2
    assert not (tmp_path / "results" / "registry" / "structure_registry.tsv").exists()
    audit = read_json(run_dir / "compounds_audit.json")
    assert audit["registries"]["structure_registry"]["path"] == str(elsewhere)


# --- determinism and refusal ----------------------------------------------------------------------
def test_the_same_inputs_give_the_same_table_and_audit(tmp_path):
    config, _, _ = six(tmp_path)
    run(config, run_id="a")
    shutil.rmtree(tmp_path / "results" / "registry")
    run(config, run_id="b")
    first, second = (tmp_path / "results" / f"{tag}_compounds" for tag in "ab")
    for name in ("compound_structures.tsv", "compounds_audit.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_an_existing_run_directory_leaves_the_structure_registry_alone(tmp_path):
    config, _, run_dir = six(tmp_path)
    run(config)
    registry = tmp_path / "results" / "registry" / "structure_registry.tsv"
    before = registry.read_bytes()
    with pytest.raises(InputError):
        run(config, now=lambda: LATER)
    assert registry.read_bytes() == before
    run(config, force=True, now=lambda: LATER)
    assert read_json(run_dir / "run_manifest.json")["overwritten"] is True


def test_two_rows_that_resolve_to_one_identity_write_nothing(tmp_path):
    config, _, _ = two(tmp_path)
    run(config)
    registry = tmp_path / "results" / "registry" / "structure_registry.tsv"
    before = registry.read_bytes()
    # Compound 1 is now bound to another export and Compound 3 takes over its old export: the
    # first row matches the registered identity by name, the second one by export file.
    rows = [
        compound_row(1, "CCO", stp_file="other.xlsx"),
        compound_row(3, "CCC", stp_file="c1.xlsx"),
    ]
    write_config(tmp_path, rows)
    with pytest.raises(InputError) as caught:
        run(config, run_id="r2")
    assert caught.value.exit_code == 2
    assert caught.value.details == ["CMP0001: rows 1, 2"]
    assert registry.read_bytes() == before
    assert not (tmp_path / "results" / "r2_compounds").exists()


def test_a_log_row_that_does_not_fit_its_schema_writes_nothing(tmp_path):
    digests = write_exports(tmp_path)
    config = write_config(
        tmp_path,
        [compound_row(1, "CCO")],
        log_rows=[log_row(1, digests[1], species="human")],
    )
    with pytest.raises(InputError) as caught:
        run(config)
    assert any("species" in detail for detail in caught.value.details)
    assert not (tmp_path / "results").exists()


def test_the_same_export_twice_in_the_log_writes_nothing(tmp_path):
    digests = write_exports(tmp_path)
    config = write_config(
        tmp_path,
        [compound_row(1, "CCO")],
        log_rows=[log_row(1, digests[1]), log_row(1, digests[1], compound="Other")],
    )
    with pytest.raises(InputError):
        run(config)
    assert not (tmp_path / "results").exists()


def test_a_structure_registry_with_other_columns_writes_nothing(tmp_path):
    config, _, _ = two(tmp_path)
    registry = write_text(
        tmp_path / "results" / "registry" / "structure_registry.tsv", "structure_id\tcompound_id\n"
    )
    before = registry.read_bytes()
    with pytest.raises(InputError):
        run(config)
    assert registry.read_bytes() == before
    assert sorted(path.name for path in (tmp_path / "results").iterdir()) == ["registry"]


def test_a_missing_submission_log_file_writes_nothing(tmp_path):
    config, _, _ = two(tmp_path, inputs={"submission_log": str(tmp_path / "nowhere.tsv")})
    with pytest.raises(InputError) as caught:
        run(config)
    assert "inputs.submission_log" in caught.value.message
    assert "not a file" in caught.value.message
    assert not (tmp_path / "results").exists()


def test_a_log_needs_an_export_directory(tmp_path):
    digests = write_exports(tmp_path)
    config = write_config(
        tmp_path,
        [compound_row(1, "CCO")],
        log_rows=[log_row(1, digests[1])],
        inputs={"stp_dir": str(tmp_path / "nowhere")},
    )
    with pytest.raises(InputError) as caught:
        run(config)
    assert "inputs.stp_dir" in caught.value.message
    assert "not a directory" in caught.value.message
    assert not (tmp_path / "results").exists()


# --- without RDKit --------------------------------------------------------------------------------
@pytest.fixture
def no_rdkit(monkeypatch):
    monkeypatch.setitem(sys.modules, "rdkit", None)


def test_structure_mode_needs_the_toolkit_and_writes_nothing_without_it(tmp_path, no_rdkit):
    config, _, _ = two(tmp_path)
    with pytest.raises(ChemUnavailable) as caught:
        run_compounds(load_config(config), run_id="r1", now=lambda: NOW)
    assert caught.value.exit_code == 2
    assert not (tmp_path / "results").exists()


def test_a_new_structure_needs_the_adapter_and_writes_nothing_without_it(tmp_path, no_rdkit):
    config, _, _ = two(tmp_path)
    with pytest.raises(ChemUnavailable):
        run(config, describe=None)
    assert not (tmp_path / "results").exists()


def test_registered_structures_need_no_adapter(tmp_path, no_rdkit):
    config, _, _ = two(tmp_path)
    run(config)
    summary = run(config, run_id="r2", describe=None)
    assert summary["summary"]["structures_reused"] == 2


def test_a_table_without_a_pubchem_cid_column_works(tmp_path):
    digests = write_exports(tmp_path)
    config = write_config(
        tmp_path,
        [compound_row(1, "CCO")],
        columns=["name", "group", "stp_file", "smiles"],
        log_rows=[log_row(1, digests[1], pubchem_cid="702")],
    )
    summary = run(config)
    assert summary["stage_status"] == "complete"
    assert summary["summary"]["submissions_verified"] == 1


@pytest.mark.parametrize("name", ["check_table", "check_issues", "check_summary"])
def test_an_inconsistency_found_by_the_self_check_is_an_internal_error(tmp_path, monkeypatch, name):
    config, _, _ = two(tmp_path)
    monkeypatch.setattr(stage_module, name, lambda *args, **kwargs: ["the parts disagree"])
    with pytest.raises(SchemaViolation) as caught:
        run(config)
    assert caught.value.exit_code == 1
    assert caught.value.details == ["the parts disagree"]
    assert not (tmp_path / "results").exists()
