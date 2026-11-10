"""The optional `chem` extra: pyproject.toml, the lock file and the CI workflow.

RDKit is optional. The core dependencies stay as they were, the lock file has RDKit under the extra,
and CI installs the extra and refuses to skip the RDKit tests (RNP_REQUIRE_CHEM=1).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def pyproject() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_the_core_dependencies_are_unchanged():
    block = re.search(r"^dependencies = \[(.*?)\]", pyproject(), re.S | re.M)
    assert block is not None
    assert re.findall(r'"([^"]+)"', block.group(1)) == [
        "openpyxl>=3.1",
        "jsonschema>=4.21",
        "PyYAML>=6.0",
    ]


def test_the_chem_extra_is_rdkit_within_the_tested_major_version():
    extras = re.search(
        r"^\[project\.optional-dependencies\]\n(.*?)(?=^\[)", pyproject(), re.S | re.M
    )
    assert extras is not None
    lines = [line.strip() for line in extras.group(1).splitlines() if line.strip()]
    assert 'dev = ["pytest>=8.0", "ruff>=0.5"]' in lines
    assert 'chem = ["rdkit>=2026.3.1,<2027"]' in lines
    assert len(lines) == 2


def test_the_lock_file_has_rdkit_under_the_chem_extra():
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert re.search(r'^name = "rdkit"\nversion = "2026\.', lock, re.M)
    assert re.search(r'chem = \[\s*\{ name = "rdkit" \},?\s*\]', lock)
    assert re.search(r'name = "reproducible-network-pharmacology"', lock)


def test_the_lock_file_keeps_the_dev_extra():
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert re.search(r'dev = \[\s*\{ name = "pytest" \}', lock)


def workflow() -> dict:
    return yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))


def test_ci_installs_the_chem_extra_for_the_test_job():
    steps = workflow()["jobs"]["lint-test"]["steps"]
    installs = [step["run"] for step in steps if "uv sync" in step.get("run", "")]
    assert installs, "the test job must install from the lock file"
    assert all("--locked" in run for run in installs)
    assert any("--extra dev" in run and "--extra chem" in run for run in installs)


def test_ci_refuses_to_skip_the_rdkit_tests():
    steps = workflow()["jobs"]["lint-test"]["steps"]
    test_steps = [step for step in steps if step.get("name") == "Test"]
    assert len(test_steps) == 1
    assert test_steps[0]["env"]["RNP_REQUIRE_CHEM"] == "1"
    assert "pytest" in test_steps[0]["run"]


def test_the_wheel_check_still_installs_without_extras():
    steps = workflow()["jobs"]["lint-test"]["steps"]
    wheel_steps = [step for step in steps if "pip install" in step.get("run", "")]
    assert wheel_steps
    assert all("chem" not in step["run"] for step in wheel_steps)
