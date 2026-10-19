"""Quickstart consistency: config, README and CI must describe the same commands."""

from __future__ import annotations

from pathlib import Path

from rnp.config import load_config

ROOT = Path(__file__).parents[2]


def test_quickstart_config_points_at_fixtures_and_results() -> None:
    config_path = ROOT / "examples" / "quickstart" / "run.yaml"
    assert config_path.is_file()
    config = load_config(config_path)
    assert config.output_dir == (ROOT / "results").resolve()
    for key in ("compounds", "stp_dir", "disease_genes", "hgnc_map"):
        assert config.input_path(key).exists(), key
    assert config.resolve(config.data["enrichment"]["universe_file"]).is_file()


def test_readme_and_ci_use_the_same_quickstart() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for document in (readme, workflow):
        assert "examples/quickstart/run.yaml" in document
        assert "results/quickstart" in document
