"""Packaged resources and the offline synthetic demo."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rnp.resources import r_script

ROOT = Path(__file__).parents[2]


def test_packaged_r_scripts_are_locatable() -> None:
    script = r_script("venny.R")
    assert script.is_file()
    assert "venn" in script.read_text(encoding="utf-8").lower()


def test_synthetic_demo_matches_hand_computed_tables(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "synthetic_demo.py"),
            "--out",
            str(tmp_path / "demo"),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS: 5 synthetic scenarios" in completed.stdout
