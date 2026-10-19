"""Report command: evidence-bound rendering, hash checks and partial handling."""

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
from rnp.analysis.network import run_network
from rnp.analysis.report import run_report
from rnp.config import load_config, load_schema
from rnp.errors import InputError

FIXTURES = Path(__file__).parents[1] / "fixtures"
HEADER = (
    "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,"
    "Known actives (3D/2D)\n"
)


def _rscript() -> str | None:
    return os.environ.get("RNP_RSCRIPT") or shutil.which("Rscript")


def _chain(run_config_path: Path, run_id: str = "chain") -> Path:
    config = load_config(run_config_path)
    run_ingest(config, run_id=run_id)
    run_dir = config.output_dir / run_id
    run_intersect(config, run_dir / "targets.tsv", run_dir / "intersect")
    run_network(config, run_dir / "intersect", run_dir / "network")
    return run_dir


def test_report_from_ingest_only_shows_missing_stages(
    ingest_run: Path, run_config_path: Path, tmp_path: Path
) -> None:
    summary = run_report(load_config(run_config_path), ingest_run, tmp_path / "report")
    assert summary["stage_status"] == "complete"
    assert summary["stages"] == {"ingest": "complete"}
    text = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "## 3. Compound–target–disease intersection" in text
    assert "Intersection stage not run" in text
    assert "Enrichment stage not run" in text
    assert "not experimental validation" in text
    audit = json.loads(
        (tmp_path / "report" / "report_audit.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(audit, load_schema("report"))
    manifest = json.loads(
        (tmp_path / "report" / "run_manifest.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(manifest, load_schema("run_manifest"))
    assert manifest["command"] == "report"


def test_report_renders_intersection_and_network(
    run_config_path: Path, tmp_path: Path
) -> None:
    run_dir = _chain(run_config_path)
    summary = run_report(load_config(run_config_path), run_dir, tmp_path / "report")
    assert summary["stages"] == {
        "ingest": "complete",
        "intersect": "complete",
        "network": "complete",
    }
    text = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "| all | 2 | 4 | 4 | 10 | 2 |" in text
    assert "| all | 4 | 4 |" in text
    assert "Invariant checks: all passed" in text
    assert "Enrichment stage not run" in text
    assert "Unresolved/conflicting gene mappings: 0" in text


@pytest.mark.skipif(_rscript() is None, reason="Rscript not available")
def test_report_includes_enrichment(run_config_path: Path, tmp_path: Path) -> None:
    run_dir = _chain(run_config_path)
    config = load_config(run_config_path)
    run_enrich(
        config,
        run_dir / "intersect",
        run_dir / "enrichment",
        rscript=_rscript(),
    )
    summary = run_report(config, run_dir, tmp_path / "report")
    assert summary["stages"]["enrichment"] in {"complete", "empty"}
    text = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "Terms tested" in text
    assert "R " in text and "clusterProfiler" in text
    audit = json.loads(
        (tmp_path / "report" / "report_audit.json").read_text(encoding="utf-8")
    )
    assert "enrichment" in audit["stages"]


def test_report_refuses_tampered_artifact(
    run_config_path: Path, tmp_path: Path
) -> None:
    run_dir = _chain(run_config_path)
    with (run_dir / "targets.tsv").open("a", encoding="utf-8") as handle:
        handle.write("CMP9999\tall\tS\tx.csv\tX\tTNF\tP01375\tX\t\t0.99\tFalse\tFalse\t99\n")
    with pytest.raises(InputError) as excinfo:
        run_report(load_config(run_config_path), run_dir, tmp_path / "report")
    assert "changed since" in excinfo.value.render()


def test_report_rejects_non_run_directory(
    run_config_path: Path, tmp_path: Path
) -> None:
    with pytest.raises(InputError):
        run_report(load_config(run_config_path), tmp_path / "empty", tmp_path / "report")


def test_report_overwrite_requires_force(
    run_config_path: Path, tmp_path: Path
) -> None:
    run_dir = _chain(run_config_path)
    config = load_config(run_config_path)
    out = tmp_path / "report"
    run_report(config, run_dir, out)
    with pytest.raises(InputError):
        run_report(config, run_dir, out)
    assert run_report(config, run_dir, out, force=True)["status"] == "ok"


def test_report_partial_requires_override(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "compounds.tsv").write_text(
        "name\tstp_file\nCompoundA\ta.csv\nCompoundB\tb.csv\n", encoding="utf-8"
    )
    stp = inputs / "stp"
    stp.mkdir()
    (stp / "a.csv").write_text(HEADER + "A1,TNF,P01375,,X,0.40,No\n", encoding="utf-8")
    data = yaml.safe_load(
        (FIXTURES / "run" / "run.yaml").read_text(encoding="utf-8")
    )
    data["inputs"] = {
        "compounds": str(inputs / "compounds.tsv"),
        "stp_dir": str(stp),
        "disease_genes": str(FIXTURES / "run" / "inputs" / "disease_genes.txt"),
        "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
    }
    data["enrichment"]["universe_file"] = str(
        FIXTURES / "run" / "inputs" / "universe.txt"
    )
    data["outputs"] = {"dir": str(tmp_path / "results")}
    config_path = tmp_path / "run.yaml"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    config = load_config(config_path)
    run_ingest(config, run_id="p")
    run_dir = tmp_path / "results" / "p"
    run_intersect(config, run_dir / "targets.tsv", run_dir / "intersect", allow_partial=True)
    run_network(config, run_dir / "intersect", run_dir / "network", allow_partial=True)

    with pytest.raises(InputError) as excinfo:
        run_report(config, run_dir, tmp_path / "report")
    assert "incomplete stages" in excinfo.value.render()
    summary = run_report(config, run_dir, tmp_path / "report", allow_partial=True)
    assert summary["stage_status"] == "partial_override"
    text = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "partial stages included by explicit override" in text


def test_report_empty_result(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "compounds.tsv").write_text("name\tstp_file\nA\ta.csv\n", encoding="utf-8")
    stp = inputs / "stp"
    stp.mkdir()
    (stp / "a.csv").write_text(HEADER + "A1,CA2,P00918,,X,0.40,No\n", encoding="utf-8")
    disease = inputs / "disease.txt"
    disease.write_text("ICAM1\n", encoding="utf-8")
    data = yaml.safe_load(
        (FIXTURES / "run" / "run.yaml").read_text(encoding="utf-8")
    )
    data["inputs"] = {
        "compounds": str(inputs / "compounds.tsv"),
        "stp_dir": str(stp),
        "disease_genes": str(disease),
        "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
    }
    data["outputs"] = {"dir": str(tmp_path / "results")}
    config_path = tmp_path / "run.yaml"
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    config = load_config(config_path)
    run_ingest(config, run_id="zero")
    run_dir = tmp_path / "results" / "zero"
    run_intersect(config, run_dir / "targets.tsv", run_dir / "intersect")
    summary = run_report(config, run_dir, tmp_path / "report")
    assert summary["stage_status"] == "empty"
    text = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    assert "| all | 1 | 1 | 1 | 1 | 0 | 1 | 1 |" in text


def test_report_cli(run_config_path: Path, tmp_path: Path, capsys) -> None:
    from rnp.cli import main

    run_dir = _chain(run_config_path)
    assert main(["report", "--config", str(run_config_path), "--run-dir", str(run_dir)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stages"]["network"] == "complete"
    assert (run_dir / "report" / "report.md").is_file()


def test_report_refuses_tampered_intersection_side_artifacts(
    run_config_path: Path, tmp_path: Path
) -> None:
    run_dir = _chain(run_config_path)
    config = load_config(run_config_path)
    for name in ("target_exclusions.tsv", "gene_mapping_conflicts.tsv", "venn.json"):
        path = run_dir / "intersect" / name
        original = path.read_bytes()
        path.write_bytes(original + b"\n")
        with pytest.raises(InputError):
            run_report(config, run_dir, tmp_path / f"report-{name}")
        path.write_bytes(original)


def test_report_refuses_stale_parent_link(
    run_config_path: Path, tmp_path: Path
) -> None:
    run_dir = _chain(run_config_path)
    audit_path = run_dir / "intersect" / "intersect_audit.json"
    audit_path.write_text(audit_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(InputError) as excinfo:
        run_report(load_config(run_config_path), run_dir, tmp_path / "report")
    assert "parent" in excinfo.value.render().lower()


def test_report_audit_lists_verified_artifacts(
    run_config_path: Path, tmp_path: Path
) -> None:
    run_dir = _chain(run_config_path)
    run_report(load_config(run_config_path), run_dir, tmp_path / "report")
    audit = json.loads(
        (tmp_path / "report" / "report_audit.json").read_text(encoding="utf-8")
    )
    roles = {entry["role"] for entry in audit["artifacts"]}
    assert {"targets", "compounds", "edges", "intersection", "disease"} <= roles
    assert {"exclusions", "conflicts", "venn"} <= roles
    for entry in audit["artifacts"]:
        assert Path(entry["path"]).is_file()


@pytest.mark.skipif(_rscript() is None, reason="Rscript not available")
def test_report_refuses_tampered_enrichment_view(
    run_config_path: Path, tmp_path: Path
) -> None:
    run_dir = _chain(run_config_path)
    config = load_config(run_config_path)
    run_enrich(config, run_dir / "intersect", run_dir / "enrichment", rscript=_rscript())
    significant = run_dir / "enrichment" / "all" / "enrichment_significant.tsv"
    original = significant.read_bytes()
    significant.write_bytes(original + b"\n")
    try:
        with pytest.raises(InputError):
            run_report(config, run_dir, tmp_path / "report")
    finally:
        significant.write_bytes(original)
