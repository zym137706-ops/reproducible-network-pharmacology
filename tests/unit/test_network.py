"""Network tables: invariants, MOLIDs, empty results and parent enforcement."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from rnp.analysis.ingest import run_ingest
from rnp.analysis.intersect import run_intersect
from rnp.analysis.network import run_network
from rnp.config import load_config, load_schema
from rnp.errors import InputError

FIXTURES = Path(__file__).parents[1] / "fixtures"
HEADER = (
    "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,"
    "Known actives (3D/2D)\n"
)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]


def test_network_build(intersect_run: tuple[Path, Path], tmp_path: Path) -> None:
    config_path, intersect_dir = intersect_run
    summary = run_network(load_config(config_path), intersect_dir, tmp_path / "network")
    stats = summary["groups"]["all"]
    assert (stats["compounds_total"], stats["compounds_linked"]) == (2, 1)
    assert (stats["targets"], stats["network_nodes"], stats["network_edges"]) == (2, 4, 4)
    assert (stats["compound_target_edges"], stats["disease_edges"]) == (2, 2)

    edges = _read_tsv(tmp_path / "network" / "all" / "edges.tsv")
    assert [edge["Interaction"] for edge in edges].count("compound-target") == 2
    assert [edge["Interaction"] for edge in edges].count("target-disease") == 2
    nodes = {
        row["Node"]: row["Type"]
        for row in _read_tsv(tmp_path / "network" / "all" / "nodes.tsv")
    }
    assert nodes == {
        "Quercetin": "Compound",
        "PTGS2": "Target",
        "TNF": "Target",
        "Fixture disease": "Disease",
    }
    mol_list = _read_tsv(tmp_path / "network" / "all" / "mol_list.tsv")
    assert [row["moleculename"] for row in mol_list] == ["Kaempferol", "Quercetin"]

    audit = json.loads(
        (tmp_path / "network" / "network_audit.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(audit, load_schema("network"))
    assert audit["stage_status"] == "complete"
    assert all(audit["groups"]["all"]["checks"].values())

    manifest = json.loads(
        (tmp_path / "network" / "run_manifest.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(manifest, load_schema("run_manifest"))
    assert manifest["parents"][0]["stage"] == "intersect"


def test_zero_intersection_produces_valid_empty_network(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "compounds.tsv").write_text(
        "name\tstp_file\nCompoundA\ta.csv\n", encoding="utf-8"
    )
    stp = inputs / "stp"
    stp.mkdir()
    (stp / "a.csv").write_text(HEADER + "A1,CA2,P00918,,X,0.40,No\n", encoding="utf-8")
    disease = inputs / "disease.txt"
    disease.write_text("ICAM1\n", encoding="utf-8")
    data = {
        "project": "empty-network",
        "species": "Homo_sapiens",
        "inputs": {
            "compounds": str(inputs / "compounds.tsv"),
            "stp_dir": str(stp),
            "disease_genes": str(disease),
            "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
        },
        "thresholds": {"stp_probability": 0.10},
        "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
        "network": {"disease_label": "Fixture disease"},
        "outputs": {"dir": str(tmp_path / "results")},
    }
    config_path = tmp_path / "run.yaml"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    run_ingest(load_config(config_path), run_id="r")
    intersect_dir = tmp_path / "results" / "r" / "intersect"
    run_intersect(
        load_config(config_path), tmp_path / "results" / "r" / "targets.tsv", intersect_dir
    )
    summary = run_network(load_config(config_path), intersect_dir, tmp_path / "network")
    assert summary["stage_status"] == "empty"
    assert summary["groups"] == {}
    audit = json.loads(
        (tmp_path / "network" / "network_audit.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(audit, load_schema("network"))
    assert audit["stage_status"] == "empty"
    assert not (tmp_path / "network" / "all").exists()


def test_partial_intersection_is_refused_then_allowed(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "compounds.tsv").write_text(
        "name\tstp_file\nCompoundA\ta.csv\nCompoundB\tb.csv\n", encoding="utf-8"
    )
    stp = inputs / "stp"
    stp.mkdir()
    (stp / "a.csv").write_text(HEADER + "A1,TNF,P01375,,X,0.40,No\n", encoding="utf-8")
    data = {
        "project": "partial",
        "species": "Homo_sapiens",
        "inputs": {
            "compounds": str(inputs / "compounds.tsv"),
            "stp_dir": str(stp),
            "disease_genes": str(FIXTURES / "run" / "inputs" / "disease_genes.txt"),
            "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
        },
        "thresholds": {"stp_probability": 0.10},
        "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
        "network": {"disease_label": "Fixture disease"},
        "outputs": {"dir": str(tmp_path / "results")},
    }
    config_path = tmp_path / "run.yaml"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    config = load_config(config_path)
    assert run_ingest(config, run_id="r")["stage_status"] == "partial"
    intersect_dir = tmp_path / "results" / "r" / "intersect"
    assert (
        run_intersect(
            config, tmp_path / "results" / "r" / "targets.tsv", intersect_dir, allow_partial=True
        )["stage_status"]
        == "partial_override"
    )
    with pytest.raises(InputError):
        run_network(config, intersect_dir, tmp_path / "refused")
    summary = run_network(
        config, intersect_dir, tmp_path / "allowed", allow_partial=True
    )
    assert summary["stage_status"] == "partial_override"


def test_compound_gene_collision_is_rejected(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "compounds.tsv").write_text("name\tstp_file\nTNF\ta.csv\n", encoding="utf-8")
    stp = inputs / "stp"
    stp.mkdir()
    (stp / "a.csv").write_text(HEADER + "A1,TNF,P01375,,X,0.40,No\n", encoding="utf-8")
    data = {
        "project": "collision",
        "species": "Homo_sapiens",
        "inputs": {
            "compounds": str(inputs / "compounds.tsv"),
            "stp_dir": str(stp),
            "disease_genes": str(FIXTURES / "run" / "inputs" / "disease_genes.txt"),
            "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
        },
        "thresholds": {"stp_probability": 0.10},
        "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
        "network": {"disease_label": "Fixture disease"},
        "outputs": {"dir": str(tmp_path / "results")},
    }
    config_path = tmp_path / "run.yaml"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    config = load_config(config_path)
    run_ingest(config, run_id="r")
    intersect_dir = tmp_path / "results" / "r" / "intersect"
    run_intersect(config, tmp_path / "results" / "r" / "targets.tsv", intersect_dir)
    with pytest.raises(InputError) as excinfo:
        run_network(config, intersect_dir, tmp_path / "out")
    assert "collide" in excinfo.value.render()


def test_disease_label_collision_is_rejected(
    intersect_run: tuple[Path, Path], tmp_path: Path
) -> None:
    config_path, intersect_dir = intersect_run
    with pytest.raises(InputError):
        run_network(
            load_config(config_path), intersect_dir, tmp_path / "out", disease_label="TNF"
        )
