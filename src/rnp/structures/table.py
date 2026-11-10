"""Build and write ``compound_structures.tsv`` and its audit counts."""

from __future__ import annotations

from pathlib import Path

from ..errors import SchemaViolation
from ..io.tables import write_table
from ..output import write_table_atomic
from .model import CompoundRow, Issue, schema_problems, sorted_issues
from .registry import RegistrationResult
from .submissions import BindingResult

STRUCTURES_COLUMNS = [
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
SUMMARY_FIELDS = [
    "rows",
    "rows_accepted",
    "rows_quarantined",
    "rows_name_only",
    "structures_new",
    "structures_reused",
    "structures_superseded",
    "submissions_verified",
    "submissions_reconstructed",
    "submissions_not_recorded",
    "submissions_rejected",
    "errors",
    "warnings",
]


def _check_row(row: dict[str, str]) -> None:
    problems = schema_problems("compound_structures_row", row)
    if problems:
        raise SchemaViolation(
            f"the table row for {row['compound_id']} does not fit its schema",
            details=problems,
        )


def build_name_only_rows(rows: list[CompoundRow]) -> list[dict[str, str]]:
    """Build one name-only table row per input compound."""
    table: list[dict[str, str]] = []
    for compound in rows:
        row = {
            "compound_id": compound.compound_id,
            "group": compound.group,
            "name": compound.name,
            "stp_file": compound.stp_file,
            "row_status": "name_only",
            "structure_status": "name_only",
            "structure_id": "",
            "smiles": "",
            "inchikey": "",
            "stereo_status": "",
            "submission_status": "not_applicable",
            "export_kind": "",
            "export_sha256": "",
            "issue_codes": "",
        }
        _check_row(row)
        table.append(row)
    return table


def build_structure_rows(
    rows: list[CompoundRow],
    registration: RegistrationResult,
    binding: BindingResult,
) -> list[dict[str, str]]:
    """Build structure-aware table rows from registration and submission outcomes."""
    if not (
        len(rows) == len(registration.outcomes) == len(binding.outcomes)
    ):
        raise ValueError("rows, registration outcomes and binding outcomes do not line up")
    table: list[dict[str, str]] = []
    for compound, structure, submission in zip(
        rows, registration.outcomes, binding.outcomes, strict=True
    ):
        registered = structure.status == "registered" and structure.structure is not None
        codes = sorted(
            {issue.code for issue in structure.issues}
            | {issue.code for issue in submission.issues}
        )
        row = {
            "compound_id": compound.compound_id,
            "group": compound.group,
            "name": compound.name,
            "stp_file": compound.stp_file,
            "row_status": (
                "accepted"
                if registered and submission.status != "rejected"
                else "quarantined"
            ),
            "structure_status": "registered" if registered else "not_registered",
            "structure_id": structure.structure["structure_id"] if registered else "",
            "smiles": structure.structure["smiles"] if registered else "",
            "inchikey": structure.structure["inchikey"] if registered else "",
            "stereo_status": structure.structure["stereo_status"] if registered else "",
            "submission_status": submission.status,
            "export_kind": submission.export_kind,
            "export_sha256": submission.export_sha256,
            "issue_codes": ";".join(codes),
        }
        _check_row(row)
        table.append(row)
    return table


def collect_issues(
    registration: RegistrationResult | None, binding: BindingResult
) -> list[Issue]:
    """Collect every issue of a run in the audit order."""
    issues = list(binding.orphan_issues)
    if registration is not None:
        for outcome in registration.outcomes:
            issues.extend(outcome.issues)
    for outcome in binding.outcomes:
        issues.extend(outcome.issues)
    return sorted_issues(issues)


def summarize(
    table: list[dict[str, str]],
    registration: RegistrationResult | None,
    issues: list[Issue],
) -> dict[str, int]:
    """Return the 13 audit counts in schema order."""
    statuses = [row["submission_status"] for row in table]
    summary = {
        "rows": len(table),
        "rows_accepted": sum(row["row_status"] == "accepted" for row in table),
        "rows_quarantined": sum(row["row_status"] == "quarantined" for row in table),
        "rows_name_only": sum(row["row_status"] == "name_only" for row in table),
        "structures_new": registration.new if registration else 0,
        "structures_reused": registration.reused if registration else 0,
        "structures_superseded": registration.superseded if registration else 0,
        "submissions_verified": statuses.count("verified")
        + statuses.count("verified_kind_unstated"),
        "submissions_reconstructed": statuses.count("reconstructed"),
        "submissions_not_recorded": statuses.count("not_recorded"),
        "submissions_rejected": statuses.count("rejected"),
        "errors": sum(issue.level == "error" for issue in issues),
        "warnings": sum(issue.level == "warning" for issue in issues),
    }
    return summary


def write_structures_table(path: str | Path, rows: list[dict[str, str]]) -> None:
    """Validate and atomically write the table, including a header-only empty table."""
    problems: list[str] = []
    for number, row in enumerate(rows, start=1):
        problems.extend(
            f"row {number}: {problem}"
            for problem in schema_problems("compound_structures_row", row)
        )
    if problems:
        raise SchemaViolation(
            "the compound_structures table is not valid", details=problems
        )
    write_table_atomic(
        path,
        lambda temporary: write_table(temporary, rows, STRUCTURES_COLUMNS),
    )
