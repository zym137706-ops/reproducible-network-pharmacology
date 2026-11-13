"""Builders for the case-entry tests: the quickstart inputs, structure-mode compound tables,
submission logs, fake compounds stages and a recording stand-in for the child commands.

Nothing in this module needs RDKit. The tests that run the real `rnp ingest compounds` ask for it
themselves through `require_chem`: without RDKit they are skipped, unless the environment variable
RNP_REQUIRE_CHEM is 1 (CI sets it), in which case a missing RDKit is a failure.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parents[2]
QUICKSTART = ROOT / "tests" / "fixtures" / "run" / "inputs"
LOG_COLUMNS = [
    "stp_file",
    "compound",
    "pubchem_cid",
    "submitted_structure",
    "species",
    "submitted_date",
    "result_sha256",
    "result_url",
    "job_id",
]
TABLE_COLUMNS = [
    "compound_id",
    "group",
    "name",
    "stp_file",
    "row_status",
    "structure_status",
    "structure_id",
    "smiles",
    "inchikey",
    "stereo_status",
    "submission_status",
    "export_kind",
    "export_sha256",
    "issue_codes",
]
ERROR_CODES = {
    "missing_structure",
    "invalid_smiles",
    "submission_structure_mismatch",
    "submission_hash_mismatch",
    "submission_species_mismatch",
    "submission_export_missing",
    "submission_name_mismatch",
    "submission_cid_mismatch",
}
# The source that the core gives a code (the compound table or the submission log).
LOG_SOURCED = {
    "submission_structure_mismatch",
    "submission_hash_mismatch",
    "submission_species_mismatch",
    "submission_export_missing",
    "submission_name_mismatch",
    "submission_cid_mismatch",
    "submission_hash_not_declared",
    "submission_export_reconstructed",
    "log_row_without_compound",
}
TOOLKIT = {"name": "rdkit", "version": "2026.09.1"}


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_run():
    return load_module("rnp_case_run", "scripts/case_run.py")


def require_chem() -> None:
    try:
        import rdkit  # noqa: F401
    except ImportError:
        if os.environ.get("RNP_REQUIRE_CHEM") == "1":
            pytest.fail("RDKit is required (RNP_REQUIRE_CHEM=1) but is not installed")
        pytest.skip("RDKit is not installed (optional extra 'chem')")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- tables --------------------
def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def write_tsv(
    path: Path,
    header: list[str],
    rows: list[dict[str, str]],
    *,
    bom: bool = False,
    newline: str = "\n",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, delimiter="\t", lineterminator=newline)
        writer.writeheader()
        writer.writerows(rows)


def rewrite(path: Path, edit) -> None:
    """Read a TSV, let `edit(header, rows)` change both in place (rows are dicts), write it back."""
    header, rows = read_tsv(path)
    edit(header, rows)
    write_tsv(path, header, rows)


# --- a case on disk --------------------
def case_args(tmp_path: Path, smiles=("CCO", "CCC"), *, log: bool = True, **overrides):
    """The arguments of case_run.py for the two quickstart compounds.

    The compound table gets the given SMILES strings; with `log` (default) a matching submission log
    is written too. Everything is under `tmp_path`; the quickstart files are copied, not edited.
    """
    stp_dir = tmp_path / "inputs" / "stp"
    stp_dir.mkdir(parents=True)
    for source in sorted((QUICKSTART / "stp").iterdir()):
        (stp_dir / source.name).write_bytes(source.read_bytes())
    header, rows = read_tsv(QUICKSTART / "compounds.tsv")
    assert len(rows) == len(smiles)
    for row, value in zip(rows, smiles, strict=True):
        row["smiles"] = value
    compounds = tmp_path / "inputs" / "compounds.tsv"
    write_tsv(compounds, header, rows)
    for name in ("disease_genes.txt", "universe.txt"):
        (tmp_path / "inputs" / name).write_bytes((QUICKSTART / name).read_bytes())
    values = {
        "compounds": compounds,
        "stp_dir": stp_dir,
        "disease_genes": tmp_path / "inputs" / "disease_genes.txt",
        "hgnc_map": ROOT / "tests" / "fixtures" / "hgnc" / "hgnc_map.tsv",
        "log": None,
        "config_template": ROOT / "examples" / "quickstart" / "run.yaml",
        "thresholds": ["0.10", "0.05"],
    }
    values.update(overrides)
    args = SimpleNamespace(**values)
    if log and args.log is None:
        args.log = tmp_path / "inputs" / "log.tsv"
        write_log(args)
    return args


def write_log(args, **extra_columns: list[str]) -> None:
    """Write args.log with one correct row per compound of args.compounds.

    `extra_columns` maps an additional column name to its values, one per row.
    """
    _, compounds = read_tsv(args.compounds)
    rows = []
    for index, compound in enumerate(compounds):
        row = {
            "stp_file": compound["stp_file"],
            "compound": compound["name"],
            "pubchem_cid": compound["pubchem_cid"],
            "submitted_structure": compound["smiles"],
            "species": "Homo sapiens",
            "submitted_date": "2026-10-21",
            "result_sha256": sha256_of(args.stp_dir / compound["stp_file"]),
            "result_url": "not_saved",
            "job_id": "not_saved",
        }
        for column, values in extra_columns.items():
            row[column] = values[index]
        rows.append(row)
    write_tsv(args.log, [*LOG_COLUMNS, *(c for c in extra_columns if c not in LOG_COLUMNS)], rows)


def argv_for(args, out: Path, *, preflight_only: bool = False) -> list[str]:
    argv = [
        "--compounds",
        str(args.compounds),
        "--stp-dir",
        str(args.stp_dir),
        "--disease-genes",
        str(args.disease_genes),
        "--hgnc-map",
        str(args.hgnc_map),
        "--config-template",
        str(args.config_template),
        "--out",
        str(out),
    ]
    if args.log is not None:
        argv += ["--log", str(args.log)]
    if preflight_only:
        argv.append("--preflight-only")
    return argv


# --- a compounds stage made by hand --------------------
def stage_row(number: int, status: str = "verified", **fields: str) -> dict[str, str]:
    """A row of compound_structures.tsv for `Compound <number>`, accepted unless fields say not."""
    row = {
        "compound_id": f"CMP{number:04d}",
        "group": "all",
        "name": f"Compound {number}",
        "stp_file": f"c{number}.csv",
        "row_status": "accepted",
        "structure_status": "registered",
        "structure_id": f"STR{number:04d}",
        "smiles": "CCO",
        "inchikey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        "stereo_status": "none_present",
        "submission_status": status,
        "export_kind": "native_export" if status == "verified" else "",
        "export_sha256": "0" * 64,
        "issue_codes": "",
    }
    row.update(fields)
    return row


def stage_issue(code: str, number: int = 1, message: str | None = None) -> dict[str, Any]:
    """An audit issue about `Compound <number>` (about no compound at all when number is 0)."""
    return {
        "level": "error" if code in ERROR_CODES else "warning",
        "code": code,
        "source": "submission_log" if code in LOG_SOURCED else "compounds",
        "row": number,
        "compound_id": f"CMP{number:04d}" if number else "",
        "message": message or f"the core says something about {code}",
    }


def write_stage(
    directory: Path,
    rows: list[dict[str, str]],
    issues: list[dict[str, Any]] | None = None,
    *,
    mode: str = "structure",
) -> Path:
    """Write the two files of a compounds stage that the case policy reads; return the directory.

    Only the keys the case entry may rely on are written (the real audit has many more).
    """
    directory.mkdir(parents=True, exist_ok=True)
    audit = {
        "identity_mode": mode,
        "stage_status": "partial"
        if any(r["row_status"] == "quarantined" for r in rows)
        else "complete",
        "toolkit": dict(TOOLKIT),
        "issues": list(issues or []),
    }
    (directory / "compounds_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    write_tsv(directory / "compound_structures.tsv", TABLE_COLUMNS, rows)
    return directory


# --- the child commands of the chain --------------------
class FakeChain:
    """Stands in for `run_command`: records every command and writes what a real stage would.

    `fail(command)` may return an exit code for a command that should fail.
    """

    def __init__(self, run, fail=None) -> None:
        self.run = run  # the loaded case_run module: the exception it catches must be its own class
        self.commands: list[list[str]] = []
        self.fail = fail

    def __call__(self, command, cwd, recorded=None) -> None:
        command = [str(part) for part in command]
        self.commands.append(command)
        if recorded is not None:
            recorded.append(" ".join(command))
        code = self.fail(command) if self.fail else None
        if code:
            raise self.run.CommandFailure(command, code)
        if "ingest" in command and "compounds" in command:
            config = yaml.safe_load(Path(command[command.index("--config") + 1]).read_text("utf-8"))
            stage = (
                Path(config["outputs"]["dir"])
                / f"{command[command.index('--run-id') + 1]}_compounds"
            )
            stage.mkdir(parents=True, exist_ok=True)
            (stage / "compounds_audit.json").write_bytes(b'{"audit": "fake"}\n')
            (stage / "compound_structures.tsv").write_bytes(b"compound_id\tname\nCMP0001\tx\n")

    def find(self, *words: str, config: str | None = None) -> list[int]:
        """Positions of the commands that contain every word as a separate argument."""
        found = []
        for position, command in enumerate(self.commands):
            if not all(word in command for word in words):
                continue
            if config is not None and not any(part.endswith(config) for part in command):
                continue
            found.append(position)
        return found


def one(positions: list[int]) -> int:
    assert len(positions) == 1, positions
    return positions[0]


def option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]
