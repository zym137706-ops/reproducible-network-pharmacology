"""Acceptance scenarios for the thin Skill: normal, missing, partial, tamper, zero.

The tests call the existing CLI in-process (the Skill has no separate logic) and
assert the observable behaviour recorded in skills/np-workflow/SKILL.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from rnp.cli import main

FIXTURES = Path(__file__).parents[1] / "fixtures"
HEADER = (
    "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,"
    "Known actives (3D/2D)\n"
)


def _config(tmp_path: Path, name: str, *, mutate=None) -> Path:
    data = yaml.safe_load((FIXTURES / "run" / "run.yaml").read_text(encoding="utf-8"))
    data["inputs"] = {
        "compounds": str(FIXTURES / "run" / "inputs" / "compounds.tsv"),
        "stp_dir": str(FIXTURES / "run" / "inputs" / "stp"),
        "disease_genes": str(FIXTURES / "run" / "inputs" / "disease_genes.txt"),
        "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
        "disease_source": "fixture",
        "disease_retrieval_date": "2026-10-01",
    }
    data["enrichment"]["universe_file"] = str(
        FIXTURES / "run" / "inputs" / "universe.txt"
    )
    data["outputs"] = {"dir": str(tmp_path / "results")}
    if mutate:
        mutate(data)
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _run(capsys, args: list[str]) -> tuple[int, str]:
    code = main(args)
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_normal_chain(capsys, tmp_path: Path) -> None:
    config = _config(tmp_path, "run.yaml")
    run_id = "skill-normal"
    assert _run(capsys, ["validate", "--config", str(config)])[0] == 0
    assert _run(capsys, ["ingest", "stp", "--config", str(config), "--run-id", run_id])[0] == 0
    run_dir = tmp_path / "results" / run_id
    assert _run(
        capsys,
        ["intersect", "--config", str(config), "--targets", str(run_dir / "targets.tsv")],
    )[0] == 0
    assert _run(
        capsys,
        ["network", "--config", str(config), "--intersect", str(run_dir / "intersect")],
    )[0] == 0
    assert _run(
        capsys,
        ["report", "--config", str(config), "--run-dir", str(run_dir)],
    )[0] == 0
    audit = json.loads((run_dir / "report" / "report_audit.json").read_text(encoding="utf-8"))
    assert audit["stage_status"] == "complete"
    assert set(audit["stages"]) == {"ingest", "intersect", "network"}


def test_missing_input_is_a_clean_input_error(capsys, tmp_path: Path) -> None:
    def mutate(data):
        data["inputs"]["disease_genes"] = str(tmp_path / "does-not-exist.txt")

    config = _config(tmp_path, "missing.yaml", mutate=mutate)
    code, output = _run(capsys, ["validate", "--config", str(config)])
    assert code == 2
    assert "does-not-exist.txt" in output
    assert not (tmp_path / "results").exists()


def test_missing_export_is_partial_and_downstream_refuses(capsys, tmp_path: Path) -> None:
    stp = tmp_path / "stp"
    stp.mkdir()
    (stp / "a.csv").write_text(HEADER + "A1,TNF,P01375,,X,0.40,No\n", encoding="utf-8")
    compounds = tmp_path / "compounds.tsv"
    compounds.write_text("name\tstp_file\nA\ta.csv\nB\tb.csv\n", encoding="utf-8")

    def mutate(data):
        data["inputs"]["compounds"] = str(compounds)
        data["inputs"]["stp_dir"] = str(stp)

    config = _config(tmp_path, "partial.yaml", mutate=mutate)
    code, output = _run(capsys, ["ingest", "stp", "--config", str(config), "--run-id", "p"])
    assert code == 3, output
    run_dir = tmp_path / "results" / "p"
    audit = json.loads((run_dir / "stp_audit.json").read_text(encoding="utf-8"))
    assert audit["stage_status"] == "partial"

    code, output = _run(
        capsys,
        ["intersect", "--config", str(config), "--targets", str(run_dir / "targets.tsv")],
    )
    assert code == 2, output
    assert "partial" in output.lower()
    assert not (run_dir / "intersect").exists()

    code, output = _run(
        capsys,
        [
            "intersect",
            "--config",
            str(config),
            "--targets",
            str(run_dir / "targets.tsv"),
            "--allow-partial",
        ],
    )
    assert code == 0, output
    intersect_audit = json.loads(
        (run_dir / "intersect" / "intersect_audit.json").read_text(encoding="utf-8")
    )
    assert intersect_audit["stage_status"] == "partial_override"

    code, output = _run(
        capsys, ["report", "--config", str(config), "--run-dir", str(run_dir)]
    )
    assert code == 2, output
    assert "incomplete stages" in output


def test_tampered_hash_blocks_report(capsys, tmp_path: Path) -> None:
    config = _config(tmp_path, "run.yaml")
    run_id = "skill-tamper"
    assert _run(capsys, ["ingest", "stp", "--config", str(config), "--run-id", run_id])[0] == 0
    run_dir = tmp_path / "results" / run_id
    targets = run_dir / "targets.tsv"
    targets.write_text(targets.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    code, output = _run(
        capsys, ["report", "--config", str(config), "--run-dir", str(run_dir)]
    )
    assert code == 2, output
    assert "changed since upstream" in output and "targets.tsv" in output
    assert not (run_dir / "report").exists()


def test_zero_result_is_empty_not_an_error(capsys, tmp_path: Path) -> None:
    disease = tmp_path / "disease.txt"
    disease.write_text("ICAM1\n", encoding="utf-8")

    def mutate(data):
        data["inputs"]["disease_genes"] = str(disease)

    config = _config(tmp_path, "zero.yaml", mutate=mutate)
    run_id = "skill-zero"
    assert _run(capsys, ["ingest", "stp", "--config", str(config), "--run-id", run_id])[0] == 0
    run_dir = tmp_path / "results" / run_id
    assert _run(
        capsys,
        ["intersect", "--config", str(config), "--targets", str(run_dir / "targets.tsv")],
    )[0] == 0
    assert _run(
        capsys,
        ["network", "--config", str(config), "--intersect", str(run_dir / "intersect")],
    )[0] == 0
    code, output = _run(
        capsys, ["report", "--config", str(config), "--run-dir", str(run_dir)]
    )
    assert code == 0, output
    audit = json.loads((run_dir / "report" / "report_audit.json").read_text(encoding="utf-8"))
    assert audit["stage_status"] == "empty"
    text = (run_dir / "report" / "report.md").read_text(encoding="utf-8")
    assert re.search(r"\| all \| \d+ \| \d+ \| \d+ \| \d+ \| 0 \|", text)
    assert "No term passed" not in text  # enrichment was not run in this scenario
