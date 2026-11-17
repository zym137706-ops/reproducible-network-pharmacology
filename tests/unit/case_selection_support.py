"""A small selection case on disk for the independent selection recheck, and a fake chain for it.

`make_selection_case` extends case_check_support.make_case: the decision table, one selection
stage per threshold (written by hand with the values the real stage carries), the extra column and
audit fields of the run, `targets.tsv` and the intersection audit. Nothing here needs RDKit. A test
changes one thing and looks at what the recheck says; the `edit_*` helpers keep the hashes that
other files record up to date unless told otherwise, so that only the change itself shows.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from case_check_support import Case, load_check, make_case
from case_run_support import ROOT, FakeChain, rewrite, sha256_of, write_tsv

DECISION_HEADER = [
    "compound",
    "group",
    "decision",
    "reason_codes",
    "rules_version",
    "reviewer",
    "evidence_refs",
]
SELECTION_COLUMNS = [
    "decision_id",
    "compound_id",
    "group",
    "name",
    "stp_file",
    "structure_id",
    "compound_row_status",
    "decision",
    "decision_source",
    "selection_status",
    "reason_codes",
    "rules_version",
    "reviewer",
    "evidence_refs",
    "issue_codes",
]
TARGET_COLUMNS = ["compound_id", "group", "submission_id", "source_file", "target"]
STATUS = {"include": "selected", "exclude": "excluded"}


def decision_id(row: dict[str, str]) -> str:
    """`DEC-` and 12 hex digits of the SHA-256 of eight fields joined by U+001F (upstream 8.11)."""
    fields = (
        "compound_id",
        "structure_id",
        "decision",
        "decision_source",
        "reason_codes",
        "rules_version",
        "reviewer",
        "evidence_refs",
    )
    text = "\x1f".join(row[field] for field in fields)
    return "DEC-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass
class SelectionCase:
    """A case of case_check_support plus the decision table and a selection stage per threshold."""

    case: Case
    decisions: Path
    selection_stages: dict[str, Path]

    def table(self, label: str) -> Path:
        return self.selection_stages[label] / "selection_decisions.tsv"

    def chosen(self, label: str) -> Path:
        return self.selection_stages[label] / "selected_compounds.tsv"

    def audit(self, label: str) -> Path:
        return self.selection_stages[label] / "selection_audit.json"

    def targets(self, label: str) -> Path:
        return self.case.runs[label] / "targets.tsv"

    def intersect(self, label: str) -> Path:
        return self.case.runs[label] / "intersect" / "intersect_audit.json"


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=1), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_decisions(rows: int, group: str = "all") -> list[dict[str, str]]:
    """Include every compound but the last, which is excluded for a reason."""
    table = []
    for number in range(1, rows + 1):
        last = number == rows
        table.append(
            {
                "compound": f"Compound {number}",
                "group": group,
                "decision": "exclude" if last else "include",
                "reason_codes": "out_of_scope;too_polar" if last else "",
                "rules_version": "RA-v1",
                "reviewer": "Researcher",
                "evidence_refs": "notes.pdf" if last else "",
            }
        )
    return table


def make_selection_case(
    tmp_path: Path,
    *,
    rows: int = 3,
    labels: tuple[str, ...] = ("0.10",),
    group: bool = False,
    decisions: list[dict[str, str]] | None = None,
) -> SelectionCase:
    """Write a consistent selection case: `rows` compounds, the last one excluded by default."""
    case = make_case(tmp_path, rows=rows, labels=labels, group=group)
    group_name = "Grp A" if group else "all"
    entries = decisions if decisions is not None else default_decisions(rows, group_name)
    path = case.root / "decisions.tsv"
    write_tsv(path, DECISION_HEADER, entries)
    by_name = {entry["compound"]: entry for entry in entries}
    stages: dict[str, Path] = {}
    for label in labels:
        stage_rows = []
        for number in range(1, rows + 1):
            entry = by_name[f"Compound {number}"]
            row = {
                "compound_id": f"CMP{number:04d}",
                "group": group_name,
                "name": f"Compound {number}",
                "stp_file": f"c{number}.csv",
                "structure_id": f"STR{number:04d}",
                "compound_row_status": "accepted",
                "decision": entry["decision"],
                "decision_source": "recorded",
                "selection_status": STATUS[entry["decision"]],
                "reason_codes": ";".join(sorted(entry["reason_codes"].split(";")))
                if entry["reason_codes"]
                else "",
                "rules_version": entry["rules_version"],
                "reviewer": entry["reviewer"],
                "evidence_refs": entry["evidence_refs"],
                "issue_codes": "",
            }
            row["decision_id"] = decision_id(row)
            stage_rows.append(row)
        chosen = [row for row in stage_rows if row["selection_status"] == "selected"]
        directory = case.root / "out" / label / "run_selection"
        directory.mkdir(parents=True)
        write_tsv(directory / "selection_decisions.tsv", SELECTION_COLUMNS, stage_rows)
        write_tsv(directory / "selected_compounds.tsv", SELECTION_COLUMNS, chosen)
        excluded = len(stage_rows) - len(chosen)
        _write_json(
            directory / "selection_audit.json",
            {
                "schema_version": "1.0",
                "generated_by": "rnp compounds select",
                "stage_status": "complete",
                "identity_mode": "structure",
                "inputs": {
                    "compounds_stage": {
                        "dir": str(case.stages[label]),
                        "audit_sha256": sha256_of(case.audit(label)),
                        "table_sha256": sha256_of(case.stage_table(label)),
                        "stage_status": "complete",
                    },
                    "selection": {"path": str(path), "sha256": sha256_of(path), "rows": rows},
                },
                "summary": {
                    "candidates": rows,
                    "selected": len(chosen),
                    "excluded": excluded,
                    "needs_review": 0,
                    "quarantined": 0,
                    "decisions_recorded": rows,
                    "decisions_not_recorded": 0,
                    "decisions_without_compound": 0,
                    "warnings": 0,
                    "rules_versions": ["RA-v1"],
                },
                "issues": [],
                "notes": [],
                "selection_decisions_sha256": sha256_of(directory / "selection_decisions.tsv"),
                "selected_compounds_sha256": sha256_of(directory / "selected_compounds.tsv"),
            },
        )
        stages[label] = directory

        run = case.runs[label]

        def add_status(header: list[str], table: list[dict[str, str]], rows=stage_rows) -> None:
            header.append("selection_status")
            for row, stage_row in zip(table, rows, strict=True):
                row["selection_status"] = stage_row["selection_status"]

        rewrite(case.registered(label), add_status)
        _write_json(
            case.ingest_audit(label),
            {
                "schema_version": "1.2",
                "stage_status": "complete",
                "summary": {"files_quarantined": 0, "files_not_selected": excluded},
                "notes": [
                    {"code": "compounds_stage_applied", "message": "the compounds stage"},
                    {"code": "selection_stage_applied", "message": "the selection stage"},
                ],
                "compounds_registered_sha256": sha256_of(case.registered(label)),
            },
        )
        write_tsv(
            run / "targets.tsv",
            TARGET_COLUMNS,
            [
                {
                    "compound_id": row["compound_id"],
                    "group": group_name,
                    "submission_id": f"STP-c{index}",
                    "source_file": row["stp_file"],
                    "target": f"TP{index}",
                }
                for index, row in enumerate(chosen, start=1)
            ],
        )
        (run / "intersect").mkdir()
        _write_json(
            run / "intersect" / "intersect_audit.json",
            {"groups": {group_name: {"compounds": len(chosen)}}},
        )
    return SelectionCase(case, path, stages)


# --- changing things ------------------------------------------------------------------------
def seal_table(sc: SelectionCase, label: str) -> None:
    edit_audit(
        sc, label, lambda a: a.__setitem__("selection_decisions_sha256", sha256_of(sc.table(label)))
    )


def seal_chosen(sc: SelectionCase, label: str) -> None:
    edit_audit(
        sc, label, lambda a: a.__setitem__("selected_compounds_sha256", sha256_of(sc.chosen(label)))
    )


def edit_table(sc: SelectionCase, label: str, edit, *, seal: bool = True) -> None:
    """Let `edit(rows)` change the rows (dicts) of selection_decisions.tsv of `label`."""
    rewrite(sc.table(label), lambda header, rows: edit(rows))
    if seal:
        seal_table(sc, label)


def edit_chosen(sc: SelectionCase, label: str, edit, *, seal: bool = True) -> None:
    """Let `edit(rows)` change the rows (dicts) of selected_compounds.tsv of `label`."""
    rewrite(sc.chosen(label), lambda header, rows: edit(rows))
    if seal:
        seal_chosen(sc, label)


def edit_audit(sc: SelectionCase, label: str, edit) -> None:
    """Let `edit(audit)` change the selection audit of `label` (a dict)."""
    document = _read_json(sc.audit(label))
    edit(document)
    _write_json(sc.audit(label), document)


def edit_decisions(sc: SelectionCase, edit, *, seal: bool = True) -> None:
    """Let `edit(header, rows)` change the decision table; record its hash in every audit."""
    rewrite(sc.decisions, edit)
    if seal:
        for label in sc.selection_stages:
            edit_audit(
                sc,
                label,
                lambda a: a["inputs"]["selection"].__setitem__("sha256", sha256_of(sc.decisions)),
            )


def edit_ingest(sc: SelectionCase, label: str, edit) -> None:
    """Let `edit(audit)` change the ingest audit of `label` and keep the registered hash in it."""
    document = _read_json(sc.case.ingest_audit(label))
    edit(document)
    _write_json(sc.case.ingest_audit(label), document)


def edit_registered(sc: SelectionCase, label: str, edit) -> None:
    """Let `edit(header, rows)` change the registered table; record its hash in the ingest audit."""
    rewrite(sc.case.registered(label), edit)
    document = _read_json(sc.case.ingest_audit(label))
    document["compounds_registered_sha256"] = sha256_of(sc.case.registered(label))
    _write_json(sc.case.ingest_audit(label), document)


def edit_targets(sc: SelectionCase, label: str, edit) -> None:
    rewrite(sc.targets(label), lambda header, rows: edit(rows))


def edit_intersect(sc: SelectionCase, label: str, edit) -> None:
    document = _read_json(sc.intersect(label))
    edit(document)
    _write_json(sc.intersect(label), document)


# --- asking the recheck ---------------------------------------------------------------------
def selection_recheck(sc: SelectionCase):
    """Call check_selection on the case; return its record."""
    case = sc.case
    return load_check().check_selection(
        case.compounds, sc.decisions, case.stages, sc.selection_stages, case.runs
    )


def selection_problems(sc: SelectionCase) -> list[str]:
    """Call check_selection, expect an AssertionError, and return the lines of its message."""
    with pytest.raises(AssertionError) as raised:
        selection_recheck(sc)
    return str(raised.value).splitlines()


# --- the case entry --------------------------------------------------------------------------
class SelectionChain(FakeChain):
    """FakeChain that also writes a selection stage for every `compounds select` command."""

    def __call__(self, command, cwd, recorded=None) -> None:
        super().__call__(command, cwd, recorded)
        command = [str(part) for part in command]
        if "compounds" in command and "select" in command and "ingest" not in command:
            import yaml

            config = yaml.safe_load(Path(command[command.index("--config") + 1]).read_text("utf-8"))
            stage = (
                Path(config["outputs"]["dir"])
                / f"{command[command.index('--run-id') + 1]}_selection"
            )
            stage.mkdir(parents=True, exist_ok=True)
            (stage / "selection_audit.json").write_bytes(b'{"audit": "fake selection"}\n')
            (stage / "selection_decisions.tsv").write_bytes(b"compound_id\tname\nCMP0001\tx\n")
            (stage / "selected_compounds.tsv").write_bytes(b"compound_id\tname\nCMP0001\tx\n")


# --- the command line of case_check.py -------------------------------------------------------
def check_cli(sc: SelectionCase, tmp_path: Path, *, selection: bool = True) -> list[str]:
    """The arguments of case_check.py for the case (the binding recheck, and the selection)."""
    case = sc.case
    genes = tmp_path / "disease_genes.txt"
    genes.write_text("CA2\n", encoding="utf-8")
    argv: list[str] = []
    for label, run in case.runs.items():
        argv += ["--run", f"{label}={run}"]
    argv += [
        "--background-dir",
        str(tmp_path / "backgrounds"),
        "--disease-genes",
        str(genes),
        "--hgnc-map",
        str(ROOT / "tests" / "fixtures" / "hgnc" / "hgnc_map.tsv"),
        "--out",
        str(tmp_path / "independent-check.json"),
        "--compound-table",
        str(case.compounds),
        "--stp-dir",
        str(case.stp_dir),
        "--log",
        str(case.log),
        "--species",
        case.species,
    ]
    for label, stage in case.stages.items():
        argv += ["--stage", f"{label}={stage}"]
    if selection:
        argv += ["--selection", str(sc.decisions)]
        for label, stage in sc.selection_stages.items():
            argv += ["--selection-stage", f"{label}={stage}"]
    return argv


# --- the decision table and the selection stage of the case entry ----------------------------
def write_decision_table(path: Path, rows: list[dict[str, str]] | None = None) -> Path:
    """Write a decision table for the two quickstart compounds (the second one excluded)."""
    entries = rows
    if entries is None:
        entries = [
            {
                "compound": "Quercetin",
                "group": "all",
                "decision": "include",
                "reason_codes": "",
                "rules_version": "RA-v1",
                "reviewer": "Researcher",
                "evidence_refs": "",
            },
            {
                "compound": "Kaempferol",
                "group": "all",
                "decision": "exclude",
                "reason_codes": "out_of_scope",
                "rules_version": "RA-v1",
                "reviewer": "Researcher",
                "evidence_refs": "",
            },
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_tsv(path, DECISION_HEADER, entries)
    return path


def selection_row(number: int, status: str = "selected", **fields: str) -> dict[str, str]:
    """A row of selection_decisions.tsv for `Compound <number>`."""
    row = {column: "" for column in SELECTION_COLUMNS}
    row.update(
        compound_id=f"CMP{number:04d}",
        group="all",
        name=f"Compound {number}",
        stp_file=f"c{number}.csv",
        structure_id=f"STR{number:04d}",
        compound_row_status="accepted",
        selection_status=status,
    )
    row.update(fields)
    return row


def selection_issue(code: str, number: int = 1, message: str | None = None) -> dict[str, Any]:
    """An issue of the selection audit about `Compound <number>` (about no compound if 0)."""
    return {
        "level": "warning",
        "code": code,
        "source": "selection" if code == "decision_without_compound" else "compounds",
        "row": number,
        "compound_id": f"CMP{number:04d}" if number else "",
        "message": message or f"the core says something about {code}",
    }


def write_selection_stage(
    directory: Path,
    rows: list[dict[str, str]],
    issues: list[dict[str, Any]] | None = None,
    *,
    decisions: int = 2,
) -> Path:
    """Write the two files of a selection stage that the case policy reads; return the directory."""
    directory.mkdir(parents=True, exist_ok=True)
    audit = {"inputs": {"selection": {"rows": decisions}}, "issues": list(issues or [])}
    (directory / "selection_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    write_tsv(directory / "selection_decisions.tsv", SELECTION_COLUMNS, rows)
    return directory
