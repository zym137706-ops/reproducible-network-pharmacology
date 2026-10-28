"""Ingest: explicit binding, quarantine, stage status, overwrite and registry."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from rnp import __version__
from rnp.analysis.ingest import run_ingest
from rnp.config import load_config, load_schema
from rnp.errors import InputError

FIXTURES = Path(__file__).parents[1] / "fixtures"
HEADER = (
    "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,"
    "Known actives (3D/2D)\n"
)
VALID_A = "A1,CA2,P00918,,X,0.40,No\nA2,TNF,P01375,,X,0.30,No\n"
VALID_B = "B1,IL6,P05231,,X,0.20,No\n"


def _file(rows: str) -> str:
    return HEADER + rows


def _config(
    tmp_path: Path,
    *,
    compounds: str,
    files: dict[str, str],
    allow_filename_match: bool = False,
) -> Path:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "compounds.tsv").write_text(compounds, encoding="utf-8")
    stp = inputs / "stp"
    stp.mkdir()
    for name, body in files.items():
        (stp / name).write_text(_file(body), encoding="utf-8")
    data = {
        "project": "ingest-fixture",
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
    if allow_filename_match:
        data["inputs"]["allow_filename_match"] = True
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _run(tmp_path: Path, config_path: Path, run_id: str = "r1", force: bool = False):
    return run_ingest(load_config(config_path), run_id=run_id, force=force)


def test_complete_run_writes_registry_and_audit(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\tstp_file\nCompoundA\ta.csv\nCompoundB\tb.csv\n",
        files={"a.csv": VALID_A, "b.csv": VALID_B},
    )
    summary = _run(tmp_path, config)
    assert summary["stage_status"] == "complete"
    assert summary["summary"]["rows_used"] == 3
    assert summary["summary"]["files_quarantined"] == 0
    run_dir = Path(summary["run_dir"])

    targets = (run_dir / "targets.tsv").read_text(encoding="utf-8").splitlines()
    assert targets[0].startswith("compound_id\tgroup\tsubmission_id\tsource_file")
    assert len(targets) == 4
    registered = (run_dir / "compounds_registered.tsv").read_text(encoding="utf-8").splitlines()
    assert len(registered) == 3  # header + two compounds

    audit = json.loads((run_dir / "stp_audit.json").read_text(encoding="utf-8"))
    jsonschema.validate(audit, load_schema("stp_audit"))
    assert audit["stage_status"] == "complete"
    assert audit["registry"]["rule_version"] == "v0.1.0-name-registry"
    assert (Path(audit["registry"]["path"])).is_file()

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, load_schema("run_manifest"))
    assert manifest["code"]["version"] == __version__
    assert manifest["config"]["path"] == str(load_config(config).path)
    assert manifest["stage_status"] == "complete"


def test_unbound_export_is_quarantined_not_an_edge(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\tstp_file\nCompoundA\ta.csv\n",
        files={"a.csv": VALID_A, "extra.csv": "X1,ESR1,P03372,,X,0.90,No\n"},
    )
    summary = _run(tmp_path, config)
    assert summary["stage_status"] == "complete"
    assert summary["summary"]["files_quarantined"] == 1
    assert summary["quarantine"][0]["path"] == "extra.csv"
    assert summary["quarantine"][0]["reason"] == "not_bound_to_compound"
    targets = (Path(summary["run_dir"]) / "targets.tsv").read_text(encoding="utf-8")
    assert "ESR1" not in targets


def test_missing_export_makes_stage_partial(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\tstp_file\nCompoundA\ta.csv\nCompoundB\tb.csv\n",
        files={"a.csv": VALID_A},
    )
    summary = _run(tmp_path, config)
    assert summary["stage_status"] == "partial"
    assert summary["missing_exports"][0]["stp_file"] == "b.csv"
    audit = json.loads((Path(summary["run_dir"]) / "stp_audit.json").read_text(encoding="utf-8"))
    assert audit["summary"]["files_missing"] == 1


def test_invalid_rows_are_partial_and_counted_separately(tmp_path: Path) -> None:
    rows = "A1,CA2,P00918,,X,0.40,No\nA2,TNF,P01375,,X,abc,No\nA3,IL6,P05231,,X,0.05,No\n"
    config = _config(
        tmp_path,
        compounds="name\tstp_file\nCompoundA\ta.csv\n",
        files={"a.csv": rows},
    )
    summary = _run(tmp_path, config)
    assert summary["stage_status"] == "partial"
    assert summary["summary"]["rows_invalid"] == 1
    assert summary["summary"]["rows_below_threshold"] == 1
    assert summary["summary"]["rows_used"] == 1


def test_empty_export_is_complete_with_no_predictions(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\tstp_file\nCompoundA\ta.csv\nCompoundB\tb.csv\n",
        files={"a.csv": "", "b.csv": VALID_B},
    )
    summary = _run(tmp_path, config)
    assert summary["stage_status"] == "complete"
    assert summary["summary"]["rows_used"] == 1
    audit = json.loads((Path(summary["run_dir"]) / "stp_audit.json").read_text(encoding="utf-8"))
    statuses = {entry["path"]: entry["status"] for entry in audit["files"]}
    assert statuses["a.csv"] == "no_predictions"


def test_existing_run_is_not_overwritten_without_force(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\tstp_file\nCompoundA\ta.csv\n",
        files={"a.csv": VALID_A},
    )
    _run(tmp_path, config, run_id="same")
    with pytest.raises(InputError) as excinfo:
        _run(tmp_path, config, run_id="same")
    assert "already exists" in excinfo.value.render()
    assert _run(tmp_path, config, run_id="same", force=True)["stage_status"] == "complete"


def test_failed_run_leaves_no_directory(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\tstp_file\nCompoundA\ta.csv\n",
        files={"a.csv": VALID_A},
    )
    (tmp_path / "inputs" / "stp" / "a.csv").write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(InputError):
        _run(tmp_path, config, run_id="broken")
    assert not (tmp_path / "results" / "broken").exists()


def test_filename_compatibility_mode_is_audited(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\nCompoundA\nCompoundB\n",
        files={"CompoundA.csv": VALID_A, "CompoundB.csv": VALID_B},
        allow_filename_match=True,
    )
    summary = _run(tmp_path, config)
    assert summary["stage_status"] == "complete"
    audit = json.loads((Path(summary["run_dir"]) / "stp_audit.json").read_text(encoding="utf-8"))
    notes = {note["code"] for note in audit["notes"]}
    assert "filename_compatibility_match" in notes


def test_ambiguous_filename_is_quarantined(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\nA-B\nA B\nC\n",
        files={"A B.csv": VALID_A, "C.csv": VALID_B},
        allow_filename_match=True,
    )
    summary = _run(tmp_path, config)
    assert summary["summary"]["files_bound"] == 1
    assert summary["summary"]["files_quarantined"] == 1
    assert summary["quarantine"][0]["reason"] == "ambiguous_filename"


def test_registry_reuses_ids_across_runs(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        compounds="name\tstp_file\nCompoundA\ta.csv\n",
        files={"a.csv": VALID_A},
    )
    first = _run(tmp_path, config, run_id="first")
    second = _run(tmp_path, config, run_id="second")
    first_ids = (Path(first["run_dir"]) / "compounds_registered.tsv").read_text(encoding="utf-8")
    second_ids = (Path(second["run_dir"]) / "compounds_registered.tsv").read_text(encoding="utf-8")

    def ids(text: str) -> list[str]:
        return [line.split("\t")[0] for line in text.splitlines()[1:]]

    assert ids(first_ids) == ids(second_ids) == ["CMP0001"]
