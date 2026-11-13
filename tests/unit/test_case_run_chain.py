"""The chain of case_run.py: which commands run, in which order, and what the provenance records.

The child commands are replaced by a recording stand-in (case_run_support.FakeChain) that also
writes the files a compounds stage would write, and `structure_preflight` (the run of the real
command in the preflight) is replaced by a fixed answer, so none of this needs RDKit, R or the
network.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from case_run_support import (
    FakeChain,
    argv_for,
    case_args,
    load_run,
    one,
    option,
    sha256_of,
)

STRUCTURES = {
    "mode": "structure",
    "toolkit": {"name": "rdkit", "version": "2026.09.1"},
    "rows": 2,
    "submission_status_counts": {"verified": 2},
    "issue_code_counts": {},
}
LABELS = ["0.05", "0.10"]


def run_chain(tmp_path: Path, monkeypatch, *, log: bool = True, fail=None):
    """Run main() with the stand-ins; return (module, chain, output directory, exit code, args)."""
    run = load_run()
    chain = FakeChain(run, fail)
    monkeypatch.setattr(run, "run_command", chain)
    monkeypatch.setattr(run, "structure_preflight", lambda args: dict(STRUCTURES))
    args = case_args(tmp_path / "case", log=log)
    out = tmp_path / "out"
    try:
        code = run.main(argv_for(args, out))
    except SystemExit as exc:
        code = exc.code
    return run, chain, out, code, args


def provenance_of(out: Path) -> dict:
    return json.loads((out / "case_provenance.json").read_text(encoding="utf-8"))


def stage_dir(out: Path, label: str) -> Path:
    return out / label / "run_compounds"


# --- with a log --------------------
def test_with_a_log_each_threshold_runs_the_compounds_stage_first(tmp_path, monkeypatch) -> None:
    run, chain, out, code, args = run_chain(tmp_path, monkeypatch)
    assert code == 0
    positions = chain.find("ingest", "compounds")
    assert len(positions) == 2
    for label in LABELS:
        position = one(chain.find("ingest", "compounds", config=f"run-{label}.yaml"))
        command = chain.commands[position]
        assert command[1:3] == ["-m", "rnp.cli"]
        assert command[3:5] == ["ingest", "compounds"]
        assert option(command, "--run-id") == "run"
        assert Path(option(command, "--config")) == out / "configs" / f"run-{label}.yaml"
        stp = one(chain.find("ingest", "stp", config=f"run-{label}.yaml"))
        assert position < stp
    assert chain.find("validate")[-1] < positions[0]
    assert positions[-1] < chain.find("ingest", "stp")[0]


def test_ingest_stp_reads_the_stage_of_its_own_threshold(tmp_path, monkeypatch) -> None:
    run, chain, out, _, args = run_chain(tmp_path, monkeypatch)
    for label in LABELS:
        command = chain.commands[one(chain.find("ingest", "stp", config=f"run-{label}.yaml"))]
        assert option(command, "--compounds") == str(stage_dir(out, label))
        assert option(command, "--run-id") == "run"
        assert option(command, "--config") == str(out / "configs" / f"run-{label}.yaml")
    # nothing else is given the stage
    assert len([c for c in chain.commands if "--compounds" in c]) == 2


def test_the_stage_directories_are_checked_after_the_run_directories(tmp_path, monkeypatch) -> None:
    run, chain, out, _, args = run_chain(tmp_path, monkeypatch)
    check = chain.find("manifest", "--check-inputs")
    assert len(check) == 4
    for label in LABELS:
        in_run = [
            p for p in check if option(chain.commands[p], "--run-dir") == str(out / label / "run")
        ]
        in_stage = [
            p for p in check if option(chain.commands[p], "--run-dir") == str(stage_dir(out, label))
        ]
        assert len(in_run) == 1 and len(in_stage) == 1
        report = one(chain.find("report", config=f"run-{label}.yaml"))
        assert report < in_run[0] < in_stage[0]
    last = max(chain.find("manifest", "--check-inputs"))
    case_check = [
        p for p, c in enumerate(chain.commands) if any(x.endswith("case_check.py") for x in c)
    ]
    assert len(case_check) == 1 and last < case_check[0]


def test_the_commands_are_recorded_in_the_provenance(tmp_path, monkeypatch) -> None:
    run, chain, out, _, args = run_chain(tmp_path, monkeypatch)
    assert provenance_of(out)["commands"] == [" ".join(command) for command in chain.commands]


def test_the_configs_of_the_chain_name_the_log(tmp_path, monkeypatch) -> None:
    run, chain, out, _, args = run_chain(tmp_path, monkeypatch)
    for label in LABELS:
        config = yaml.safe_load((out / "configs" / f"run-{label}.yaml").read_text(encoding="utf-8"))
        assert config["inputs"]["submission_log"] == str(args.log.resolve())


def test_the_provenance_records_the_policy_the_structures_and_the_stage_hashes(
    tmp_path, monkeypatch
) -> None:
    run, chain, out, _, args = run_chain(tmp_path, monkeypatch)
    provenance = provenance_of(out)
    assert provenance["status"] == "complete"
    inputs = provenance["inputs"]
    assert inputs["log"]["provided"] is True
    assert inputs["log"]["verified_by"] == "rnp ingest compounds"
    assert inputs["log"]["policy"] == "case-log-policy-v2"
    assert inputs["structures"] == STRUCTURES
    assert sorted(inputs["compounds_stage"]) == LABELS
    for label in LABELS:
        directory = stage_dir(out, label)
        assert inputs["compounds_stage"][label] == {
            "dir": str(directory),
            "audit_sha256": sha256_of(directory / "compounds_audit.json"),
            "table_sha256": sha256_of(directory / "compound_structures.tsv"),
        }


# --- without a log: nothing changes --------------------
def test_without_a_log_the_chain_is_the_old_chain(tmp_path, monkeypatch) -> None:
    run, chain, out, code, args = run_chain(tmp_path, monkeypatch, log=False)
    assert code == 0
    assert chain.find("ingest", "compounds") == []
    assert [c for c in chain.commands if "--compounds" in c] == []
    assert len(chain.find("ingest", "stp")) == 2
    assert len(chain.find("manifest", "--check-inputs")) == 2
    assert len(chain.commands) == 2 + 2 + 1 + 2 * 5 + 1
    provenance = provenance_of(out)
    assert provenance["inputs"]["log"] == {"provided": False}
    assert "structures" not in provenance["inputs"]
    assert "compounds_stage" not in provenance["inputs"]
    for label in LABELS:
        config = yaml.safe_load((out / "configs" / f"run-{label}.yaml").read_text(encoding="utf-8"))
        assert "submission_log" not in config["inputs"]
    assert not any(stage_dir(out, label).exists() for label in LABELS)


def test_the_preflight_of_the_structures_is_not_asked_without_a_log(tmp_path, monkeypatch) -> None:
    run = load_run()
    monkeypatch.setattr(run, "run_command", FakeChain(run))
    monkeypatch.setattr(
        run, "structure_preflight", lambda args: pytest.fail("the structures were preflighted")
    )
    args = case_args(tmp_path / "case", log=False)
    assert run.main(argv_for(args, tmp_path / "out")) == 0


def test_write_configs_adds_the_log_and_nothing_else(tmp_path) -> None:
    run = load_run()
    with_log = case_args(tmp_path / "a", log=True)
    without = SimpleNamespace(**{**vars(with_log), "log": None})
    # both calls write to the same directory: read the first result before the second overwrites it
    first = {
        label: yaml.safe_load(path.read_text(encoding="utf-8"))
        for label, path in run.write_configs(with_log, tmp_path / "out").items()
    }
    second = {
        label: yaml.safe_load(path.read_text(encoding="utf-8"))
        for label, path in run.write_configs(without, tmp_path / "out").items()
    }
    assert sorted(first) == sorted(second) == LABELS
    for label, config in first.items():
        assert list(config["inputs"])[-1] == "submission_log"
        assert config["inputs"].pop("submission_log") == str(with_log.log.resolve())
        assert config == second[label]
        assert "submission_log" not in second[label]["inputs"]


# --- the preflight happens before anything is written --------------------
def test_a_rejected_structure_layer_creates_no_output(tmp_path, monkeypatch) -> None:
    run = load_run()
    chain = FakeChain(run)
    monkeypatch.setattr(run, "run_command", chain)

    def refuse(args):
        raise ValueError("the structure layer says no")

    monkeypatch.setattr(run, "structure_preflight", refuse)
    args = case_args(tmp_path / "case")
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="the structure layer says no"):
        run.main(argv_for(args, out))
    assert not out.exists()
    assert chain.commands == []


def test_a_preflight_only_run_does_not_run_the_chain(tmp_path, monkeypatch) -> None:
    run = load_run()
    chain = FakeChain(run)
    monkeypatch.setattr(run, "run_command", chain)
    monkeypatch.setattr(run, "structure_preflight", lambda args: dict(STRUCTURES))
    args = case_args(tmp_path / "case")
    out = tmp_path / "out"
    assert run.main(argv_for(args, out, preflight_only=True)) == 0
    assert chain.commands == []
    provenance = provenance_of(out)
    assert provenance["status"] == "preflight_only"
    assert provenance["inputs"]["structures"] == STRUCTURES
    assert "compounds_stage" not in provenance["inputs"]


# --- failures --------------------
def stage_command(command: list[str]) -> bool:
    return "ingest" in command and "compounds" in command


def test_a_failed_compounds_stage_is_recorded_with_its_own_name_and_code(
    tmp_path, monkeypatch
) -> None:
    run, chain, out, code, args = run_chain(
        tmp_path, monkeypatch, fail=lambda c: 5 if stage_command(c) else None
    )
    assert code == 5
    provenance = provenance_of(out)
    assert provenance["status"] == "failed"
    assert provenance["failed_stage"] == "ingest_compounds"
    assert provenance["child_exit_code"] == 5
    assert "ingest compounds" in provenance["failed_command"]
    assert chain.find("ingest", "stp") == []
    assert provenance["inputs"].get("compounds_stage", {}) == {}


def test_a_failure_of_ingest_stp_keeps_its_old_name(tmp_path, monkeypatch) -> None:
    run, chain, out, code, args = run_chain(
        tmp_path, monkeypatch, fail=lambda c: 3 if "stp" in c and "ingest" in c else None
    )
    assert code == 3
    provenance = provenance_of(out)
    assert provenance["failed_stage"] == "ingest"
    assert provenance["child_exit_code"] == 3
    assert sorted(provenance["inputs"]["compounds_stage"]) == LABELS


def test_a_failure_of_the_stage_check_is_a_manifest_failure(tmp_path, monkeypatch) -> None:
    def fail(command):
        if "manifest" in command and option(command, "--run-dir").endswith("run_compounds"):
            return 9
        return None

    run, chain, out, code, args = run_chain(tmp_path, monkeypatch, fail=fail)
    assert code == 9
    provenance = provenance_of(out)
    assert provenance["failed_stage"] == "manifest"
    assert provenance["child_exit_code"] == 9
    assert provenance["failed_command"].endswith("--check-inputs")


@pytest.mark.parametrize(
    "command, stage",
    [
        (["py", "-m", "rnp.cli", "validate", "--config", "c.yaml"], "validate"),
        (["py", "-m", "rnp.cli", "ingest", "compounds", "--config", "c.yaml"], "ingest_compounds"),
        (["py", "-m", "rnp.cli", "ingest", "stp", "--config", "c.yaml"], "ingest"),
        (
            ["py", "-m", "rnp.cli", "ingest", "stp", "--config", "c.yaml", "--compounds", "d"],
            "ingest",
        ),
        (["py", "-m", "rnp.cli", "intersect", "--config", "c.yaml"], "intersect"),
        (["py", "-m", "rnp.cli", "manifest", "--run-dir", "run_compounds"], "manifest"),
        (["py", "scripts/build_case_background.py"], "backgrounds"),
        (["py", "scripts/case_check.py"], "independent_check"),
    ],
)
def test_stage_names(command, stage) -> None:
    assert load_run()._stage_name(command) == stage
