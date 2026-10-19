"""CLI behaviour: exit codes, run directories, manifest checks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from rnp.cli import main

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _tmp_config(tmp_path: Path, *, drop_b: bool = False) -> Path:
    inputs = tmp_path / "inputs"
    shutil.copytree(FIXTURES / "run" / "inputs", inputs)
    if drop_b:
        (inputs / "stp" / "compound_b.csv").unlink()
    data = yaml.safe_load((FIXTURES / "run" / "run.yaml").read_text(encoding="utf-8"))
    data["inputs"] = {
        "compounds": str(inputs / "compounds.tsv"),
        "stp_dir": str(inputs / "stp"),
        "disease_genes": str(inputs / "disease_genes.txt"),
        "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
    }
    data["outputs"] = {"dir": str(tmp_path / "results")}
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_validate_ok(run_config_path: Path, capsys) -> None:
    assert main(["validate", "--config", str(run_config_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["export_files"] == "2"


def test_validate_missing_inputs_returns_2(tmp_path: Path, run_config_path: Path) -> None:
    data = yaml.safe_load(run_config_path.read_text(encoding="utf-8"))
    data["inputs"]["stp_dir"] = str(tmp_path / "does-not-exist")
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert main(["validate", "--config", str(broken)]) == 2


def test_validate_invalid_schema_returns_2(tmp_path: Path, run_config_path: Path) -> None:
    data = yaml.safe_load(run_config_path.read_text(encoding="utf-8"))
    del data["thresholds"]
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert main(["validate", "--config", str(broken)]) == 2


def test_ingest_cli_and_manifest_check(tmp_path: Path, capsys) -> None:
    config = _tmp_config(tmp_path)
    assert main(["ingest", "stp", "--config", str(config), "--run-id", "cli"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stage_status"] == "complete"
    assert payload["summary"]["rows_used"] == 6
    run_dir = Path(payload["run_dir"])
    assert len((run_dir / "targets.tsv").read_text(encoding="utf-8").splitlines()) == 7

    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 0
    check = json.loads(capsys.readouterr().out)
    assert check["stage_status"] == "complete"
    assert check["inputs_checked"] >= 1


def test_ingest_refuses_existing_run_without_force(tmp_path: Path) -> None:
    config = _tmp_config(tmp_path)
    assert main(["ingest", "stp", "--config", str(config), "--run-id", "same"]) == 0
    assert main(["ingest", "stp", "--config", str(config), "--run-id", "same"]) == 2
    assert main(["ingest", "stp", "--config", str(config), "--run-id", "same", "--force"]) == 0


def test_partial_ingest_returns_3(tmp_path: Path) -> None:
    config = _tmp_config(tmp_path, drop_b=True)
    assert main(["ingest", "stp", "--config", str(config), "--run-id", "p"]) == 3


def test_intersect_and_network_cli(tmp_path: Path, capsys) -> None:
    config = _tmp_config(tmp_path)
    assert main(["ingest", "stp", "--config", str(config), "--run-id", "chain"]) == 0
    run_dir = Path(json.loads(capsys.readouterr().out)["run_dir"])

    assert (
        main(
            [
                "intersect",
                "--config",
                str(config),
                "--targets",
                str(run_dir / "targets.tsv"),
            ]
        )
        == 0
    )
    intersect_summary = json.loads(capsys.readouterr().out)
    assert intersect_summary["groups"]["all"]["intersection"] == 2

    assert (
        main(
            [
                "network",
                "--config",
                str(config),
                "--intersect",
                str(run_dir / "intersect"),
            ]
        )
        == 0
    )
    network_summary = json.loads(capsys.readouterr().out)
    assert network_summary["groups"]["all"]["network_edges"] == 4
    assert (run_dir / "network" / "all" / "edges.tsv").is_file()


def test_network_without_intersect_returns_2(tmp_path: Path) -> None:
    config = _tmp_config(tmp_path)
    assert (
        main(
            [
                "network",
                "--config",
                str(config),
                "--intersect",
                str(tmp_path / "missing"),
            ]
        )
        == 2
    )


def test_manifest_detects_input_drift(tmp_path: Path, capsys) -> None:
    config = _tmp_config(tmp_path)
    assert main(["ingest", "stp", "--config", str(config), "--run-id", "drift"]) == 0
    run_dir = Path(json.loads(capsys.readouterr().out)["run_dir"])
    with (tmp_path / "inputs" / "stp" / "compound_a.csv").open("a", encoding="utf-8") as handle:
        handle.write("Extra,TNF,P01375,,X,0.20,No\n")
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 3


@pytest.mark.parametrize(
    "command",
    [
        ["ingest", "stp", "--config", "missing.yaml"],
        ["validate", "--config", "missing.yaml"],
    ],
)
def test_missing_config_returns_2(command: list[str]) -> None:
    assert main(command) == 2
