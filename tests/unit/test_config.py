"""Config loading and schema validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rnp.config import load_config
from rnp.errors import ConfigError


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "run.yaml"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_payload(tmp_path: Path) -> dict:
    return {
        "project": "unit-test",
        "species": "Homo_sapiens",
        "inputs": {
            "compounds": "c.tsv",
            "stp_dir": "stp",
            "disease_genes": "d.txt",
        },
        "thresholds": {"stp_probability": 0.1},
        "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
        "outputs": {"dir": "results"},
    }


def test_valid_config_round_trip(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, _valid_payload(tmp_path)))
    assert config.project == "unit-test"
    assert config.species == "Homo_sapiens"
    assert len(config.sha256) == 64
    assert config.input_path("compounds") == (tmp_path / "c.tsv").resolve()
    assert config.output_dir == (tmp_path / "results").resolve()


def test_relative_paths_resolve_against_config_not_cwd(tmp_path: Path, monkeypatch) -> None:
    nested = tmp_path / "project"
    nested.mkdir()
    config_path = _write(nested, _valid_payload(tmp_path))
    monkeypatch.chdir(tmp_path.parent)
    config = load_config(config_path)
    assert config.input_path("disease_genes") == (nested / "d.txt").resolve()


def test_missing_required_key_is_reported(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    del payload["thresholds"]
    with pytest.raises(ConfigError) as excinfo:
        load_config(_write(tmp_path, payload))
    assert "thresholds" in excinfo.value.render()


def test_unknown_top_level_key_is_rejected(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["extra"] = 1
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, payload))


def test_invalid_species_is_rejected(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["species"] = "Drosophila_melanogaster"
    with pytest.raises(ConfigError) as excinfo:
        load_config(_write(tmp_path, payload))
    assert "species" in excinfo.value.render()


def test_threshold_out_of_range_is_rejected(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["thresholds"]["stp_probability"] = 1.5
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, payload))


def test_non_mapping_config_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "run.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")
