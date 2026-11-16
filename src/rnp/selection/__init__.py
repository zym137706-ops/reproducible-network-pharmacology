"""Selection decisions for the compound candidates of an 'rnp ingest compounds' stage.

The researcher writes one decision per candidate. This library reads that table, derives the full
candidate table with a selection status (no candidate is dropped), the issues, the selected list
and the summary, and checks that all of them agree with the compounds stage. A compound without a
decision is held for review, never selected. The library reads no registry, needs no RDKit and
writes nothing: a change of decisions only reruns the selection step.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..errors import InputError
from ..io.tables import clean_text, name_key, write_table
from ..structures.model import schema_problems
from ..structures.tables import read_rows

RULE_VERSION = "v0.2.0-selection-rules"
DECISION_VALUES = ("include", "exclude", "needs_review")
STATUS_VALUES = ("selected", "excluded", "needs_review", "quarantined")
ROW_ISSUE_CODES = (
    "no_decision_recorded",
    "include_blocked_by_quarantine",
    "quarantine_resolved_by_exclusion",
)
ISSUE_CODES = (*ROW_ISSUE_CODES, "decision_without_compound", "no_compound_selected")
INPUT_REQUIRED = ("compound", "decision", "reason_codes", "rules_version", "reviewer")
INPUT_OPTIONAL = ("group", "evidence_refs")
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
SUMMARY_COUNTS = (
    "candidates",
    "selected",
    "excluded",
    "needs_review",
    "quarantined",
    "decisions_recorded",
    "decisions_not_recorded",
    "decisions_without_compound",
    "warnings",
)

_ID_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class DecisionRow:
    """One row of the researcher's decision table, cleaned and numbered."""

    row: int
    compound: str
    group: str
    decision: str
    reason_codes: str
    rules_version: str
    reviewer: str
    evidence_refs: str

    @property
    def key(self) -> tuple[str, str]:
        """Return the matching key of this decision: name key and exact group."""
        return (name_key(self.compound), self.group)


@dataclass(frozen=True)
class Decisions:
    """The decision table as a whole."""

    path: Path | None
    rows: list[DecisionRow]
    extra_columns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SelectionIssue:
    """One problem of the selection stage, with a stable code."""

    code: str
    source: str
    row: int | None
    compound_id: str
    message: str
    level: str = "warning"

    def as_dict(self) -> dict[str, Any]:
        """Return the audit-record form of this issue."""
        return {
            "level": self.level,
            "code": self.code,
            "source": self.source,
            "row": self.row,
            "compound_id": self.compound_id,
            "message": self.message,
        }


@dataclass(frozen=True)
class Derivation:
    """The derived candidate table and the issues that belong to it."""

    rows: list[dict[str, str]]
    issues: list[SelectionIssue]


def canonical_codes(codes: str) -> str:
    """Return the reason codes sorted and without repeats, joined by semicolons."""
    return ";".join(sorted({part.strip() for part in codes.split(";") if part.strip()}))


def _cleaned_cells(record: dict[str, str]) -> dict[str, str]:
    return {
        "compound": clean_text(record.get("compound", "")),
        "group": clean_text(record.get("group", "")) or "all",
        "decision": record.get("decision", "").strip(),
        "reason_codes": record.get("reason_codes", "").strip(),
        "rules_version": clean_text(record.get("rules_version", "")),
        "reviewer": clean_text(record.get("reviewer", "")),
        "evidence_refs": clean_text(record.get("evidence_refs", "")),
    }


def _refuse_duplicates(filename: str, rows: list[DecisionRow]) -> None:
    grouped: dict[tuple[str, str], list[DecisionRow]] = {}
    for row in rows:
        grouped.setdefault(row.key, []).append(row)
    duplicates = [group for group in grouped.values() if len(group) > 1]
    if not duplicates:
        return
    duplicates.sort(key=lambda group: group[0].row)
    details = [
        f"{group[0].compound} (group {group[0].group}): rows "
        + ", ".join(str(row.row) for row in group)
        for group in duplicates
    ]
    raise InputError(
        f"{filename}: the selection table decides the same compound more than once",
        details=details,
    )


def read_decisions(path: str | Path) -> Decisions:
    """Read and clean the decision table, refusing anything the schema does not allow."""
    table_path = Path(path)
    header, records = read_rows(table_path)
    missing = [column for column in INPUT_REQUIRED if column not in header]
    if missing:
        raise InputError(
            f"{table_path.name}: the selection table lacks required column(s)",
            details=[", ".join(missing)],
        )
    if not records:
        raise InputError(f"{table_path.name}: the selection table has no decisions")
    extra_columns = [
        column
        for column in header
        if column not in INPUT_REQUIRED and column not in INPUT_OPTIONAL
    ]
    rows: list[DecisionRow] = []
    problems: list[str] = []
    for number, record in enumerate(records, start=1):
        cells = _cleaned_cells(record)
        rows.append(
            DecisionRow(
                row=number,
                compound=cells["compound"],
                group=cells["group"],
                decision=cells["decision"],
                reason_codes=canonical_codes(cells["reason_codes"]),
                rules_version=cells["rules_version"],
                reviewer=cells["reviewer"],
                evidence_refs=cells["evidence_refs"],
            )
        )
        problems.extend(
            f"row {number}: {problem}"
            for problem in schema_problems("selection_input_row", cells)
        )
    if problems:
        raise InputError(
            f"{table_path.name}: the selection table has invalid rows",
            details=problems,
        )
    _refuse_duplicates(table_path.name, rows)
    return Decisions(path=table_path, rows=rows, extra_columns=extra_columns)


def decision_id(
    *,
    compound_id: str,
    structure_id: str,
    decision: str,
    decision_source: str,
    reason_codes: str,
    rules_version: str,
    reviewer: str,
    evidence_refs: str,
) -> str:
    """Return the content id of one derived decision: the prefix DEC- and twelve hex digits."""
    values = (
        compound_id,
        structure_id,
        decision,
        decision_source,
        reason_codes,
        rules_version,
        reviewer,
        evidence_refs,
    )
    digest = hashlib.sha256(_ID_SEPARATOR.join(values).encode("utf-8")).hexdigest()
    return "DEC-" + digest[:12]


def status_for(row_status: str, decision: str | None) -> str:
    """Return the selection status of a candidate; None means no decision recorded."""
    if row_status == "quarantined":
        return "excluded" if decision == "exclude" else "quarantined"
    if decision == "include":
        return "selected"
    if decision == "exclude":
        return "excluded"
    return "needs_review"


def row_issue_codes(row_status: str, decision: str | None) -> list[str]:
    """Return the codes of the row-level issues of one candidate."""
    if decision is None:
        return ["no_decision_recorded"]
    if row_status == "quarantined":
        if decision == "include":
            return ["include_blocked_by_quarantine"]
        if decision == "exclude":
            return ["quarantine_resolved_by_exclusion"]
    return []


def _row_issue_message(code: str, name: str, group: str) -> str:
    if code == "include_blocked_by_quarantine":
        return (
            f"{name!r} (group {group!r}) is decided include, but the compounds stage "
            "quarantined it, so it is not selected"
        )
    if code == "quarantine_resolved_by_exclusion":
        return (
            f"{name!r} (group {group!r}) was quarantined by the compounds stage and "
            "is decided exclude: the exclusion stands"
        )
    return f"no decision is recorded for {name!r} (group {group!r}); it is held for review"


def _issue_key(issue: SelectionIssue) -> tuple[str, int, int, str, str, str]:
    return (
        issue.source,
        0 if issue.row is not None else 1,
        issue.row or 0,
        issue.code,
        issue.compound_id,
        issue.message,
    )


def derive_selection(
    stage_rows: Iterable[dict[str, str]], decisions: Decisions
) -> Derivation:
    """Derive the candidate table of the stage and the issues of the derivation."""
    by_key: dict[tuple[str, str], DecisionRow] = {}
    for decision in decisions.rows:
        if decision.key in by_key:
            raise ValueError("the decisions are not unique per compound")
        by_key[decision.key] = decision
    rows: list[dict[str, str]] = []
    issues: list[SelectionIssue] = []
    matched: set[tuple[str, str]] = set()
    for number, stage in enumerate(stage_rows, start=1):
        key = (name_key(stage["name"]), stage["group"])
        matched.add(key)
        recorded = by_key.get(key)
        if recorded is None:
            decision = "needs_review"
            decision_source = "not_recorded"
            reason_codes = ""
            rules_version = ""
            reviewer = ""
            evidence_refs = ""
            chosen = None
        else:
            decision = recorded.decision
            decision_source = "recorded"
            reason_codes = recorded.reason_codes
            rules_version = recorded.rules_version
            reviewer = recorded.reviewer
            evidence_refs = recorded.evidence_refs
            chosen = recorded.decision
        row_status = stage["row_status"]
        codes = row_issue_codes(row_status, chosen)
        row = {
            "decision_id": decision_id(
                compound_id=stage["compound_id"],
                structure_id=stage["structure_id"],
                decision=decision,
                decision_source=decision_source,
                reason_codes=reason_codes,
                rules_version=rules_version,
                reviewer=reviewer,
                evidence_refs=evidence_refs,
            ),
            "compound_id": stage["compound_id"],
            "group": stage["group"],
            "name": stage["name"],
            "stp_file": stage["stp_file"],
            "structure_id": stage["structure_id"],
            "compound_row_status": row_status,
            "decision": decision,
            "decision_source": decision_source,
            "selection_status": status_for(row_status, chosen),
            "reason_codes": reason_codes,
            "rules_version": rules_version,
            "reviewer": reviewer,
            "evidence_refs": evidence_refs,
            "issue_codes": ";".join(codes),
        }
        rows.append(row)
        for code in codes:
            issues.append(
                SelectionIssue(
                    code=code,
                    source="compounds",
                    row=number,
                    compound_id=stage["compound_id"],
                    message=_row_issue_message(code, stage["name"], stage["group"]),
                )
            )
    for row in decisions.rows:
        if row.key in matched:
            continue
        issues.append(
            SelectionIssue(
                code="decision_without_compound",
                source="selection",
                row=row.row,
                compound_id="",
                message=(
                    f"decision row {row.row} names {row.compound!r} (group {row.group!r}), "
                    "which is not a candidate of this run"
                ),
            )
        )
    if not any(row["selection_status"] == "selected" for row in rows):
        issues.append(
            SelectionIssue(
                code="no_compound_selected",
                source="selection",
                row=None,
                compound_id="",
                message="no compound is selected",
            )
        )
    return Derivation(rows=rows, issues=sorted(issues, key=_issue_key))


def selected_rows(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    """Return the selected candidates, in the order of the table."""
    return [row for row in rows if row["selection_status"] == "selected"]


def summarize(
    rows: Sequence[dict[str, str]], issues: Sequence[SelectionIssue]
) -> dict[str, Any]:
    """Count the table and the issues."""
    return {
        "candidates": len(rows),
        "selected": sum(1 for row in rows if row["selection_status"] == "selected"),
        "excluded": sum(1 for row in rows if row["selection_status"] == "excluded"),
        "needs_review": sum(1 for row in rows if row["selection_status"] == "needs_review"),
        "quarantined": sum(1 for row in rows if row["selection_status"] == "quarantined"),
        "decisions_recorded": sum(1 for row in rows if row["decision_source"] == "recorded"),
        "decisions_not_recorded": sum(
            1 for row in rows if row["decision_source"] == "not_recorded"
        ),
        "decisions_without_compound": sum(
            1 for issue in issues if issue.code == "decision_without_compound"
        ),
        "warnings": len(issues),
        "rules_versions": sorted(
            {row["rules_version"] for row in rows if row["decision_source"] == "recorded"}
        ),
    }


def check_selection(
    table: Sequence[dict[str, str]],
    selected: Sequence[dict[str, str]],
    stage_rows: Sequence[dict[str, str]],
    *,
    issues: Sequence[SelectionIssue],
    summary: dict[str, Any],
) -> list[str]:
    """Return the problems that make the derived artefacts disagree with the stage."""
    if len(table) != len(stage_rows):
        return [f"the table has {len(table)} rows for {len(stage_rows)} compounds of the stage"]
    problems: list[str] = []
    for number, (row, stage) in enumerate(zip(table, stage_rows, strict=True), start=1):
        where = f"row {number} ({stage['compound_id']})"
        for column in ("compound_id", "group", "name", "stp_file", "structure_id"):
            if row[column] != stage[column]:
                problems.append(
                    f"{where}: {column} is {row[column]!r}, "
                    f"the compounds stage has {stage[column]!r}"
                )
        if row["compound_row_status"] != stage["row_status"]:
            problems.append(
                f"{where}: compound_row_status is {row['compound_row_status']!r}, "
                f"the compounds stage has {stage['row_status']!r}"
            )
        chosen = row["decision"] if row["decision_source"] == "recorded" else None
        expected_status = status_for(stage["row_status"], chosen)
        if row["selection_status"] != expected_status:
            problems.append(
                f"{where}: selection_status is {row['selection_status']!r}, "
                f"expected {expected_status!r}"
            )
        expected_codes = ";".join(row_issue_codes(stage["row_status"], chosen))
        if row["issue_codes"] != expected_codes:
            problems.append(
                f"{where}: issue_codes is {row['issue_codes']!r}, expected {expected_codes!r}"
            )
        expected_id = decision_id(
            compound_id=row["compound_id"],
            structure_id=row["structure_id"],
            decision=row["decision"],
            decision_source=row["decision_source"],
            reason_codes=row["reason_codes"],
            rules_version=row["rules_version"],
            reviewer=row["reviewer"],
            evidence_refs=row["evidence_refs"],
        )
        if row["decision_id"] != expected_id:
            problems.append(
                f"{where}: decision_id is {row['decision_id']!r}, expected {expected_id!r}"
            )
    counts: dict[str, int] = {}
    for row in table:
        counts[row["decision_id"]] = counts.get(row["decision_id"], 0) + 1
    for value in sorted(value for value, count in counts.items() if count > 1):
        problems.append(f"decision_id {value} appears {counts[value]} times")
    if list(selected) != selected_rows(table):
        problems.append("the selected list is not the selected rows of the table, in order")
    compound_issues = sorted(
        (issue.row, issue.code, issue.compound_id)
        for issue in issues
        if issue.source == "compounds"
    )
    table_issues = sorted(
        (number, code, row["compound_id"])
        for number, row in enumerate(table, start=1)
        for code in row["issue_codes"].split(";")
        if code
    )
    if compound_issues != table_issues:
        problems.append(
            "the compound issues of the audit do not match the issue_codes of the table"
        )
    expected_summary = summarize(table, issues)
    for name in (*SUMMARY_COUNTS, "rules_versions"):
        if summary.get(name) != expected_summary[name]:
            problems.append(
                f"summary.{name} is {summary.get(name)!r}, "
                f"expected {expected_summary[name]!r}"
            )
    return problems


def write_selection_table(path: str | Path, rows: Iterable[dict[str, str]]) -> None:
    """Write the candidate table in the fixed column order (UTF-8, LF, no BOM)."""
    write_table(path, rows, SELECTION_COLUMNS)


__all__ = [
    "DECISION_VALUES",
    "INPUT_OPTIONAL",
    "INPUT_REQUIRED",
    "ISSUE_CODES",
    "ROW_ISSUE_CODES",
    "RULE_VERSION",
    "SELECTION_COLUMNS",
    "STATUS_VALUES",
    "SUMMARY_COUNTS",
    "DecisionRow",
    "Decisions",
    "Derivation",
    "SelectionIssue",
    "canonical_codes",
    "check_selection",
    "decision_id",
    "derive_selection",
    "read_decisions",
    "row_issue_codes",
    "selected_rows",
    "status_for",
    "summarize",
    "write_selection_table",
]
