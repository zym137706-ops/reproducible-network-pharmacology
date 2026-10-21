"""Portable case entry preflight and independent statistical checks (synthetic fixtures only)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from rnp.config import load_config

ROOT = Path(__file__).parents[2]


def _module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _args(tmp_path: Path, **overrides):
    run = _module("rnp_case_run", "scripts/case_run.py")
    values = {
        "compounds": ROOT / "tests/fixtures/run/inputs/compounds.tsv",
        "stp_dir": ROOT / "tests/fixtures/run/inputs/stp",
        "disease_genes": ROOT / "tests/fixtures/run/inputs/disease_genes.txt",
        "hgnc_map": ROOT / "tests/fixtures/hgnc/hgnc_map.tsv",
        "log": None,
        "config_template": ROOT / "examples/quickstart/run.yaml",
        "thresholds": ["0.10", "0.05"],
    }
    values.update(overrides)
    return run, type("Args", (), values)()


def test_case_run_preflight_and_configs_are_portable(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    inputs = run.verify_inputs(args)
    assert inputs["compound_rows"] == 2
    assert inputs["stp_files"]
    out = tmp_path / "case"
    out.mkdir()
    configs = run.write_configs(args, out)
    assert set(configs) == {"0.10", "0.05"}
    for label, path in configs.items():
        config = load_config(path)
        assert config.data["thresholds"]["stp_probability"] == float(label)
        assert "data/local" not in str(config.data["inputs"]["disease_genes"])
    provenance = run.source_hash(ROOT)
    assert len(provenance) == 64

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
    provenance = __import__("json").loads(
        (out2 / "case_provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["source"]["source_sha256"] == run.source_hash(ROOT)
    assert set(provenance["configs"]) == {"0.10", "0.05"}


def test_case_run_rejects_unbound_export(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    stp = tmp_path / "stp"
    stp.mkdir()
    (stp / "extra.csv").write_text("Target,Common name,Uniprot ID,Probability\nA,B,P,0.5\n")
    args.stp_dir = stp
    with pytest.raises(ValueError, match="binding mismatch"):
        run.verify_inputs(args)


def test_case_run_rejects_bad_submission_hash(tmp_path: Path) -> None:
    run, args = _args(tmp_path)
    compounds = list(
        __import__("csv").DictReader(
            args.compounds.open(encoding="utf-8"), delimiter="\t"
        )
    )
    log = tmp_path / "log.tsv"
    with log.open("w", encoding="utf-8", newline="") as handle:
        writer = __import__("csv").writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "stp_file",
                "submitted_structure",
                "species",
                "submitted_date",
                "result_sha256",
                "result_url",
                "job_id",
            ]
        )
        for row in compounds:
            writer.writerow(
                [
                    row["stp_file"],
                    "C",
                    "Homo sapiens",
                    "2026-10-21",
                    "0" * 64,
                    "not_saved",
                    "not_saved",
                ]
            )
    args.log = log
    with pytest.raises(ValueError, match="result hash mismatch"):
        run.verify_inputs(args)


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
    # Enforce monotonic BH from the largest p-value downward.
    assert check.bh([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.04, 0.04])
    # P(X >= 1) for population 10, 3 successes, 4 draws = 1 - C(7,4)/C(10,4).
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
