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


def test_public_case_gate_is_not_confused_with_local_completion() -> None:
    data = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    assert data["case_id"] == "demo-public-compounds"
    assert data["status"] == "local_complete_publication_decision_pending"
    assert data["public_case_claim"] is False
    assert data["case_computed_in_linux"] is True
    assert data["public_release_status"].startswith("permission_confirmed")
    assert data["status_dimensions"] == {
        "local_inputs_verified": True,
        "local_linux_calculation": "complete",
        "local_independent_check": "passed",
        "public_redistribution": "stp_and_ctd_permission_confirmed_publication_pending",
        "public_case_claim": False,
        "final_skill_acceptance": "passed_codex_2026-10-21_with_environment_caveat",
        "stp_permission": "confirmed_2026-10-23_tables_only",
        "ctd_permission": "confirmed_public_nonprofit_2026-10-26_ticket_8545",
        "pubchem_review": "complete_2026-10-27_residual_third_party_caveat",
    }
    gaps = {item["id"] for item in data["public_release_gaps"]}
    assert {
        "researcher_publication_decision",
        "candidate_review",
        "pubchem_publication_decision",
    } == gaps
    assert data["public_release_gate"]["status"] == (
        "permission_confirmed_publication_decision_pending"
    )
    assert data["disease"]["term"] == "Arthritis, Rheumatoid"
    assert data["disease"]["mesh_id"] == "MESH:D001172"
    assert data["disease"]["row_count"] == 179
    assert data["disease"]["license_status"] == "public_nonprofit_research_permission_2026-10-26"
    assert data["disease"]["status"] == "local_prepared_permission_confirmed_not_committed"
    assert data["enrichment_background"]["status"] == "generated_and_frozen_local_not_committed"
    assert data["enrichment_background"]["thresholds"] == [0.10, 0.05]
    assert data["stp_exports"]["status"] == "local_verified_license_confirmed_not_committed"
    assert data["stp_exports"]["public_redistribution"] == "confirmed_cc_by_4_0_tables_only"
    assert data["stp_exports"]["permission"]["reply_date"] == "2026-10-23"
    assert data["stp_exports"]["permission"]["license"] == "CC BY 4.0"
    assert "do not modify" in data["stp_exports"]["permission"]["requirements"][2]
    runs = data["local_calculation"]["runs"]
    assert runs["0.10"]["T_r"] == 239 and runs["0.10"]["foreground"] == 15
    assert runs["0.05"]["T_r"] == 267 and runs["0.05"]["foreground"] == 17
    assert runs["0.10"]["significant"] == 0
    assert runs["0.05"]["significant"] == 2


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
    assert all(entry["stp_file"].endswith(".xlsx") for entry in compounds)
    assert "pending_v0.2" not in decisions["compound_list"]["smiles_status"]
    assert decisions["compound_list"]["smiles_evidence"]["log_evidence_id"] == (
        "EVID-HANDOFF-2026-10-21"
    )
    assert "PubChem" in decisions["compound_list"]["smiles_evidence"]["structures_source"]
    assert data["public_release_gaps"]
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
    assert run["enrichment"]["universe_file"] == "inputs/universe-0.10.txt"
    sensitivity = yaml.safe_load((DEMO / "run-0.05.yaml").read_text(encoding="utf-8"))
    assert sensitivity["thresholds"]["stp_probability"] == 0.05
    assert sensitivity["enrichment"]["universe_file"] == "inputs/universe-0.05.txt"
    assert freeze["enrichment_background"]["file"] == run["enrichment"]["universe_file"]
    assert run["references"]["hgnc"] == "2026-10-16"
    assert freeze["data_sources"]["hgnc"]["release_or_date"].endswith("2026-10-16")
    assert run["inputs"]["disease_source"] == "CTD"
    assert run["inputs"]["disease_retrieval_date"] == "2026-10-21"
    assert run["network"]["disease_label"].startswith("Rheumatoid arthritis")

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
    # The submission log must not sit in the export scan directory; real CSV/XLSX exports are
    # allowed there and must match the explicit bindings, with no unbound export.
    stp_dir = DEMO / "inputs" / "stp"
    assert not (stp_dir / "STP-SUBMISSION-LOG.tsv").exists()
    assert not (stp_dir / "SUBMISSION-LOG.tsv").exists()
    expected_files = set(freeze["stp_exports"]["expected_files"])
    export_files = {
        path.name
        for path in stp_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".csv", ".xlsx"}
    }
    assert export_files <= expected_files, f"unbound STP exports: {export_files - expected_files}"
    if export_files != expected_files:
        assert freeze["public_release_gate"]["status"] == (
            "permission_confirmed_publication_decision_pending"
        )
    else:
        # Once all exports exist, the log must contain the real submission evidence.
        required = {
            "submitted_structure",
            "structure_source",
            "species",
            "submitted_date",
            "result_file",
            "retrieved_date",
            "operator",
            "result_sha256",
        }
        for row in log:
            assert all(row.get(field, "").strip() for field in required), row["compound"]


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


def test_local_ctd_metadata_matches_freeze_if_present() -> None:
    metadata_path = ROOT / "data" / "local" / "case" / "ctd_metadata.json"
    if not metadata_path.is_file():
        pytest.skip("local CTD extract not present (expected in CI)")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    freeze = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    disease = freeze["disease"]
    assert metadata["disease"]["mesh_id"] == disease["mesh_id"]
    assert metadata["disease"]["child_expansion"] is False
    assert metadata["unique_genes"] == disease["row_count"] == 179
    assert metadata["disease_genes_sha256"] == disease["sha256"]
    assert metadata["raw_sha256"] == disease["raw_sha256"]
    assert metadata["license"]["committed"] is False
    assert metadata["license"]["status"] == "restricted_redistribution_not_confirmed"
    genes = (ROOT / "data" / "local" / "case" / "disease_genes.txt").read_text(
        encoding="utf-8"
    ).split()
    assert len(genes) == 179
    assert len(set(genes)) == 179


def test_frozen_compounds_bindings_and_log_are_consistent() -> None:
    freeze = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    assert not (DEMO / "inputs" / "STP-PENDING-SUBMISSIONS.tsv").exists()
    assert "pending_submission_list" not in freeze["stp_exports"]
    assert freeze["stp_exports"]["submission_log_template"] == "inputs/STP-SUBMISSION-LOG.tsv"

    compounds = read_table(DEMO / "inputs" / "compounds.tsv")
    log = read_table(DEMO / "inputs" / "STP-SUBMISSION-LOG.tsv")
    expected = set(freeze["stp_exports"]["expected_files"])
    assert len(compounds) == len(log) == freeze["stp_exports"]["count"] == 8
    assert {row["stp_file"] for row in compounds} == expected
    assert {row["stp_file"] for row in log} == expected
    assert {row["pubchem_cid"] for row in compounds} == {
        entry["pubchem_cid"]
        for entry in freeze["recorded_scientific_decisions"]["compound_list"]["compounds"]
    }

    by_file = {row["stp_file"]: row for row in compounds}
    for row in log:
        compound = by_file[row["stp_file"]]
        assert row["compound"] == compound["name"]
        assert row["pubchem_cid"] == compound["pubchem_cid"]
