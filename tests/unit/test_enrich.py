"""Enrichment stage: explicit background, status separation and parent checks."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import jsonschema
import pytest
import yaml

from rnp.analysis.enrich import run_enrich
from rnp.analysis.ingest import run_ingest
from rnp.analysis.intersect import run_intersect
from rnp.config import load_config, load_schema
from rnp.errors import InputError

FIXTURES = Path(__file__).parents[1] / "fixtures"
HEADER = (
    "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,"
    "Known actives (3D/2D)\n"
)


def _rscript() -> str | None:
    return os.environ.get("RNP_RSCRIPT") or shutil.which("Rscript")


def _config(tmp_path: Path, *, disease: str = "disease.txt", universe: bool = True) -> Path:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "compounds.tsv").write_text(
        "name\tstp_file\nCompoundA\ta.csv\n", encoding="utf-8"
    )
    stp = inputs / "stp"
    stp.mkdir()
    (stp / "a.csv").write_text(
        HEADER + "A1,TNF,P01375,,X,0.40,No\nA2,PTGS2,P35354,,X,0.30,No\n",
        encoding="utf-8",
    )
    (inputs / "disease.txt").write_text("TNF\nPTGS2\n", encoding="utf-8")
    (inputs / "universe.txt").write_text(
        (FIXTURES / "run" / "inputs" / "universe.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    enrichment = {
        "engine": "r",
        "gene_sets": "GO_BP",
        "p_adjust": "BH",
        "pvalue_cutoff": 0.05,
        "qvalue_cutoff": 0.2,
        "min_gssize": 5,
        "max_gssize": 500,
    }
    if universe:
        enrichment["universe_file"] = str(inputs / "universe.txt")
    data = {
        "project": "enrich-fixture",
        "species": "Homo_sapiens",
        "inputs": {
            "compounds": str(inputs / "compounds.tsv"),
            "stp_dir": str(stp),
            "disease_genes": str(inputs / disease),
            "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
        },
        "thresholds": {"stp_probability": 0.10},
        "enrichment": enrichment,
        "network": {"disease_label": "Fixture disease"},
        "outputs": {"dir": str(tmp_path / "results")},
    }
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _chain(config_path: Path, run_id: str = "r") -> Path:
    config = load_config(config_path)
    run_ingest(config, run_id=run_id)
    run_dir = config.output_dir / run_id
    run_intersect(config, run_dir / "targets.tsv", run_dir / "intersect")
    return run_dir / "intersect"


def test_missing_universe_file_is_refused(tmp_path: Path) -> None:
    config_path = _config(tmp_path, universe=False)
    intersect_dir = _chain(config_path)
    with pytest.raises(InputError) as excinfo:
        run_enrich(load_config(config_path), intersect_dir, tmp_path / "enrichment")
    assert "universe_file" in excinfo.value.render()


def test_missing_rscript_is_refused(tmp_path: Path) -> None:
    config_path = _config(tmp_path)
    intersect_dir = _chain(config_path)
    with pytest.raises(InputError) as excinfo:
        run_enrich(
            load_config(config_path),
            intersect_dir,
            tmp_path / "enrichment",
            rscript=str(tmp_path / "no-such-Rscript"),
        )
    assert "Rscript not found" in excinfo.value.render()


def test_zero_foreground_is_a_valid_empty_result(tmp_path: Path) -> None:
    config_path = _config(tmp_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["inputs"]["disease_genes"] = str(tmp_path / "inputs" / "disease_close.txt")
    (tmp_path / "inputs" / "disease_close.txt").write_text("ICAM1\n", encoding="utf-8")
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    intersect_dir = _chain(config_path)
    summary = run_enrich(load_config(config_path), intersect_dir, tmp_path / "enrichment")
    assert summary["stage_status"] == "empty"
    audit = json.loads(
        (tmp_path / "enrichment" / "enrichment_audit.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(audit, load_schema("enrichment"))
    assert audit["groups"] == {}


@pytest.mark.skipif(_rscript() is None, reason="Rscript not available")
def test_live_enrichment_writes_complete_table_and_audit(tmp_path: Path) -> None:
    config_path = _config(tmp_path)
    intersect_dir = _chain(config_path)
    summary = run_enrich(
        load_config(config_path),
        intersect_dir,
        tmp_path / "enrichment",
        rscript=_rscript(),
    )
    assert summary["stage_status"] == "complete"
    group = summary["groups"]["all"]
    assert group["status"] in {"ok", "completed_no_significant_terms"}
    assert group["terms_tested"] > 0
    assert group["foreground_mapped"] == 2

    result = (
        tmp_path / "enrichment" / "all" / "enrichment_result.tsv"
    ).read_text(encoding="utf-8").splitlines()
    assert result[0].startswith("ID\tDescription\tGeneRatio")
    significant = (
        tmp_path / "enrichment" / "all" / "enrichment_significant.tsv"
    ).read_text(encoding="utf-8").splitlines()
    assert significant[0].startswith("ID\tDescription")
    assert len(significant) - 1 <= len(result) - 1

    audit = json.loads(
        (tmp_path / "enrichment" / "enrichment_audit.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(audit, load_schema("enrichment"))
    assert audit["universe"] == {
        "source": "explicit",
        "input": 30,
        "mapped": 30,
        "unmapped": 0,
        "statistical": 30,
    }
    assert audit["parents"][0]["stage"] == "intersect"
    assert audit["environment"]["packages"]["clusterProfiler"]

    manifest = json.loads(
        (tmp_path / "enrichment" / "run_manifest.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(manifest, load_schema("run_manifest"))
    assert manifest["parents"][0]["stage"] == "intersect"


@pytest.mark.skipif(_rscript() is None, reason="Rscript not available")
def test_enrich_cli(tmp_path: Path, capsys) -> None:
    from rnp.cli import main

    config_path = _config(tmp_path)
    intersect_dir = _chain(config_path)
    code = main(
        [
            "enrich",
            "--config",
            str(config_path),
            "--intersect",
            str(intersect_dir),
            "--rscript",
            _rscript(),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stage_status"] == "complete"
    assert payload["groups"]["all"]["terms_tested"] > 0


@pytest.mark.skipif(_rscript() is None, reason="Rscript not available")
def test_existing_output_requires_force(tmp_path: Path) -> None:
    config_path = _config(tmp_path)
    intersect_dir = _chain(config_path)
    config = load_config(config_path)
    out = tmp_path / "enrichment"
    run_enrich(config, intersect_dir, out, rscript=_rscript())
    with pytest.raises(InputError):
        run_enrich(config, intersect_dir, out, rscript=_rscript())
    assert (
        run_enrich(config, intersect_dir, out, rscript=_rscript(), force=True)["stage_status"]
        in {"complete", "partial_override"}
    )
