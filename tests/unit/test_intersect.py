"""Intersection: parent-stage enforcement, exclusions and audit contracts."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from rnp.analysis.intersect import run_intersect
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


def _config(tmp_path: Path, *, missing_export: bool = False) -> Path:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "compounds.tsv").write_text(
        "name\tstp_file\nCompoundA\ta.csv\nCompoundB\tb.csv\n", encoding="utf-8"
    )
    stp = inputs / "stp"
    stp.mkdir()
    (stp / "a.csv").write_text(
        HEADER + "A1,CA2,P00918,,X,0.40,No\nA2,TNF,P01375,,X,0.30,No\n", encoding="utf-8"
    )
    if not missing_export:
        (stp / "b.csv").write_text(HEADER + "B1,IL6,P05231,,X,0.20,No\n", encoding="utf-8")
    data = {
        "project": "intersect-fixture",
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
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _ingest(config_path: Path, run_id: str = "r") -> Path:
    from rnp.cli import main

    code = main(["ingest", "stp", "--config", str(config_path), "--run-id", run_id])
    assert code in {0, 3}
    payload = json.loads(
        (config_path.parent / "results" / run_id / "run_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    return config_path.parent / "results" / payload["run_id"]


def test_intersect_run(ingest_run: Path, run_config_path: Path, tmp_path: Path) -> None:
    summary = run_intersect(
        load_config(run_config_path), ingest_run / "targets.tsv", tmp_path / "intersect"
    )
    stats = summary["groups"]["all"]
    assert (stats["targets"], stats["intersection"], stats["union"]) == (4, 2, 12)
    assert (stats["target_only"], stats["disease_only"]) == (2, 8)
    assert summary["exclusions"]["multi_symbol_common_name"] == 2
    assert summary["stage_status"] == "complete"

    edges = _read_tsv(tmp_path / "intersect" / "edges.tsv")
    assert [edge["gene"] for edge in edges] == ["CA2", "ESR1", "PTGS2", "TNF"]
    assert {edge["compound"] for edge in edges} == {"Quercetin"}
    assert all(edge["compound_id"].startswith("CMP") for edge in edges)

    intersection = _read_tsv(tmp_path / "intersect" / "intersection_genes.tsv")
    assert [row["gene"] for row in intersection] == ["PTGS2", "TNF"]

    audit = json.loads(
        (tmp_path / "intersect" / "intersect_audit.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(audit, load_schema("intersection"))
    assert len(audit["parents"]) == 1
    assert audit["parents"][0]["stage"] == "ingest"
    assert audit["parents"][0]["stage_status"] == "complete"

    manifest = json.loads(
        (tmp_path / "intersect" / "run_manifest.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(manifest, load_schema("run_manifest"))
    assert manifest["parents"][0]["stage"] == "ingest"
    assert manifest["code"]["version"] == "0.0.1"


def test_partial_upstream_is_refused_then_allowed(tmp_path: Path) -> None:
    config_path = _config(tmp_path, missing_export=True)
    run_dir = _ingest(config_path, "partial")
    config = load_config(config_path)
    with pytest.raises(InputError) as excinfo:
        run_intersect(config, run_dir / "targets.tsv", tmp_path / "refused")
    assert "not 'complete'" in excinfo.value.render()

    summary = run_intersect(
        config,
        run_dir / "targets.tsv",
        tmp_path / "allowed",
        allow_partial=True,
    )
    assert summary["stage_status"] == "partial_override"
    audit = json.loads(
        (tmp_path / "allowed" / "intersect_audit.json").read_text(encoding="utf-8")
    )
    assert audit["parents"][0]["status_override"] is True
    assert any(w["code"] == "upstream_status_override" for w in audit["warnings"])


def test_config_change_is_refused(ingest_run: Path, run_config_path: Path, tmp_path: Path) -> None:
    data = yaml.safe_load(run_config_path.read_text(encoding="utf-8"))
    data["project"] = "changed-after-ingest"
    changed = tmp_path / "changed.yaml"
    changed.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(InputError) as excinfo:
        run_intersect(load_config(changed), ingest_run / "targets.tsv", tmp_path / "out")
    assert "config changed" in excinfo.value.render()


def test_tampered_targets_are_refused(
    ingest_run: Path, run_config_path: Path, tmp_path: Path
) -> None:
    with (ingest_run / "targets.tsv").open("a", encoding="utf-8") as handle:
        handle.write("CMP9999\tall\tS\tx.csv\tX\tTNF\tP01375\tX\t\t0.99\tFalse\tFalse\t99\n")
    with pytest.raises(InputError) as excinfo:
        run_intersect(load_config(run_config_path), ingest_run / "targets.tsv", tmp_path / "out")
    assert "changed since" in excinfo.value.render()


def test_missing_parent_audit_is_refused(
    ingest_run: Path, run_config_path: Path, tmp_path: Path
) -> None:
    (ingest_run / "stp_audit.json").unlink()
    with pytest.raises(InputError) as excinfo:
        run_intersect(load_config(run_config_path), ingest_run / "targets.tsv", tmp_path / "out")
    assert "audit not found" in excinfo.value.render()


def test_existing_output_requires_force(
    ingest_run: Path, run_config_path: Path, tmp_path: Path
) -> None:
    out = tmp_path / "intersect"
    run_intersect(load_config(run_config_path), ingest_run / "targets.tsv", out)
    with pytest.raises(InputError):
        run_intersect(load_config(run_config_path), ingest_run / "targets.tsv", out)
    assert (
        run_intersect(
            load_config(run_config_path), ingest_run / "targets.tsv", out, force=True
        )["stage_status"]
        == "complete"
    )


def test_zero_intersection_is_a_valid_empty_result(tmp_path: Path) -> None:
    config_path = _config(tmp_path)
    disease = tmp_path / "disease.txt"
    disease.write_text("ICAM1\n", encoding="utf-8")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["inputs"]["disease_genes"] = str(disease)
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    run_dir = _ingest(config_path, "zero")
    summary = run_intersect(
        load_config(config_path), run_dir / "targets.tsv", tmp_path / "intersect"
    )
    assert summary["groups"]["all"]["intersection"] == 0
    assert summary["groups"]["all"]["disease_only"] == 1
    assert summary["stage_status"] == "complete"


def test_requires_hgnc_map(ingest_run: Path, tmp_path: Path) -> None:
    data = yaml.safe_load((FIXTURES / "run" / "run.yaml").read_text(encoding="utf-8"))
    data["inputs"] = {
        "compounds": str(FIXTURES / "run" / "inputs" / "compounds.tsv"),
        "stp_dir": str(FIXTURES / "run" / "inputs" / "stp"),
        "disease_genes": str(FIXTURES / "run" / "inputs" / "disease_genes.txt"),
    }
    data["outputs"] = {"dir": str(tmp_path / "results")}
    config_path = tmp_path / "run.yaml"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(InputError) as excinfo:
        run_intersect(load_config(config_path), ingest_run / "targets.tsv", tmp_path / "out")
    assert "hgnc_map" in excinfo.value.render()


def test_unresolved_disease_gene_raises(
    ingest_run: Path, run_config_path: Path, tmp_path: Path
) -> None:
    data = yaml.safe_load(run_config_path.read_text(encoding="utf-8"))
    disease = tmp_path / "disease.txt"
    disease.write_text("TNF\nNOSUCHGENE\n", encoding="utf-8")
    data["inputs"]["disease_genes"] = str(disease)
    config_path = tmp_path / "run.yaml"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    with pytest.raises(InputError):
        run_intersect(load_config(config_path), ingest_run / "targets.tsv", tmp_path / "out")


def test_venn_plot_when_r_available(
    ingest_run: Path, run_config_path: Path, tmp_path: Path, monkeypatch
) -> None:
    import os
    import shutil

    rscript = os.environ.get("RNP_RSCRIPT") or shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")
    if not (Path(__file__).parents[2] / "R" / "venny.R").is_file():
        pytest.skip("R/venny.R not present")
    monkeypatch.setenv("RNP_RSCRIPT", rscript)
    summary = run_intersect(
        load_config(run_config_path),
        ingest_run / "targets.tsv",
        tmp_path / "intersect",
        venn_plot=True,
    )
    plots = summary["venn_plots"]
    assert len(plots) == 2
    assert all(Path(plot).is_file() for plot in plots)
