"""Windows R/DOSE exit-status regression: warnings on stderr are not failures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
RSCRIPT = os.environ.get("RNP_RSCRIPT") or shutil.which("Rscript")


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not available")
def test_r_warning_keeps_zero_exit_status(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            RSCRIPT,
            "-e",
            "warning('dose-like warning'); cat('ok\\n'); quit(save='no', status=0)",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0
    assert "dose-like warning" in completed.stderr


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not available")
def test_ora_bridge_exits_zero_even_with_dose_stderr(tmp_path: Path) -> None:
    request = {
        "genes": ["TNF", "PTGS2"],
        "gene_id_type": "SYMBOL",
        "species": "Homo_sapiens",
        "gene_sets": "GO_BP",
        "p_adjust": "BH",
        "pvalue_cutoff": 0.05,
        "qvalue_cutoff": 0.2,
        "min_gssize": 5,
        "max_gssize": 500,
        "universe": ["TNF", "PTGS2", "IL6", "IL1B", "CXCL8", "NFKB1"],
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
    meta = json.loads((tmp_path / "out" / "enrichment_meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert meta["environment"]["r_version"]
