"""The public-case freeze must stay honest: blocked until inputs/licences exist."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
FREEZE = ROOT / "examples" / "demo" / "CASE-FREEZE.yaml"


def test_public_case_is_not_claimed_before_inputs_exist() -> None:
    data = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    assert data["case_id"] == "demo-public-compounds"
    assert data["status"] == "blocked"
    assert data["public_case_claim"] is False
    assert data["case_computed_in_linux"] is False
    missing = {item["id"] for item in data["required_inputs_missing"]}
    assert {"disease_genes", "stp_exports", "hgnc_map"} <= missing


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
    # No file may be marked verified/frozen until a real hash and licence evidence exist.
    assert data["required_inputs_missing"]
    assert data["verification_environment"]["windows"]["status"] == "unverified_blocked"
