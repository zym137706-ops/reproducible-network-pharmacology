"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def run_config_path(tmp_path: Path) -> Path:
    """A valid run config with absolute fixture inputs and a temporary output dir."""
    data = yaml.safe_load((FIXTURES / "run" / "run.yaml").read_text(encoding="utf-8"))
    data["inputs"] = {
        "compounds": str(FIXTURES / "run" / "inputs" / "compounds.tsv"),
        "stp_dir": str(FIXTURES / "run" / "inputs" / "stp"),
        "disease_genes": str(FIXTURES / "run" / "inputs" / "disease_genes.txt"),
        "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
        "disease_source": "CTD",
        "disease_retrieval_date": "2026-10-01",
    }
    data["outputs"] = {"dir": str(tmp_path / "results")}
    enrichment = data.get("enrichment", {})
    if "universe_file" in enrichment:
        enrichment["universe_file"] = str(FIXTURES / "run" / "inputs" / "universe.txt")
    path = tmp_path / "run.yaml"
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


@pytest.fixture
def ingest_run(tmp_path: Path, run_config_path: Path, capsys) -> Path:
    """Run `rnp ingest stp` on the fixture and return the results directory."""
    from rnp.cli import main

    assert main(["ingest", "stp", "--config", str(run_config_path), "--run-id", "chain"]) == 0
    payload = json.loads(capsys.readouterr().out)
    return Path(payload["run_dir"])


@pytest.fixture
def intersect_run(ingest_run: Path, run_config_path: Path, capsys) -> tuple[Path, Path]:
    """Run `rnp intersect` on top of the fixture ingest; return (config, intersect dir)."""
    from rnp.cli import main

    out_dir = ingest_run / "intersect"
    assert (
        main(
            [
                "intersect",
                "--config",
                str(run_config_path),
                "--targets",
                str(ingest_run / "targets.tsv"),
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()
    return run_config_path, out_dir
