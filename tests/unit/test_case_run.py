"""Portable case entry preflight, provenance hash scope and independent-check wiring."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from rnp.config import load_config

ROOT = Path(__file__).parents[2]
QUICKSTART = ROOT / "tests" / "fixtures" / "run" / "inputs"


def _module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _args(tmp_path: Path, **overrides):
    run = _module("rnp_case_run", "scripts/case_run.py")
    values = {
        "compounds": QUICKSTART / "compounds.tsv",
        "stp_dir": QUICKSTART / "stp",
        "disease_genes": QUICKSTART / "disease_genes.txt",
        "hgnc_map": ROOT / "tests/fixtures/hgnc/hgnc_map.tsv",
        "log": None,
        "config_template": ROOT / "examples/quickstart/run.yaml",
        "thresholds": ["0.10", "0.05"],
    }
    values.update(overrides)
    return run, type("Args", (), values)()


def _compounds_with_structures(tmp_path: Path, smiles: list[str]) -> Path:
    rows = list(
        csv.DictReader((QUICKSTART / "compounds.tsv").open(encoding="utf-8"), delimiter="\t")
    )
    assert len(rows) == len(smiles)
    for row, value in zip(rows, smiles, strict=True):
        row["smiles"] = value
    path = tmp_path / "compounds.tsv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_log(
    path: Path,
    compounds: Path,
    stp_dir: Path,
    *,
    structures: dict[str, str] | None = None,
    cid_override: dict[str, str] | None = None,
    hash_override: dict[str, str] | None = None,
) -> None:
    rows = list(csv.DictReader(compounds.open(encoding="utf-8"), delimiter="\t"))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "stp_file",
                "compound",
                "pubchem_cid",
                "submitted_structure",
                "species",
                "submitted_date",
                "result_sha256",
                "result_url",
                "job_id",
            ]
        )
        for row in rows:
            stp = row["stp_file"]
            structure = (structures or {}).get(stp, row["smiles"])
            cid = (cid_override or {}).get(stp, row["pubchem_cid"])
            digest = (hash_override or {}).get(
                stp,
                __import__("hashlib").sha256((stp_dir / stp).read_bytes()).hexdigest(),
            )
            writer.writerow(
                [
                    stp,
                    row["name"],
                    cid,
                    structure,
                    "Homo sapiens",
                    "2026-10-21",
                    digest,
                    "not_saved",
                    "not_saved",
                ]
            )


def test_case_run_preflight_and_configs_are_portable(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    inputs = run.verify_inputs(args)
    assert inputs["compound_rows"] == 2
    assert inputs["stp_files"]
    assert inputs["log"] == {"provided": False}
    out = tmp_path / "case"
    out.mkdir()
    configs = run.write_configs(args, out)
    assert set(configs) == {"0.10", "0.05"}
    for label, path in configs.items():
        config = load_config(path)
        assert config.data["thresholds"]["stp_probability"] == float(label)
        assert "data/local" not in str(config.data["inputs"]["disease_genes"])

    out2 = tmp_path / "case2"
    assert (
        run.main(
            [
                "--compounds",
                str(args.compounds),
                "--stp-dir",
                str(args.stp_dir),
                "--disease-genes",
                str(args.disease_genes),
                "--hgnc-map",
                str(args.hgnc_map),
                "--config-template",
                str(args.config_template),
                "--out",
                str(out2),
                "--preflight-only",
            ]
        )
        == 0
    )
    provenance = json.loads((out2 / "case_provenance.json").read_text(encoding="utf-8"))
    assert provenance["source"]["source_sha256"] == run.source_hash(ROOT)
    assert provenance["source"]["hash_rule"]["version"] == "case-source-hash-v2"
    assert "not the full repository/package" in provenance["source"]["hash_rule"]["scope"]
    assert set(provenance["configs"]) == {"0.10", "0.05"}


def test_case_run_accepts_matching_log(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    args.compounds = _compounds_with_structures(tmp_path, ["CCO", "CCC"])
    log = tmp_path / "log.tsv"
    _write_log(log, args.compounds, args.stp_dir)
    args.log = log
    inputs = run.verify_inputs(args)
    assert inputs["log"]["provided"] is True
    assert inputs["log"]["structures_verified"] is True


def test_case_run_rejects_wrong_submitted_structure(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    args.compounds = _compounds_with_structures(tmp_path, ["CCO", "CCC"])
    log = tmp_path / "log.tsv"
    _write_log(log, args.compounds, args.stp_dir, structures={"compound_a.csv": "C"})
    args.log = log
    with pytest.raises(ValueError, match="submitted_structure"):
        run.verify_inputs(args)


def test_case_run_rejects_binding_and_cid_conflicts(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    args.compounds = _compounds_with_structures(tmp_path, ["CCO", "CCC"])
    log = tmp_path / "log.tsv"
    _write_log(log, args.compounds, args.stp_dir, cid_override={"compound_a.csv": "999"})
    args.log = log
    with pytest.raises(ValueError, match="pubchem_cid"):
        run.verify_inputs(args)

    _write_log(log, args.compounds, args.stp_dir)
    rows = list(csv.DictReader(log.open(encoding="utf-8"), delimiter="\t"))
    rows.append(dict(rows[0]))
    with log.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="duplicate stp_file"):
        run.verify_inputs(args)


def test_case_run_rejects_bad_submission_hash(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    args.compounds = _compounds_with_structures(tmp_path, ["CCO", "CCC"])
    log = tmp_path / "log.tsv"
    _write_log(log, args.compounds, args.stp_dir, hash_override={"compound_a.csv": "0" * 64})
    args.log = log
    with pytest.raises(ValueError, match="result_sha256"):
        run.verify_inputs(args)


def test_case_run_rejects_missing_log_column(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    args.compounds = _compounds_with_structures(tmp_path, ["CCO", "CCC"])
    log = tmp_path / "log.tsv"
    _write_log(log, args.compounds, args.stp_dir)
    rows = list(csv.DictReader(log.open(encoding="utf-8"), delimiter="\t"))
    fields = [field for field in rows[0] if field != "pubchem_cid"]
    with log.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows([{field: row[field] for field in fields} for row in rows])
    args.log = log
    with pytest.raises(ValueError, match="missing columns"):
        run.verify_inputs(args)


def test_case_run_rejects_blank_compound_structure_when_log_is_given(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    log = tmp_path / "log.tsv"
    _write_log(log, args.compounds, args.stp_dir)
    args.log = log
    with pytest.raises(ValueError, match="empty smiles"):
        run.verify_inputs(args)


def test_source_hash_ignores_caches_and_changes_with_controlled_source(tmp_path: Path) -> None:
    run = _module("rnp_case_run", "scripts/case_run.py")
    source = tmp_path / "source"
    for relative in (
        "src/rnp/a.py",
        "R/a.R",
        "schemas/a.json",
        "scripts/case_run.py",
        "scripts/case_check.py",
        "scripts/build_case_background.py",
        "uv.lock",
        "renv.lock",
    ):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")

    first = run.source_hashes(source)
    assert first["version"] == "case-source-hash-v2"
    assert first["combined"]["files"] == 8
    assert run.source_hash(source) == first["combined"]["sha256"]

    cache = source / "src/rnp/__pycache__/a.cpython-312.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"cache")
    second = run.source_hashes(source)
    assert second["combined"]["sha256"] == first["combined"]["sha256"]

    (source / "src/rnp/a.py").write_text("changed", encoding="utf-8")
    third = run.source_hashes(source)
    assert third["combined"]["sha256"] != first["combined"]["sha256"]
    assert third["groups"]["core"]["sha256"] != first["groups"]["core"]["sha256"]
    assert third["groups"]["locks"]["sha256"] == first["groups"]["locks"]["sha256"]


def test_case_run_records_checker_failure(tmp_path: Path, monkeypatch) -> None:
    run, args = _args(tmp_path)

    def fake_run(command, cwd, recorded=None):
        if recorded is not None:
            recorded.append(" ".join(command))
        if any(str(part).endswith("case_check.py") for part in command):
            raise run.CommandFailure(command, 7)

    monkeypatch.setattr(run, "run_command", fake_run)
    out = tmp_path / "case"
    with pytest.raises(SystemExit) as exc:
        run.main(
            [
                "--compounds",
                str(args.compounds),
                "--stp-dir",
                str(args.stp_dir),
                "--disease-genes",
                str(args.disease_genes),
                "--hgnc-map",
                str(args.hgnc_map),
                "--config-template",
                str(args.config_template),
                "--out",
                str(out),
            ]
        )
    assert exc.value.code == 7
    provenance = json.loads((out / "case_provenance.json").read_text(encoding="utf-8"))
    assert provenance["status"] == "failed"
    assert provenance["failed_stage"] == "independent_check"
    assert provenance["child_exit_code"] == 7
    assert any("case_check.py" in command for command in provenance["commands"])


def test_case_run_records_analysis_child_failure(tmp_path: Path, monkeypatch) -> None:
    run, args = _args(tmp_path)

    def fake_run(command, cwd, recorded=None):
        if recorded is not None:
            recorded.append(" ".join(command))
        if "validate" in command:
            raise run.CommandFailure(command, 2)

    monkeypatch.setattr(run, "run_command", fake_run)
    out = tmp_path / "case"
    with pytest.raises(SystemExit) as exc:
        run.main(
            [
                "--compounds",
                str(args.compounds),
                "--stp-dir",
                str(args.stp_dir),
                "--disease-genes",
                str(args.disease_genes),
                "--hgnc-map",
                str(args.hgnc_map),
                "--config-template",
                str(args.config_template),
                "--out",
                str(out),
            ]
        )
    assert exc.value.code == 2
    provenance = json.loads((out / "case_provenance.json").read_text(encoding="utf-8"))
    assert provenance["status"] == "failed"
    assert provenance["failed_stage"] == "validate"
    assert provenance["child_exit_code"] == 2


def test_case_run_rejects_nonempty_output(tmp_path: Path) -> None:
    out = tmp_path / "case"
    out.mkdir()
    (out / "keep.txt").write_text("x", encoding="utf-8")
    run, args = _args(tmp_path)
    args.compounds = tmp_path / "missing.tsv"
    with pytest.raises(SystemExit, match="non-empty output"):
        run.main(
            [
                "--compounds",
                str(args.compounds),
                "--stp-dir",
                str(args.stp_dir),
                "--disease-genes",
                str(args.disease_genes),
                "--hgnc-map",
                str(args.hgnc_map),
                "--out",
                str(out),
            ]
        )


def test_independent_bh_and_hypergeometric() -> None:
    check = _module("rnp_case_check", "scripts/case_check.py")
    assert check.bh([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.04, 0.04])
    expected = 1 - (35 / 210)
    assert check.hypergeom_sf(1, 10, 3, 4) == pytest.approx(expected)
    assert check.hypergeom_sf(0, 10, 3, 4) == 1.0


def test_independent_target_normalisation_excludes_composites() -> None:
    check = _module("rnp_case_check", "scripts/case_check.py")
    from rnp.normalize.hgnc import GeneMapper

    mapper = GeneMapper(ROOT / "tests/fixtures/hgnc/hgnc_map.tsv")
    rows = [
        {"common_name": "CA2", "uniprot_id": "P00918"},
        {"common_name": "CDK5R1 CDK5", "uniprot_id": "", "multi_symbol_common_name": "true"},
        {"common_name": "TNF", "uniprot_id": "P01375", "is_complex": "true"},
    ]
    assert check.normalise_targets(rows, mapper) == {"CA2"}
