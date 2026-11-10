"""Cross-row checks that JSON Schema cannot express."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from ..errors import InputError
from .model import CompoundRow, Issue

_STRUCTURE_ID = re.compile(r"STR[0-9]{4,}")


def structure_number(structure_id: str) -> int:
    """Return the numeric part of a structure id, or raise ``ValueError``."""
    if not _STRUCTURE_ID.fullmatch(structure_id):
        raise ValueError(f"not a structure id: {structure_id!r}")
    return int(structure_id[3:])


def check_registry(rows: list[dict[str, str]]) -> list[str]:
    """Return consistency problems of a structure registry, in a stable order."""
    problems: list[str] = []
    id_counts = Counter(row["structure_id"] for row in rows)
    for structure_id in sorted(
        structure_id for structure_id, count in id_counts.items() if count > 1
    ):
        problems.append(f"structure_id {structure_id} appears {id_counts[structure_id]} times")

    string_counts = Counter((row["compound_id"], row["smiles"]) for row in rows)
    for compound_id, smiles in sorted(key for key, count in string_counts.items() if count > 1):
        problems.append(
            f"{compound_id} has the structure {smiles} registered "
            f"{string_counts[(compound_id, smiles)]} times"
        )

    by_compound: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_compound[row["compound_id"]].append(row)
    for compound_id in sorted(by_compound):
        current = sum(1 for row in by_compound[compound_id] if row["status"] == "current")
        if current != 1:
            problems.append(f"{compound_id} has {current} current structures, expected exactly 1")

    first_by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        first_by_id.setdefault(row["structure_id"], row)
    for number, row in enumerate(rows, start=1):
        where = f"row {number} ({row['structure_id']})"
        if row["status"] == "superseded":
            target = row["superseded_by"]
            target_row = first_by_id.get(target)
            if target_row is None:
                problems.append(f"{where}: superseded_by {target} is not in the registry")
            elif target_row["compound_id"] != row["compound_id"]:
                problems.append(f"{where}: superseded_by {target} belongs to another compound")
            elif target == row["structure_id"]:
                problems.append(f"{where}: superseded_by points to itself")

        expected_block = row["inchikey"].split("-")[0]
        if row["connectivity_block"] != expected_block:
            problems.append(f"{where}: connectivity_block is not the first block of the inchikey")
        if row["stereo_status"] == "defined" and (
            row["stereo_elements_specified"] != row["stereo_elements_total"]
        ):
            problems.append(
                f"{where}: stereo_status is defined but only "
                f"{row['stereo_elements_specified']} of {row['stereo_elements_total']} are"
            )
        if row["stereo_status"] == "partially_defined" and not (
            int(row["stereo_elements_specified"]) < int(row["stereo_elements_total"])
        ):
            problems.append(
                f"{where}: stereo_status is partially_defined but "
                f"{row['stereo_elements_specified']} of {row['stereo_elements_total']}"
            )
        if row["first_seen_utc"] > row["last_seen_utc"]:
            problems.append(f"{where}: first_seen_utc is later than last_seen_utc")
    return problems


def check_table(
    rows: list[dict[str, str]],
    registry: list[dict[str, str]],
    compounds: list[CompoundRow],
) -> list[str]:
    """Compare compound_structures rows with the inputs and the structure registry."""
    problems: list[str] = []
    if len(rows) != len(compounds):
        problems.append(f"{len(rows)} table rows for {len(compounds)} input rows")
    registry_by_id = {row["structure_id"]: row for row in registry}
    for number, (row, compound) in enumerate(
        zip(rows, compounds, strict=False), start=1
    ):
        where = f"row {number} ({compound.compound_id})"
        if row["compound_id"] != compound.compound_id:
            problems.append(
                f"{where}: compound_id is {row['compound_id']}, expected {compound.compound_id}"
            )
        codes = [code for code in row["issue_codes"].split(";") if code]
        if codes != sorted(set(codes)):
            problems.append(f"{where}: issue_codes are not sorted and unique")
        structure_id = row["structure_id"]
        if not structure_id:
            continue
        registered = registry_by_id.get(structure_id)
        if registered is None:
            problems.append(f"{where}: {structure_id} is not in the registry")
            continue
        if registered["compound_id"] != row["compound_id"]:
            problems.append(
                f"{where}: {structure_id} belongs to {registered['compound_id']}"
            )
        if registered["status"] != "current":
            problems.append(
                f"{where}: {structure_id} is not the current structure of the compound"
            )
        for column in ("smiles", "inchikey", "stereo_status"):
            if row[column] != registered[column]:
                problems.append(f"{where}: {column} differs from the registry")
    return problems


def check_issues(rows: list[dict[str, str]], issues: list[Issue]) -> list[str]:
    """Check that each row's issue codes and quarantine status match the run issues."""
    problems: list[str] = []
    grouped: dict[str, list[Issue]] = {}
    for issue in issues:
        if issue.compound_id:
            grouped.setdefault(issue.compound_id, []).append(issue)

    known = {row["compound_id"] for row in rows}
    for compound_id in sorted(set(grouped) - known):
        problems.append(f"{compound_id}: has issues but no table row")

    for number, row in enumerate(rows, start=1):
        compound_id = row["compound_id"]
        where = f"row {number} ({compound_id})"
        table_codes = sorted({code for code in row["issue_codes"].split(";") if code})
        issue_codes = sorted({issue.code for issue in grouped.get(compound_id, [])})
        if table_codes != issue_codes:
            table_text = ";".join(table_codes) if table_codes else "(none)"
            issue_text = ";".join(issue_codes) if issue_codes else "(none)"
            problems.append(
                f"{where}: issue_codes are {table_text}, the issues say {issue_text}"
            )
        has_error = any(
            issue.level == "error" for issue in grouped.get(compound_id, [])
        )
        if row["row_status"] == "quarantined" and not has_error:
            problems.append(f"{where}: quarantined, but no error issue explains it")
        if has_error and row["row_status"] != "quarantined":
            problems.append(f"{where}: has an error issue but is {row['row_status']}")
    return problems


def check_summary(
    summary: dict[str, int],
    rows: list[dict[str, str]],
    errors: int,
    warnings: int,
) -> list[str]:
    """Compare the audit summary with counts derived from the table."""
    expected = {
        "rows": len(rows),
        "rows_accepted": sum(row["row_status"] == "accepted" for row in rows),
        "rows_quarantined": sum(row["row_status"] == "quarantined" for row in rows),
        "rows_name_only": sum(row["row_status"] == "name_only" for row in rows),
        "submissions_verified": sum(
            row["submission_status"] in {"verified", "verified_kind_unstated"}
            for row in rows
        ),
        "submissions_reconstructed": sum(
            row["submission_status"] == "reconstructed" for row in rows
        ),
        "submissions_not_recorded": sum(
            row["submission_status"] == "not_recorded" for row in rows
        ),
        "submissions_rejected": sum(
            row["submission_status"] == "rejected" for row in rows
        ),
        "errors": errors,
        "warnings": warnings,
    }
    problems: list[str] = []
    for name, value in expected.items():
        if summary.get(name) != value:
            problems.append(
                f"summary.{name} is {summary.get(name)}, the table says {value}"
            )
    return problems


def raise_if_problems(problems: list[str], message: str) -> None:
    """Raise one InputError with every problem, if there is any."""
    if problems:
        raise InputError(message, details=problems)
