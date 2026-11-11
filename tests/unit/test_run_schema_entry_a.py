"""The run config accepts the two inputs of the compounds stage (docs/upstream.md, section 8)."""

from __future__ import annotations

import copy

import pytest
import yaml
from jsonschema import Draft202012Validator

from rnp.config import load_config, load_schema

BASE = {
    "project": "p",
    "species": "Homo_sapiens",
    "inputs": {"compounds": "c.tsv", "stp_dir": "stp", "disease_genes": "d.txt"},
    "thresholds": {"stp_probability": 0.1},
    "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
    "outputs": {"dir": "results"},
}


def problems(**inputs) -> list[str]:
    config = copy.deepcopy(BASE)
    config["inputs"].update(inputs)
    validator = Draft202012Validator(load_schema("run"))
    return [error.message for error in validator.iter_errors(config)]


def test_the_base_config_is_valid():
    assert problems() == []


@pytest.mark.parametrize(
    "key, value",
    [
        ("submission_log", "STP-SUBMISSION-LOG.tsv"),
        ("submission_log", "../logs/log.tsv"),
        ("structure_registry", "registry/structure_registry.tsv"),
        ("structure_registry", "C:/data/structure_registry.tsv"),
    ],
)
def test_each_new_input_is_accepted(key, value):
    assert problems(**{key: value}) == []


def test_both_new_inputs_together_are_accepted():
    assert problems(submission_log="log.tsv", structure_registry="registry.tsv") == []


@pytest.mark.parametrize("key", ["submission_log", "structure_registry"])
@pytest.mark.parametrize("value", ["", 5, 1.5, None, True, ["x.tsv"], {"path": "x.tsv"}])
def test_a_new_input_must_be_a_non_empty_string(key, value):
    assert problems(**{key: value})


@pytest.mark.parametrize("key", ["submission_logs", "structure_registries", "log", "smiles"])
def test_an_unknown_input_is_still_refused(key):
    assert problems(**{key: "x.tsv"})


def test_the_existing_inputs_are_unchanged():
    properties = load_schema("run")["properties"]["inputs"]["properties"]
    assert {
        "compounds",
        "stp_dir",
        "disease_genes",
        "disease_source",
        "disease_retrieval_date",
        "hgnc_map",
        "compound_registry",
        "allow_filename_match",
        "mcode_dir",
        "submission_log",
        "structure_registry",
    } == set(properties)
    assert load_schema("run")["properties"]["inputs"]["required"] == [
        "compounds",
        "stp_dir",
        "disease_genes",
    ]
    assert load_schema("run")["properties"]["inputs"]["additionalProperties"] is False


def test_load_config_resolves_the_new_inputs_next_to_the_config(tmp_path):
    config = copy.deepcopy(BASE)
    config["inputs"].update(submission_log="logs/log.tsv", structure_registry="reg/s.tsv")
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    loaded = load_config(path)
    assert loaded.input_path("submission_log") == (tmp_path / "logs" / "log.tsv").resolve()
    assert loaded.input_path("structure_registry") == (tmp_path / "reg" / "s.tsv").resolve()
