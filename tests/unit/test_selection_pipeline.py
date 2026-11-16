"""The whole pipeline with the real toolkit, from `rnp ingest compounds` to `rnp manifest`.

`rnp ingest compounds`, `rnp compounds select`, `rnp ingest stp --compounds --selection`,
`rnp intersect`, `rnp network`, `rnp report` and `rnp manifest` run one after the other on the same
run config (the command line, real RDKit). The test is skipped when RDKit is not installed, unless
RNP_REQUIRE_CHEM is 1 (CI sets it).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from selection_ingest_support import decision, read_tsv
from selection_support import build

from rnp.cli import main


@pytest.fixture
def chem():
    try:
        import rdkit  # noqa: F401
    except ImportError:
        if os.environ.get("RNP_REQUIRE_CHEM") == "1":
            pytest.fail("RDKit is required (RNP_REQUIRE_CHEM=1) but is not installed")
        pytest.skip("RDKit is not installed (optional extra 'chem')")


def test_the_whole_pipeline_works_with_the_real_toolkit(tmp_path, capsys, chem):
    rows = [
        decision("Compound 1", "include"),
        decision("Compound 2", "include"),
        decision("Compound 3", "exclude", reason="no_structure"),
    ]
    scenario = [("CCO", "ok"), ("c1ccccc1", "ok"), ("", None)]
    config = build(tmp_path, rows, scenario)
    base = ["--config", str(config)]
    assert main(["ingest", "compounds", *base, "--run-id", "s"]) == 3
    compounds = Path(json.loads(capsys.readouterr().out)["run_dir"])
    assert (
        main(["compounds", "select", *base, "--compounds", str(compounds), "--run-id", "sel"]) == 0
    )
    selection = Path(json.loads(capsys.readouterr().out)["run_dir"])
    assert (
        main(
            [
                "ingest",
                "stp",
                *base,
                "--run-id",
                "i1",
                "--compounds",
                str(compounds),
                "--selection",
                str(selection),
            ]
        )
        == 0
    )
    printed = json.loads(capsys.readouterr().out)
    assert printed["stage_status"] == "complete"
    run_dir = Path(printed["run_dir"])
    rows = read_tsv(run_dir / "compounds_registered.tsv")
    assert [(row["structure_id"], row["selection_status"]) for row in rows] == [
        ("STR0001", "selected"),
        ("STR0002", "selected"),
        ("", "excluded"),
    ]
    assert main(["intersect", *base, "--targets", str(run_dir / "targets.tsv")]) == 0
    intersect = json.loads(capsys.readouterr().out)
    assert intersect["groups"]["all"]["compounds"] == 2
    assert intersect["groups"]["all"]["compounds_without_edges"] == []
    assert main(["network", *base, "--intersect", str(run_dir / "intersect")]) == 0
    network = json.loads(capsys.readouterr().out)
    assert network["groups"]["all"]["compounds_total"] == 2
    assert main(["report", *base, "--run-dir", str(run_dir)]) == 0
    capsys.readouterr()
    report = next((run_dir / "report").glob("*.md")).read_text(encoding="utf-8")
    assert "- Compound selection: 2 selected, 1 excluded, 0 needs review or quarantined" in report
    assert main(["manifest", "--run-dir", str(run_dir), "--check-inputs"]) == 0
