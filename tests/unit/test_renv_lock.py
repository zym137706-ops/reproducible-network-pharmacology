"""The R lock must exist, parse, and pin the packages the bridge imports."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
LOCK = ROOT / "renv.lock"


def test_renv_lock_records_r_and_bridge_packages() -> None:
    data = json.loads(LOCK.read_text(encoding="utf-8"))
    assert data["R"]["Version"] == "4.5.2"
    packages = data["Packages"]
    for name in ("clusterProfiler", "DOSE", "org.Hs.eg.db", "GO.db", "AnnotationDbi", "jsonlite"):
        assert name in packages, name
        assert packages[name].get("Version"), name
    assert len(packages) >= 100


def test_renv_lock_does_not_point_at_a_local_library() -> None:
    text = LOCK.read_text(encoding="utf-8")
    assert "C:/" not in text and "C:\\" not in text
    assert "rnp-renv-clean" not in text
