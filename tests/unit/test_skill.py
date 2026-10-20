"""The Skill layer must stay thin and only call the existing CLI."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
SKILL = ROOT / "skills" / "np-workflow" / "SKILL.md"


def test_skill_exists_and_declares_name() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert re.search(r"^name:\s*np-workflow\s*$", text, re.MULTILINE)
    assert re.search(r"^description:\s*.+", text, re.MULTILINE)


def test_skill_only_references_existing_cli_commands() -> None:
    text = SKILL.read_text(encoding="utf-8")
    expected = {"validate", "ingest", "intersect", "network", "enrich", "report", "manifest"}
    referenced = set(re.findall(r"rnp\s+([a-z]+)", text)) & expected
    assert referenced == expected
    assert "rnp command" in text


def test_skill_has_no_embedded_business_logic() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "import rnp" not in text
    assert "subprocess" not in text
    assert "```python" not in text
    assert "p.adjust" not in text


def test_skill_keeps_validation_boundary() -> None:
    text = re.sub(r"\s+", " ", SKILL.read_text(encoding="utf-8").lower())
    assert "not validated mechanisms" in text
    assert "prediction" in text
    assert "do not" in text


def test_skill_zero_result_keeps_raw_counts() -> None:
    text = re.sub(r"\s+", " ", SKILL.read_text(encoding="utf-8"))
    assert "empty intersection/network" in text
    assert "do not zero them" in text
    assert "raw target, disease-gene" in text
    assert "no edges or enrichment terms may be invented" in text


def test_skill_reuses_recorded_scientific_decisions() -> None:
    text = re.sub(r"\s+", " ", SKILL.read_text(encoding="utf-8"))
    assert "Recorded decisions: reuse" in text
    assert "Case-specific configuration (not generic defaults)" in text
    assert "ask only when a decision is missing, conflicting or scientifically changed" in text
    assert "explicit `enrichment.universe_file`" in text
    assert "never automate STP submissions" in text
    assert "public case is not complete" in text.lower()
    assert "do not hard-code the quickstart" in text
