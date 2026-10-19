"""Independent hypergeometric/BH benchmark for the frozen synthetic R path.

The expected p-values and BH-adjusted values are computed in this test from the
combinatorial definition; they are not copied from the R output.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
RSCRIPT = os.environ.get("RNP_RSCRIPT") or shutil.which("Rscript")


def _hypergeom_sf(k: int, population: int, successes: int, draws: int) -> float:
    """P(X >= k) for X ~ Hypergeometric(population, successes, draws)."""
    total = math.comb(population, draws)
    upper = min(successes, draws)
    return sum(
        math.comb(successes, i) * math.comb(population - successes, draws - i)
        for i in range(k, upper + 1)
    ) / total


def _benjamini_hochberg(pvalues: list[float]) -> list[float]:
    count = len(pvalues)
    order = sorted(range(count), key=lambda index: pvalues[index])
    adjusted = [0.0] * count
    previous = 1.0
    for rank in range(count, 0, -1):
        index = order[rank - 1]
        value = min(previous, pvalues[index] * count / rank)
        adjusted[index] = value
        previous = value
    return adjusted


def _read_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not available")
def test_synthetic_hypergeom_and_bh_match_independent_calculation(tmp_path: Path) -> None:
    genes = ["1", "2", "3", "60"]
    gene_sets = {
        "S1": [str(index) for index in range(1, 11)],
        "S2": [str(index) for index in range(1, 6)] + [str(index) for index in range(50, 55)],
        "S3": [str(index) for index in range(60, 71)],
    }
    # clusterProfiler::enricher restricts the background to the union of the
    # provided term genes; the benchmark therefore uses exactly that universe.
    universe = sorted({gene for members in gene_sets.values() for gene in members})
    request = {
        "genes": genes,
        "gene_id_type": "ENTREZID",
        "species": "Homo_sapiens",
        "gene_sets": "GO_BP",
        "p_adjust": "BH",
        "pvalue_cutoff": 1.0,
        "qvalue_cutoff": 1.0,
        "min_gssize": 5,
        "max_gssize": 500,
        "universe": universe,
        "synthetic_gene_sets": gene_sets,
        "output_dir": str(tmp_path / "out"),
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    completed = subprocess.run(
        [RSCRIPT, str(ROOT / "R" / "ora.R"), str(request_path), str(tmp_path / "out")],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert completed.returncode == 0, completed.stderr

    rows = _read_tsv(tmp_path / "out" / "enrichment_result.tsv")
    assert {row["ID"] for row in rows} == {"S1", "S2", "S3"}
    population = len(universe)
    draws = len(genes)
    for row in rows:
        members = set(gene_sets[row["ID"]])
        overlap = len(members & set(genes))
        assert int(row["Count"]) == overlap
        expected = _hypergeom_sf(overlap, population, len(members), draws)
        assert math.isclose(
            float(row["pvalue"]), expected, rel_tol=1e-6, abs_tol=1e-12
        ), row["ID"]

    expected_adjusted = _benjamini_hochberg([float(row["pvalue"]) for row in rows])
    for row, expected in zip(rows, expected_adjusted, strict=True):
        assert math.isclose(
            float(row["p.adjust"]), expected, rel_tol=1e-6, abs_tol=1e-9
        ), row["ID"]

    meta = json.loads((tmp_path / "out" / "enrichment_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert meta["gene_sets"] == "SYNTHETIC"
    assert meta["universe"]["source"] == "explicit"
