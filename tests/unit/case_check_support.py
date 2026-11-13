"""A small case on disk for the independent binding recheck: inputs and one output per threshold.

The compounds stage is written by hand, with the values the real stage carries for these inputs, so
nothing here needs RDKit. `make_case` returns a consistent case; a test then changes one thing and
looks at what the recheck says. The `edit_*` helpers change a file and, unless told otherwise, keep
the hash that another file records of it up to date, so that only the change itself shows.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from case_run_support import TABLE_COLUMNS, load_module, rewrite, sha256_of, write_tsv

SMILES = ["CCO", "CCC", "CCN", "CCCl", "CCBr", "CCF"]
KIND_STATUS = {
    "native_export": "verified",
    "": "verified_kind_unstated",
    "reconstructed_from_result_page": "reconstructed",
}
LOG_HEADER = [
    "stp_file",
    "compound",
    "pubchem_cid",
    "submitted_structure",
    "species",
    "submitted_date",
    "result_sha256",
    "result_url",
    "job_id",
    "export_kind",
]
REGISTERED_HEADER = [
    "compound_id",
    "group",
    "name",
    "stp_file",
    "submission_id",
    "identity_basis",
    "structure_id",
    "structure_status",
]
DERIVED_COLUMNS = [
    "name",
    "group",
    "stp_file",
    "smiles",
    "submission_status",
    "export_kind",
    "export_sha256",
]


def load_check():
    return load_module("rnp_case_check", "scripts/case_check.py")


@dataclass
class Case:
    """The paths of a case on disk; `rows` is the number of compounds."""

    root: Path
    compounds: Path
    stp_dir: Path
    log: Path
    species: str
    stages: dict[str, Path]
    runs: dict[str, Path]
    rows: int

    def export(self, number: int) -> Path:
        return self.stp_dir / f"c{number}.csv"

    def stage_table(self, label: str) -> Path:
        return self.stages[label] / "compound_structures.tsv"

    def audit(self, label: str) -> Path:
        return self.stages[label] / "compounds_audit.json"

    def registered(self, label: str) -> Path:
        return self.runs[label] / "compounds_registered.tsv"

    def ingest_audit(self, label: str) -> Path:
        return self.runs[label] / "stp_audit.json"


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=1), encoding="utf-8")


def make_case(
    tmp_path: Path,
    *,
    rows: int = 3,
    labels: tuple[str, ...] = ("0.10",),
    kinds: list[str] | None = None,
    messy: bool = False,
    group: bool = False,
) -> Case:
    """Write a consistent case: `rows` compounds, their exports, the log and one output per label.

    `kinds` gives the export kind of every log row (default: none stated). With `messy` the compound
    table and the log carry what the core cleans away (no-break spaces, runs of spaces, spaces
    around cells); `group` adds a group column.
    """
    root = tmp_path / "case"
    stp_dir = root / "stp"
    stp_dir.mkdir(parents=True)
    kinds = list(kinds) if kinds is not None else [""] * rows
    assert len(kinds) == rows
    items = []
    for number in range(1, rows + 1):
        export = f"c{number}.csv"
        (stp_dir / export).write_bytes(f"target,score\nTP{number},0.9\n".encode())
        items.append(
            {
                "number": number,
                "name": f"Compound {number}",
                "group": "Grp A" if group else "all",
                "cid": str(1000 + number),
                "smiles": SMILES[number - 1],
                "stp_file": export,
                "kind": kinds[number - 1],
                "sha": sha256_of(stp_dir / export),
            }
        )

    header = ["name", "pubchem_cid", "smiles", "stp_file", *(["group"] if group else [])]
    table = []
    for item in items:
        row = {
            "name": item["name"],
            "pubchem_cid": item["cid"],
            "smiles": item["smiles"],
            "stp_file": item["stp_file"],
        }
        if group:
            row["group"] = item["group"]
        if messy:
            row["name"] = item["name"].replace(" ", "\u00a0")
            row["pubchem_cid"] = f" {item['cid']} "
            row["smiles"] = f" {item['smiles']} "
            row["stp_file"] = f"  {item['stp_file']} "
            if group:
                row["group"] = "  Grp  A "
        table.append(row)
    compounds = root / "compounds.tsv"
    write_tsv(compounds, header, table)

    log_rows = []
    for item in items:
        cells = {
            "stp_file": item["stp_file"],
            "compound": item["name"],
            "pubchem_cid": item["cid"],
            "submitted_structure": item["smiles"],
            "species": "Homo sapiens",
            "submitted_date": "2026-10-21",
            "result_sha256": item["sha"],
            "result_url": "not_saved",
            "job_id": "not_saved",
            "export_kind": item["kind"],
        }
        log_rows.append(
            {key: f" {value} " if messy and value else value for key, value in cells.items()}
        )
    log = root / "log.tsv"
    write_tsv(log, LOG_HEADER, log_rows)

    statuses = [KIND_STATUS[item["kind"]] for item in items]
    stages: dict[str, Path] = {}
    runs: dict[str, Path] = {}
    for label in labels:
        stage = root / "out" / label / "run_compounds"
        run = root / "out" / label / "run"
        stage.mkdir(parents=True)
        run.mkdir(parents=True)
        stage_rows = []
        for item, status in zip(items, statuses, strict=True):
            number = item["number"]
            stage_rows.append(
                {
                    "compound_id": f"CMP{number:04d}",
                    "group": item["group"],
                    "name": item["name"],
                    "stp_file": item["stp_file"],
                    "row_status": "accepted",
                    "structure_status": "registered",
                    "structure_id": f"STR{number:04d}",
                    "smiles": item["smiles"],
                    "inchikey": f"{'A' * 13}{chr(64 + number)}-UHFFFAOYSA-N",
                    "stereo_status": "none_present",
                    "submission_status": status,
                    "export_kind": item["kind"],
                    "export_sha256": item["sha"],
                    "issue_codes": "",
                }
            )
        write_tsv(stage / "compound_structures.tsv", TABLE_COLUMNS, stage_rows)
        counts = Counter(statuses)
        _write_json(
            stage / "compounds_audit.json",
            {
                "schema_version": "1.0",
                "generated_by": "rnp ingest compounds",
                "stage_status": "complete",
                "identity_mode": "structure",
                "toolkit": {"name": "rdkit", "version": "2026.09.1"},
                "inputs": {
                    "compounds": {
                        "path": str(compounds),
                        "sha256": sha256_of(compounds),
                        "rows": rows,
                    },
                    "submission_log": {"path": str(log), "sha256": sha256_of(log), "rows": rows},
                    "stp_dir": {"path": str(stp_dir), "files_hashed": rows},
                },
                "summary": {
                    "rows": rows,
                    "rows_accepted": rows,
                    "rows_quarantined": 0,
                    "rows_name_only": 0,
                    "structures_new": rows,
                    "structures_reused": 0,
                    "structures_superseded": 0,
                    "submissions_verified": counts["verified"] + counts["verified_kind_unstated"],
                    "submissions_reconstructed": counts["reconstructed"],
                    "submissions_not_recorded": 0,
                    "submissions_rejected": 0,
                    "errors": 0,
                    "warnings": 0,
                },
                "issues": [],
                "compound_structures_sha256": sha256_of(stage / "compound_structures.tsv"),
            },
        )
        registered_rows = [
            {
                "compound_id": row["compound_id"],
                "group": row["group"],
                "name": row["name"],
                "stp_file": row["stp_file"],
                "submission_id": f"STP-c{index}",
                "identity_basis": "registry_name",
                "structure_id": row["structure_id"],
                "structure_status": "registered",
            }
            for index, row in enumerate(stage_rows, start=1)
        ]
        write_tsv(run / "compounds_registered.tsv", REGISTERED_HEADER, registered_rows)
        _write_json(
            run / "stp_audit.json",
            {
                "stage_status": "complete",
                "compounds_registered_sha256": sha256_of(run / "compounds_registered.tsv"),
            },
        )
        stages[label] = stage
        runs[label] = run
    return Case(root, compounds, stp_dir, log, "Homo_sapiens", stages, runs, rows)


# --- changing things ------------------------------------------------------------------------
def seal_stage(case: Case, label: str) -> None:
    """Record the hash of the stage table in the stage audit again."""
    edit_audit(
        case,
        label,
        lambda audit: audit.__setitem__(
            "compound_structures_sha256", sha256_of(case.stage_table(label))
        ),
    )


def seal_registered(case: Case, label: str) -> None:
    """Record the hash of the registered table in the ingest audit again."""
    path = case.ingest_audit(label)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["compounds_registered_sha256"] = sha256_of(case.registered(label))
    _write_json(path, document)


def edit_stage(case: Case, label: str, edit, *, seal: bool = True) -> None:
    """Let `edit(rows)` change the rows (dicts) of the stage table of `label`."""
    rewrite(case.stage_table(label), lambda header, rows: edit(rows))
    if seal:
        seal_stage(case, label)


def edit_registered(case: Case, label: str, edit, *, seal: bool = True) -> None:
    """Let `edit(rows)` change the rows (dicts) of the registered table of `label`."""
    rewrite(case.registered(label), lambda header, rows: edit(rows))
    if seal:
        seal_registered(case, label)


def edit_audit(case: Case, label: str, edit) -> None:
    """Let `edit(audit)` change the stage audit of `label` (a dict)."""
    path = case.audit(label)
    document = json.loads(path.read_text(encoding="utf-8"))
    edit(document)
    _write_json(path, document)


def edit_log(case: Case, edit) -> None:
    """Let `edit(header, rows)` change the submission log (rows are dicts)."""
    rewrite(case.log, edit)


def edit_compounds(case: Case, edit) -> None:
    """Let `edit(header, rows)` change the compound table (rows are dicts)."""
    rewrite(case.compounds, edit)


def reseal_inputs(case: Case) -> None:
    """Record the hashes of the compound table and of the log in every stage audit again."""

    def update(audit: dict[str, Any]) -> None:
        audit["inputs"]["compounds"]["sha256"] = sha256_of(case.compounds)
        audit["inputs"]["submission_log"]["sha256"] = sha256_of(case.log)

    for label in case.stages:
        edit_audit(case, label, update)


# --- asking the recheck ---------------------------------------------------------------------
def recheck(case: Case):
    """Call check_bindings on the case; return its record."""
    return load_check().check_bindings(
        case.compounds, case.stp_dir, case.log, case.species, case.stages, case.runs
    )


def problems(case: Case) -> list[str]:
    """Call check_bindings, expect an AssertionError, and return the lines of its message."""
    with pytest.raises(AssertionError) as raised:
        recheck(case)
    return str(raised.value).splitlines()
