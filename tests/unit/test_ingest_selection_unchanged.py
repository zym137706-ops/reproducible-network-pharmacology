"""`rnp ingest stp --compounds DIR` without `--selection` is what it was before the option existed.

Two small scenarios (a clean one and a mixed one) run the compounds stage and then `ingest stp
--compounds`. Their three deterministic artifacts are compared with fingerprints taken from the code
before `--selection` was added: `compounds_registered.tsv` and `targets.tsv` byte for byte,
`stp_audit.json` after the machine-dependent fields (the paths with their separators, and the hash
of the run config that contains them) are normalised. The builders write LF on every platform, so
the hashes of the exports in the audit are the same everywhere. A selection stage that exists, and
the key `inputs.selection` in the run config, change nothing as long as the option is not given.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
from ingest_link_support import CLEAN, MIXED, build, compounds_stage, ingest
from selection_ingest_support import ALL_FOUR, EVERYTHING_DECIDED, make

from rnp.cli import main
from rnp.config import load_config, load_schema

REGISTERED_HEADER = (
    "compound_id\tgroup\tname\tstp_file\tsubmission_id\tidentity_basis\tstructure_id"
    "\tstructure_status"
)
# fingerprints taken from the code before `--selection` existed
GOLDEN = {
    "clean": {
        "registered": "3b2af9c88070736bbc882222aae44afab62615f81bd3d237ec61f9c5618c41e6",
        "targets": "32fab02ab959d25023588e933c17267841fe2e94778e148e549f0d40d1741399",
        "audit": "9f0a21f10cf779f274fb514be85216f100fe4c622c97f2c5258f178de75b874e",
    },
    "mixed": {
        "registered": "49e608566cb948eb78c1c9ed9bcbf10fa360bc0ac4ca1d24df04bbdc81c7f245",
        "targets": "1f0c7c95fae7415e5f9fff2372dbbefa0bfcf5b31097e0097d46b4729b677f13",
        "audit": "9305934f8d4e738d1008e5008f2385d4e19a8a2f563397f3c59331afe166efda",
    },
}
SCENARIOS = {"clean": CLEAN, "mixed": MIXED}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalised_audit(run_dir: Path, root: str) -> str:
    """The audit as JSON text without what depends on the machine: the paths, the config hash."""
    audit = json.loads((run_dir / "stp_audit.json").read_text(encoding="utf-8"))
    audit["config"]["sha256"] = "<config sha256>"
    text = json.dumps(audit, sort_keys=True, ensure_ascii=False)
    text = text.replace(root, "<root>").replace(root.replace("\\", "\\\\"), "<root>")
    # what is left of a path after the root is a relative path: write its separators as "/"
    return text.replace("\\\\", "/")


def fingerprints(run_dir: Path, root: str) -> dict[str, str]:
    return {
        "registered": sha256((run_dir / "compounds_registered.tsv").read_bytes()),
        "targets": sha256((run_dir / "targets.tsv").read_bytes()),
        "audit": sha256(normalised_audit(run_dir, root).encode("utf-8")),
    }


def run(tmp_path: Path, scenario) -> tuple[Path, str]:
    config = build(tmp_path, scenario)
    summary = ingest(config, compounds_stage(config))
    return Path(summary["run_dir"]), str(load_config(config).path.parent)


@pytest.mark.parametrize("name", ["clean", "mixed"])
def test_the_artifacts_are_the_ones_of_the_code_before_the_option_existed(tmp_path, name):
    run_dir, root = run(tmp_path, SCENARIOS[name])
    assert fingerprints(run_dir, root) == GOLDEN[name]


def test_the_two_scenarios_cover_a_complete_and_a_partial_stage(tmp_path):
    clean, _ = run(tmp_path / "c", CLEAN)
    mixed, _ = run(tmp_path / "m", MIXED)
    stages = [
        json.loads((path / "stp_audit.json").read_text(encoding="utf-8"))["stage_status"]
        for path in (clean, mixed)
    ]
    assert stages == ["complete", "partial"]


def test_a_selection_stage_that_exists_changes_nothing_without_the_option(tmp_path):
    case = make(tmp_path, EVERYTHING_DECIDED)
    summary = ingest(case.config, case.compounds)
    run_dir = Path(summary["run_dir"])
    assert fingerprints(run_dir, str(load_config(case.config).path.parent)) == GOLDEN["mixed"]


def test_without_the_option_nothing_of_the_selection_is_recorded(tmp_path):
    run_dir, _ = run(tmp_path, MIXED)
    header = (run_dir / "compounds_registered.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert header == REGISTERED_HEADER
    audit = json.loads((run_dir / "stp_audit.json").read_text(encoding="utf-8"))
    jsonschema.validate(audit, load_schema("stp_audit"))
    assert audit["schema_version"] == "1.1"
    assert "files_not_selected" not in audit["summary"]
    assert {entry["status"] for entry in audit["files"]} == {"ok", "quarantined"}
    assert [note["code"] for note in audit["notes"]][-1] == "compounds_stage_applied"
    assert "selection_stage_applied" not in {note["code"] for note in audit["notes"]}
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert sorted(manifest["args"]) == [
        "allow_filename_match",
        "compounds",
        "config",
        "stp_dir",
        "stp_probability",
    ]
    assert [parent["stage"] for parent in manifest["parents"]] == ["ingest compounds"]
    assert [Path(item["path"]).name for item in manifest["inputs"]] == [
        "run.yaml",
        "compounds.tsv",
        "c1.csv",
        "c2.csv",
        "c3.csv",
        "c4.csv",
        "compounds_audit.json",
        "compound_structures.tsv",
    ]


def test_the_command_without_the_option_prints_the_usual_summary(tmp_path, capsys):
    case = make(tmp_path, ALL_FOUR)
    code = main(
        [
            "ingest",
            "stp",
            "--config",
            str(case.config),
            "--run-id",
            "i1",
            "--compounds",
            str(case.compounds),
        ]
    )
    assert code == 3
    printed = json.loads(capsys.readouterr().out)
    assert "files_not_selected" not in printed["summary"]
    assert [item["path"] for item in printed["quarantine"]] == ["c2.csv", "c3.csv"]
