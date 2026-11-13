"""The wiring of the binding recheck in case_run.py: what the checker is given and what is recorded.

The child commands are replaced by the recording stand-in of case_run_support.FakeChain, and
`structure_preflight` by a fixed answer, so none of this needs RDKit, R or the network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from case_run_support import (
    ROOT,
    FakeChain,
    argv_for,
    case_args,
    load_run,
    one,
    option,
)

STRUCTURES = {
    "mode": "structure",
    "toolkit": {"name": "rdkit", "version": "2026.09.1"},
    "rows": 2,
    "submission_status_counts": {"verified": 2},
    "issue_code_counts": {},
}
LABELS = ["0.05", "0.10"]


def is_check(command: list[str]) -> bool:
    return any(part.endswith("case_check.py") for part in command)


def run_chain(tmp_path: Path, monkeypatch, *, log: bool = True, fail=None, **overrides):
    """Run main() with the stand-ins; return (chain, output directory, exit code, args)."""
    run = load_run()
    chain = FakeChain(run, fail)
    monkeypatch.setattr(run, "run_command", chain)
    monkeypatch.setattr(run, "structure_preflight", lambda args: dict(STRUCTURES))
    args = case_args(tmp_path / "case", log=log, **overrides)
    out = tmp_path / "out"
    try:
        code = run.main(argv_for(args, out))
    except SystemExit as exc:
        code = exc.code
    return chain, out, code, args


def the_check(chain: FakeChain) -> list[str]:
    return chain.commands[one([p for p, c in enumerate(chain.commands) if is_check(c)])]


def values_of(command: list[str], name: str) -> list[str]:
    return [command[i + 1] for i, part in enumerate(command) if part == name]


def provenance_of(out: Path) -> dict:
    return json.loads((out / "case_provenance.json").read_text(encoding="utf-8"))


# --- with a log --------------------
def test_with_a_log_the_checker_gets_the_inputs_the_species_and_every_stage(
    tmp_path, monkeypatch
) -> None:
    chain, out, code, args = run_chain(tmp_path, monkeypatch)
    assert code == 0
    command = the_check(chain)
    assert option(command, "--compound-table") == str(args.compounds.resolve())
    assert option(command, "--stp-dir") == str(args.stp_dir.resolve())
    assert option(command, "--log") == str(args.log.resolve())
    assert option(command, "--species") == "Homo_sapiens"
    assert values_of(command, "--stage") == [
        f"{label}={out / label / 'run_compounds'}" for label in LABELS
    ]
    assert values_of(command, "--run") == [f"{label}={out / label / 'run'}" for label in LABELS]


def test_the_species_is_the_one_of_the_config_template(tmp_path, monkeypatch) -> None:
    template = tmp_path / "template.yaml"
    text = (ROOT / "examples" / "quickstart" / "run.yaml").read_text(encoding="utf-8")
    assert "species: Homo_sapiens" in text
    template.write_text(text.replace("species: Homo_sapiens", "species: Mus_musculus"), "utf-8")
    chain, out, code, args = run_chain(tmp_path, monkeypatch, config_template=template)
    assert code == 0
    assert option(the_check(chain), "--species") == "Mus_musculus"
    config = yaml.safe_load((out / "configs" / "run-0.10.yaml").read_text(encoding="utf-8"))
    assert config["species"] == "Mus_musculus"


def test_one_threshold_gives_one_stage(tmp_path, monkeypatch) -> None:
    run = load_run()
    chain = FakeChain(run)
    monkeypatch.setattr(run, "run_command", chain)
    monkeypatch.setattr(run, "structure_preflight", lambda args: dict(STRUCTURES))
    args = case_args(tmp_path / "case")
    out = tmp_path / "out"
    assert run.main([*argv_for(args, out), "--thresholds", "0.10"]) == 0
    command = the_check(chain)
    assert values_of(command, "--stage") == [f"0.10={out / '0.10' / 'run_compounds'}"]
    assert values_of(command, "--run") == [f"0.10={out / '0.10' / 'run'}"]


def test_the_provenance_records_the_recheck_after_it_passed(tmp_path, monkeypatch) -> None:
    chain, out, code, args = run_chain(tmp_path, monkeypatch)
    assert code == 0
    provenance = provenance_of(out)
    assert provenance["status"] == "complete"
    log = provenance["inputs"]["log"]
    assert log["binding_recheck"] == {
        "tool": "scripts/case_check.py",
        "rule": "case-binding-recheck-v1",
        "result": "passed",
    }
    assert log["verified_by"] == "rnp ingest compounds"
    assert log["policy"] == "case-log-policy-v2"
    assert log["provided"] is True


def test_a_failed_recheck_is_not_recorded_as_passed(tmp_path, monkeypatch) -> None:
    chain, out, code, args = run_chain(
        tmp_path, monkeypatch, fail=lambda command: 1 if is_check(command) else None
    )
    assert code == 1
    provenance = provenance_of(out)
    assert provenance["status"] == "failed"
    assert provenance["failed_stage"] == "independent_check"
    assert provenance["child_exit_code"] == 1
    assert "binding_recheck" not in provenance["inputs"]["log"]
    assert any("--stage" in command for command in provenance["commands"])


def test_the_recheck_is_not_recorded_when_an_earlier_stage_fails(tmp_path, monkeypatch) -> None:
    chain, out, code, args = run_chain(
        tmp_path, monkeypatch, fail=lambda command: 3 if "intersect" in command else None
    )
    assert code == 3
    provenance = provenance_of(out)
    assert provenance["failed_stage"] == "intersect"
    assert "binding_recheck" not in provenance["inputs"]["log"]
    assert not any(is_check(command) for command in chain.commands)


# --- without a log: nothing changes --------------------
def test_without_a_log_the_checker_command_is_the_old_one(tmp_path, monkeypatch) -> None:
    chain, out, code, args = run_chain(tmp_path, monkeypatch, log=False)
    assert code == 0
    assert the_check(chain) == [
        sys.executable,
        str(ROOT / "scripts" / "case_check.py"),
        "--run",
        f"0.05={out / '0.05' / 'run'}",
        "--run",
        f"0.10={out / '0.10' / 'run'}",
        "--background-dir",
        str(out / "backgrounds"),
        "--disease-genes",
        str(args.disease_genes.resolve()),
        "--hgnc-map",
        str(args.hgnc_map.resolve()),
        "--out",
        str(out / "independent-check.json"),
    ]


def test_without_a_log_the_provenance_has_no_recheck(tmp_path, monkeypatch) -> None:
    chain, out, code, args = run_chain(tmp_path, monkeypatch, log=False)
    assert code == 0
    assert provenance_of(out)["inputs"]["log"] == {"provided": False}
