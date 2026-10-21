"""The public-case freeze must stay honest and consistent with the recorded config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from rnp.io.tables import read_table

ROOT = Path(__file__).parents[2]
DEMO = ROOT / "examples" / "demo"
FREEZE = DEMO / "CASE-FREEZE.yaml"


def test_public_case_is_not_claimed_before_inputs_exist() -> None:
    data = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    assert data["case_id"] == "demo-public-compounds"
    assert data["status"] == "blocked"
    assert data["public_case_claim"] is False
    assert data["case_computed_in_linux"] is False
    missing = {item["id"] for item in data["required_inputs_missing"]}
    assert {"disease_genes", "stp_exports", "universe_file"} <= missing
    assert "hgnc_map" not in missing
    assert data["disease"]["sha256"] is None
    assert data["disease"]["term"] is None
    assert data["enrichment_background"]["sha256"] is None
    assert data["stp_exports"]["status"] == "blocked"


def test_freeze_reuses_recorded_decisions_without_inventing_sources() -> None:
    data = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    decisions = data["recorded_scientific_decisions"]
    assert decisions["stp_probability"] == 0.10
    assert decisions["enrichment"]["gene_sets"] == "GO_BP"
    assert decisions["enrichment"]["p_adjust"] == "BH"
    assert decisions["stp_submission"] == "manual by researcher; never automated"
    compounds = decisions["compound_list"]["compounds"]
    assert len(compounds) == 8
    assert compounds[0]["pubchem_cid"] == "5280343"
    assert data["required_inputs_missing"]
    assert data["verification_environment"]["windows"]["status"] == "unverified_blocked"


def test_freeze_matches_run_yaml_and_binding_files() -> None:
    freeze = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    run = yaml.safe_load((DEMO / "run.yaml").read_text(encoding="utf-8"))
    decisions = freeze["recorded_scientific_decisions"]
    assert decisions["stp_probability"] == run["thresholds"]["stp_probability"]
    for key in (
        "gene_sets",
        "p_adjust",
        "pvalue_cutoff",
        "qvalue_cutoff",
        "min_gssize",
        "max_gssize",
    ):
        assert decisions["enrichment"][key] == run["enrichment"][key], key
    assert run["enrichment"]["universe_file"] == "inputs/universe.txt"
    assert freeze["enrichment_background"]["file"] == run["enrichment"]["universe_file"]
    assert run["references"]["hgnc"] == "2026-10-16"
    assert freeze["data_sources"]["hgnc"]["release_or_date"].endswith("2026-10-16")

    hgnc = read_table(DEMO / "inputs" / "hgnc_map.tsv")
    assert len(hgnc) == 45277
    assert list(hgnc[0]) == [
        "hgnc_id",
        "symbol",
        "status",
        "prev_symbol",
        "alias_symbol",
        "uniprot_ids",
        "entrez_id",
        "locus_group",
    ]
    assert all(row["status"] == "Approved" for row in hgnc)
    hgnc_meta = json.loads(
        (DEMO / "inputs" / "hgnc_map.metadata.json").read_text(encoding="utf-8")
    ) if (DEMO / "inputs" / "hgnc_map.metadata.json").is_file() else None
    if hgnc_meta is not None:
        assert hgnc_meta["derived_sha256"] == freeze["data_sources"]["hgnc"]["sha256"]
        assert hgnc_meta["derived_rows_approved"] == 45277
    assert (DEMO / "inputs" / "HGNC-SOURCE.md").is_file()

    compounds = read_table(DEMO / "inputs" / "compounds.tsv")
    assert len(compounds) == 8
    assert all(row["stp_file"] for row in compounds)
    assert {row["stp_file"] for row in compounds} == set(freeze["stp_exports"]["expected_files"])
    assert {row["pubchem_cid"] for row in compounds} == {
        entry["pubchem_cid"] for entry in decisions["compound_list"]["compounds"]
    }

    log = read_table(DEMO / "inputs" / "STP-SUBMISSION-LOG.tsv")
    assert len(log) == 8
    assert {row["stp_file"] for row in log} == set(freeze["stp_exports"]["expected_files"])
    # The log must not sit in the export scan directory; otherwise ingest treats it as an
    # unbound export and quarantines it.
    stp_files = {path.suffix.lower() for path in (DEMO / "inputs" / "stp").iterdir()}
    assert ".tsv" not in stp_files and ".csv" not in stp_files


def test_local_pubchem_metadata_matches_freeze_and_is_nonempty() -> None:
    metadata_path = ROOT / "data" / "local" / "case" / "metadata.json"
    if not metadata_path.is_file():
        pytest.skip("local PubChem fetch not present (expected in CI)")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    freeze = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    source = freeze["data_sources"]["pubchem"]
    files = metadata["files"]
    table = next(iter(files.values()))
    assert table["row_count"] == 8
    assert table["sha256"] == source["sha256"]
    assert metadata["retrieved_utc"] == source["retrieved"]
    assert metadata["requested_fields"] == ["SMILES", "ConnectivitySMILES"]
    rows = read_table(ROOT / "data" / "local" / "case" / "pubchem_structures.tsv")
    assert len(rows) == 8
    assert all(row["smiles"].strip() for row in rows)
    assert all(row["connectivity_smiles"].strip() for row in rows)
    assert all(row["pubchem_cid"].strip() for row in rows)
