"""`case_run.py --selection FILE`: the option, the configs, the policy, the chain, the provenance.

The selection is applied to the compounds stage of the structure-mode chain, so `--selection` needs
`--log`. Before anything is written the preflight runs `rnp compounds select` on a copy and holds
the decision table to the case policy: every candidate is decided (include or exclude), every
decision belongs to a compound, and one compound is included. The chain then runs
`compounds select` after every `ingest compounds`, gives `ingest stp` both stage directories and
`case_check.py` the decision table and the selection stages. The child commands are replaced by a
recording stand-in (case_selection_support.SelectionChain); the real commands run only in the
preflight tests at the end, which need RDKit (skipped without it unless RNP_REQUIRE_CHEM is 1).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from case_run_support import argv_for, case_args, load_run, one, option, require_chem, sha256_of
from case_selection_support import (
    SelectionChain,
    selection_issue,
    selection_row,
    write_decision_table,
    write_selection_stage,
)

LABELS = ["0.05", "0.10"]
STRUCTURES = {
    "mode": "structure",
    "toolkit": {"name": "rdkit", "version": "2026.09.1"},
    "rows": 2,
    "submission_status_counts": {"verified": 2},
    "issue_code_counts": {},
}
SELECTION = {
    "provided": True,
    "path": "decisions.tsv",
    "sha256": "a" * 64,
    "rows": 2,
    "selected": 1,
    "excluded": 1,
    "verified_by": "rnp compounds select",
    "policy": "case-selection-policy-v1",
}


def judged(tmp_path, rows, issues=None, *, code=0, stderr="", decisions=2):
    """Run judge_selection on a hand-written selection stage; return the record and the table."""
    run = load_run()
    table = write_decision_table(tmp_path / "decisions.tsv")
    stage = write_selection_stage(tmp_path / "run_selection", rows, issues, decisions=decisions)
    return run.judge_selection(SimpleNamespace(selection=table), code, stderr, stage), table


def refused(tmp_path, rows, issues=None, **kwargs) -> list[str]:
    with pytest.raises(ValueError) as caught:
        judged(tmp_path, rows, issues, **kwargs)
    return str(caught.value).splitlines()


# --- the option -------------------------------------------------------------------------------
def test_the_names_the_chain_and_the_tests_rely_on() -> None:
    run = load_run()
    assert run.SELECTION_POLICY_VERSION == "case-selection-policy-v1"
    assert run.SELECTION_RECHECK_RULE == "case-selection-recheck-v1"
    assert run.SELECTION_DIR_NAME == "run_selection"
    assert run._stage_name(["python", "-m", "rnp.cli", "compounds", "select"]) == "compounds_select"


def test_a_selection_without_a_log_is_refused(tmp_path) -> None:
    run = load_run()
    table = write_decision_table(tmp_path / "decisions.tsv")
    args = case_args(tmp_path / "case", log=False, selection=table)
    with pytest.raises(ValueError) as caught:
        run.verify_inputs(args)
    assert str(caught.value) == (
        "--selection needs --log: the selection is applied to the compounds stage "
        "of the structure-mode chain"
    )


def test_a_selection_file_that_does_not_exist_is_refused(tmp_path) -> None:
    run = load_run()
    args = case_args(tmp_path / "case", selection=tmp_path / "nowhere.tsv")
    with pytest.raises(ValueError) as caught:
        run.verify_inputs(args)
    assert str(caught.value) == f"selection table not found: {tmp_path / 'nowhere.tsv'}"


def test_the_command_line_has_the_option_and_refuses_it_without_a_log(tmp_path) -> None:
    run = load_run()
    table = write_decision_table(tmp_path / "decisions.tsv")
    args = case_args(tmp_path / "case", log=False)
    argv = argv_for(args, tmp_path / "out") + ["--selection", str(table)]
    with pytest.raises(ValueError, match="--selection needs --log"):
        run.main(argv)
    assert not (tmp_path / "out").exists()


def test_the_inputs_record_holds_the_selection_after_the_structures(tmp_path, monkeypatch) -> None:
    run = load_run()
    calls: list[str] = []
    monkeypatch.setattr(run, "structure_preflight", lambda a: calls.append("s") or dict(STRUCTURES))
    monkeypatch.setattr(run, "selection_preflight", lambda a: calls.append("c") or dict(SELECTION))
    table = write_decision_table(tmp_path / "decisions.tsv")
    record = run.verify_inputs(case_args(tmp_path / "case", selection=table))
    assert calls == ["s", "c"]
    assert record["structures"] == STRUCTURES and record["selection"] == SELECTION


def test_without_a_selection_nothing_of_it_is_done(tmp_path, monkeypatch) -> None:
    run = load_run()
    monkeypatch.setattr(run, "structure_preflight", lambda a: dict(STRUCTURES))
    monkeypatch.setattr(run, "selection_preflight", lambda a: pytest.fail("no selection given"))
    record = run.verify_inputs(case_args(tmp_path / "case"))
    assert "selection" not in record


# --- the configs ------------------------------------------------------------------------------
def test_the_configs_name_the_decision_table_after_the_log(tmp_path) -> None:
    run = load_run()
    table = write_decision_table(tmp_path / "decisions.tsv")
    args = case_args(tmp_path / "case", selection=table)
    configs = run.write_configs(args, tmp_path / "out")
    for label in ("0.10", "0.05"):
        data = yaml.safe_load(configs[label].read_text(encoding="utf-8"))
        assert data["inputs"]["selection"] == str(table.resolve())
        assert list(data["inputs"])[-2:] == ["submission_log", "selection"]


def test_without_a_selection_the_configs_are_as_before(tmp_path) -> None:
    run = load_run()
    configs = run.write_configs(case_args(tmp_path / "case"), tmp_path / "out")
    data = yaml.safe_load(configs["0.10"].read_text(encoding="utf-8"))
    assert "selection" not in data["inputs"] and list(data["inputs"])[-1] == "submission_log"


# --- the case policy --------------------------------------------------------------------------
def test_a_clean_selection_stage_is_accepted_and_recorded(tmp_path) -> None:
    record, table = judged(tmp_path, [selection_row(1), selection_row(2, "excluded")])
    assert record == {
        "provided": True,
        "path": str(table.resolve()),
        "sha256": sha256_of(table),
        "rows": 2,
        "selected": 1,
        "excluded": 1,
        "verified_by": "rnp compounds select",
        "policy": "case-selection-policy-v1",
    }


@pytest.mark.parametrize(
    "code",
    [
        "no_decision_recorded",
        "include_blocked_by_quarantine",
        "quarantine_resolved_by_exclusion",
        "decision_without_compound",
        "no_compound_selected",
    ],
)
def test_every_issue_of_the_selection_stage_stops_the_run(tmp_path, code) -> None:
    number = 0 if code in ("decision_without_compound", "no_compound_selected") else 2
    rows = [selection_row(1), selection_row(2, "excluded")]
    lines = refused(tmp_path, rows, [selection_issue(code, number, "the core says so")])
    entry = "entry 'Compound 2' " if number else ""
    assert lines == [f"{tmp_path / 'decisions.tsv'}: {entry}decision: the core says so [{code}]"]


def test_a_decision_that_holds_a_compound_for_review_stops_the_run(tmp_path) -> None:
    rows = [selection_row(1), selection_row(2, "needs_review")]
    assert refused(tmp_path, rows) == [
        f"{tmp_path / 'decisions.tsv'}: entry 'Compound 2' decision: needs_review, "
        "not a decided candidate"
    ]


def test_a_compound_with_an_issue_is_named_once(tmp_path) -> None:
    rows = [selection_row(1), selection_row(2, "needs_review")]
    lines = refused(tmp_path, rows, [selection_issue("no_decision_recorded", 2, "no decision")])
    assert len(lines) == 1 and lines[0].endswith("[no_decision_recorded]")


def test_a_selection_that_selects_nobody_stops_the_run(tmp_path) -> None:
    rows = [selection_row(1, "excluded"), selection_row(2, "excluded")]
    assert refused(tmp_path, rows) == [f"{tmp_path / 'decisions.tsv'}: no compound is selected"]


def test_an_issue_the_policy_does_not_know_is_not_guessed_about(tmp_path) -> None:
    with pytest.raises(ValueError) as caught:
        judged(tmp_path, [selection_row(1)], [selection_issue("something_new")])
    assert str(caught.value) == (
        "rnp compounds select reported 'something_new', which the case policy does not classify"
    )


def test_exit_code_2_and_other_failures_of_the_command_are_reported(tmp_path) -> None:
    rows = [selection_row(1)]
    with pytest.raises(ValueError) as caught:
        judged(tmp_path / "a", rows, code=2, stderr="  the table is bad\n")
    assert str(caught.value) == (
        "rnp compounds select rejected the inputs (exit 2): the table is bad"
    )
    with pytest.raises(ValueError) as caught:
        judged(tmp_path / "b", rows, code=1, stderr="boom")
    assert str(caught.value) == "rnp compounds select failed (exit 1): boom"


def test_a_command_that_wrote_no_stage_is_reported(tmp_path) -> None:
    run = load_run()
    table = write_decision_table(tmp_path / "decisions.tsv")
    with pytest.raises(ValueError) as caught:
        run.judge_selection(SimpleNamespace(selection=table), 0, "", tmp_path / "nowhere")
    assert str(caught.value) == (
        f"rnp compounds select wrote no selection stage in {tmp_path / 'nowhere'}"
    )


# --- the chain --------------------------------------------------------------------------------
def run_chain(tmp_path: Path, monkeypatch, *, selection: bool = True, fail=None):
    """Run main() with the stand-ins; return (module, chain, out, exit code, decision table)."""
    run = load_run()
    chain = SelectionChain(run, fail)
    monkeypatch.setattr(run, "run_command", chain)
    monkeypatch.setattr(run, "structure_preflight", lambda args: dict(STRUCTURES))
    monkeypatch.setattr(run, "selection_preflight", lambda args: dict(SELECTION))
    args = case_args(tmp_path / "case")
    table = write_decision_table(tmp_path / "case" / "inputs" / "decisions.tsv")
    out = tmp_path / "out"
    argv = argv_for(args, out) + (["--selection", str(table)] if selection else [])
    try:
        code = run.main(argv)
    except SystemExit as exc:
        code = exc.code
    return run, chain, out, code, table


def provenance_of(out: Path) -> dict:
    return json.loads((out / "case_provenance.json").read_text(encoding="utf-8"))


def is_select(command: list[str]) -> bool:
    return "compounds" in command and "select" in command and "ingest" not in command


def is_case_check(command: list[str]) -> bool:
    return any(part.endswith("case_check.py") for part in command)


def test_each_threshold_selects_after_its_compounds_stage_and_before_its_ingest(
    tmp_path, monkeypatch
) -> None:
    run, chain, out, code, table = run_chain(tmp_path, monkeypatch)
    assert code == 0
    selects = [p for p, command in enumerate(chain.commands) if is_select(command)]
    assert len(selects) == 2
    for label in LABELS:
        config = str(out / "configs" / f"run-{label}.yaml")
        compounds = one(chain.find("ingest", "compounds", config=f"run-{label}.yaml"))
        select = one([p for p in selects if option(chain.commands[p], "--config") == config])
        stp = one(chain.find("ingest", "stp", config=f"run-{label}.yaml"))
        assert compounds < select < stp
        command = chain.commands[select]
        assert command[1:3] == ["-m", "rnp.cli"] and command[3:5] == ["compounds", "select"]
        assert option(command, "--compounds") == str(out / label / "run_compounds")
        assert option(command, "--run-id") == "run"


def test_ingest_stp_reads_both_stages_of_its_own_threshold(tmp_path, monkeypatch) -> None:
    run, chain, out, _, _ = run_chain(tmp_path, monkeypatch)
    for label in LABELS:
        command = chain.commands[one(chain.find("ingest", "stp", config=f"run-{label}.yaml"))]
        assert option(command, "--compounds") == str(out / label / "run_compounds")
        assert option(command, "--selection") == str(out / label / "run_selection")


def test_the_selection_stages_are_checked_after_the_other_manifests(tmp_path, monkeypatch) -> None:
    run, chain, out, _, _ = run_chain(tmp_path, monkeypatch)
    checks = chain.find("manifest", "--check-inputs")
    assert len(checks) == 6
    for label in LABELS:
        positions = {
            Path(option(chain.commands[p], "--run-dir")).name: p
            for p in checks
            if Path(option(chain.commands[p], "--run-dir")).parent == out / label
        }
        assert sorted(positions) == ["run", "run_compounds", "run_selection"]
        assert positions["run"] < positions["run_compounds"] < positions["run_selection"]
    case_check = [p for p, command in enumerate(chain.commands) if is_case_check(command)]
    assert len(case_check) == 1 and max(checks) < case_check[0]


def test_the_independent_check_gets_the_decision_table_and_the_stages(
    tmp_path, monkeypatch
) -> None:
    run, chain, out, _, table = run_chain(tmp_path, monkeypatch)
    command = next(c for c in chain.commands if is_case_check(c))
    assert option(command, "--selection") == str(table.resolve())
    given = [command[i + 1] for i, part in enumerate(command) if part == "--selection-stage"]
    assert sorted(given) == sorted(f"{label}={out / label / 'run_selection'}" for label in LABELS)


def test_the_configs_of_the_chain_name_the_decision_table(tmp_path, monkeypatch) -> None:
    run, chain, out, _, table = run_chain(tmp_path, monkeypatch)
    for label in LABELS:
        data = yaml.safe_load((out / "configs" / f"run-{label}.yaml").read_text(encoding="utf-8"))
        assert data["inputs"]["selection"] == str(table.resolve())


def test_the_provenance_records_the_selection_the_stages_and_the_recheck(
    tmp_path, monkeypatch
) -> None:
    run, chain, out, _, _ = run_chain(tmp_path, monkeypatch)
    provenance = provenance_of(out)
    assert provenance["status"] == "complete"
    assert provenance["commands"] == [" ".join(command) for command in chain.commands]
    selection = provenance["inputs"]["selection"]
    assert {key: selection[key] for key in SELECTION} == SELECTION
    assert selection["recheck"] == {
        "tool": "scripts/case_check.py",
        "rule": "case-selection-recheck-v1",
        "result": "passed",
    }
    for label in LABELS:
        stage = out / label / "run_selection"
        assert provenance["inputs"]["selection_stage"][label] == {
            "dir": str(stage),
            "audit_sha256": sha256_of(stage / "selection_audit.json"),
            "table_sha256": sha256_of(stage / "selection_decisions.tsv"),
            "list_sha256": sha256_of(stage / "selected_compounds.tsv"),
        }
    assert provenance["inputs"]["log"]["binding_recheck"]["result"] == "passed"


def test_without_a_selection_the_chain_is_as_before(tmp_path, monkeypatch) -> None:
    run, chain, out, code, _ = run_chain(tmp_path, monkeypatch, selection=False)
    assert code == 0
    assert not [c for c in chain.commands if is_select(c) or "--selection" in c]
    assert len(chain.find("manifest", "--check-inputs")) == 4
    inputs = provenance_of(out)["inputs"]
    assert "selection" not in inputs and "selection_stage" not in inputs


def test_a_failing_selection_stage_is_named_in_the_provenance(tmp_path, monkeypatch) -> None:
    def fail(command):
        return 2 if is_select(command) else None

    run, chain, out, code, _ = run_chain(tmp_path, monkeypatch, fail=fail)
    assert code == 2
    provenance = provenance_of(out)
    assert provenance["status"] == "failed"
    assert provenance["failed_stage"] == "compounds_select"
    assert provenance["child_exit_code"] == 2
    assert not chain.find("ingest", "stp")


# --- the real commands in the preflight --------------------------------------------------------
def entry_rows(*decisions: tuple[str, str]) -> list[dict[str, str]]:
    return [
        {
            "compound": name,
            "group": "all",
            "decision": decision,
            "reason_codes": "" if decision == "include" else "out_of_scope",
            "rules_version": "RA-v1",
            "reviewer": "Researcher",
            "evidence_refs": "",
        }
        for name, decision in decisions
    ]


def preflight(tmp_path, rows=None):
    run = load_run()
    case = tmp_path / "case"
    args = case_args(case)
    table = write_decision_table(case / "inputs" / "decisions.tsv", rows)
    out = tmp_path / "out"
    argv = argv_for(args, out, preflight_only=True) + ["--selection", str(table)]
    return run.main(argv), out, table


def test_the_real_preflight_accepts_and_records_a_decided_selection(tmp_path, capsys) -> None:
    require_chem()
    code, out, table = preflight(tmp_path)
    assert code == 0
    capsys.readouterr()
    provenance = provenance_of(out)
    assert provenance["status"] == "preflight_only"
    assert provenance["inputs"]["selection"] == {
        "provided": True,
        "path": str(table.resolve()),
        "sha256": sha256_of(table),
        "rows": 2,
        "selected": 1,
        "excluded": 1,
        "verified_by": "rnp compounds select",
        "policy": "case-selection-policy-v1",
    }
    config = yaml.safe_load((out / "configs" / "run-0.10.yaml").read_text(encoding="utf-8"))
    assert config["inputs"]["selection"] == str(table.resolve())


def test_the_real_preflight_refuses_a_compound_without_a_decision(tmp_path) -> None:
    require_chem()
    with pytest.raises(ValueError) as caught:
        preflight(tmp_path, entry_rows(("Quercetin", "include")))
    lines = str(caught.value).splitlines()
    assert len(lines) == 1
    assert lines[0].endswith(
        "entry 'Kaempferol' decision: no decision is recorded for 'Kaempferol' (group 'all'); "
        "it is held for review [no_decision_recorded]"
    )
    assert not (tmp_path / "out").exists()


def test_the_real_preflight_refuses_a_decision_for_no_compound(tmp_path) -> None:
    require_chem()
    rows = entry_rows(("Quercetin", "include"), ("Kaempferol", "exclude"), ("Rutin", "include"))
    with pytest.raises(ValueError) as caught:
        preflight(tmp_path, rows)
    assert "[decision_without_compound]" in str(caught.value)
    assert "'Rutin'" in str(caught.value)


def test_the_real_preflight_refuses_a_compound_held_for_review(tmp_path) -> None:
    require_chem()
    rows = entry_rows(("Quercetin", "include"), ("Kaempferol", "needs_review"))
    with pytest.raises(ValueError) as caught:
        preflight(tmp_path, rows)
    assert str(caught.value).endswith(
        "entry 'Kaempferol' decision: needs_review, not a decided candidate"
    )


def test_the_real_preflight_refuses_a_selection_of_nobody(tmp_path) -> None:
    require_chem()
    rows = entry_rows(("Quercetin", "exclude"), ("Kaempferol", "exclude"))
    with pytest.raises(ValueError) as caught:
        preflight(tmp_path, rows)
    assert "[no_compound_selected]" in str(caught.value)
