"""R enrichment bridge: contract tests against a committed fixture and a live run.

The committed fixture pins the column contract. The live run (skipped unless an
Rscript binary is available) checks that the bridge still produces that contract
and reports its own package versions.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "ora"
EXPECTED_COLUMNS = [
    "ID",
    "Description",
    "GeneRatio",
    "BgRatio",
    "pvalue",
    "p.adjust",
    "qvalue",
    "geneID",
    "Count",
]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _assert_contract(rows: list[dict[str, str]]) -> None:
    assert rows, "expected at least one enrichment term"
    assert list(rows[0]) == EXPECTED_COLUMNS
    adjusted = [float(row["p.adjust"]) for row in rows]
    assert adjusted == sorted(adjusted), "result must be ordered by p.adjust"
    for row in rows:
        genes = [gene for gene in row["geneID"].split("/") if gene]
        assert genes, f"empty geneID in {row['ID']}"
        assert int(row["Count"]) == len(genes)
        assert row["Description"]


def test_committed_contract_fixture() -> None:
    rows = _read_rows(FIXTURE / "expected" / "enrichment_result.tsv")
    _assert_contract(rows)


def _rscript() -> str | None:
    return os.environ.get("RNP_RSCRIPT") or shutil.which("Rscript")


@pytest.mark.skipif(_rscript() is None, reason="Rscript not available")
def test_live_r_bridge(tmp_path: Path) -> None:
    out_dir = tmp_path / "ora"
    completed = subprocess.run(
        [_rscript(), str(ROOT / "R" / "ora.R"), str(FIXTURE / "input.json"), str(out_dir)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert completed.returncode == 0, completed.stderr

    rows = _read_rows(out_dir / "enrichment_result.tsv")
    _assert_contract(rows)
    assert (out_dir / "entrez_to_symbol.tsv").is_file()

    meta = json.loads((out_dir / "enrichment_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert meta["species"] == "Homo_sapiens"
    assert meta["counts"]["input"] == 25
    assert meta["counts"]["mapped"] == 25
    assert meta["environment"]["packages"]["clusterProfiler"]
    assert meta["params"]["p_adjust"] == "BH"
