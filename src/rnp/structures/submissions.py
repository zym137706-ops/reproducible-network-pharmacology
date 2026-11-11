"""Bind the researcher's STP submission log to registered structures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..errors import InputError
from ..provenance import sha256_file
from .model import CompoundRow, Issue, schema_problems, sorted_issues
from .registry import StructureOutcome
from .tables import read_rows

RULE_VERSION = "v0.2.0-submission-binding"
_REQUIRED = ("stp_file", "submitted_structure", "species", "submitted_date")


@dataclass(frozen=True)
class LogRow:
    """One data row of the submission log, stripped and numbered."""

    row: int
    cells: dict[str, str]


@dataclass
class SubmissionOutcome:
    """The binding result for one compound row."""

    row: int
    compound_id: str
    status: str
    export_kind: str
    export_sha256: str
    issues: list[Issue]


@dataclass
class BindingResult:
    """Per-compound outcomes plus warnings for unused log rows."""

    outcomes: list[SubmissionOutcome]
    orphan_issues: list[Issue]


def species_label(species: str) -> str:
    """Convert a run-config species identifier to the log's display form."""
    return species.replace("_", " ")


def read_submission_log(path: str | Path) -> list[LogRow]:
    """Read, strip and validate a submission log."""
    log_path = Path(path)
    header, rows = read_rows(log_path)
    missing = [column for column in _REQUIRED if column not in header]
    if missing:
        raise InputError(
            f"{log_path.name}: the submission log lacks required column(s)",
            details=[", ".join(missing)],
        )

    log_rows: list[LogRow] = []
    problems: list[str] = []
    for number, row in enumerate(rows, start=1):
        cells = {column: value.strip() for column, value in row.items()}
        problems.extend(
            f"row {number}: {problem}"
            for problem in schema_problems("submission_log_row", cells)
        )
        log_rows.append(LogRow(number, cells))
    if problems:
        raise InputError(
            f"{log_path.name}: the submission log has invalid rows", details=problems
        )

    by_file: dict[str, list[int]] = {}
    for entry in log_rows:
        by_file.setdefault(entry.cells["stp_file"], []).append(entry.row)
    duplicates = [
        f"{stp_file}: rows {', '.join(str(row) for row in numbers)}"
        for stp_file, numbers in sorted(by_file.items())
        if len(numbers) > 1
    ]
    if duplicates:
        raise InputError(
            f"{log_path.name}: stp_file appears more than once in the submission log",
            details=duplicates,
        )
    return log_rows


def bind_submissions(
    rows: list[CompoundRow],
    registration: list[StructureOutcome],
    log: list[LogRow] | None,
    *,
    stp_dir: Path | None,
    species: str,
    hasher: Callable[[Path], str] = sha256_file,
) -> BindingResult:
    """Compare every registered compound with its optional submission-log row."""
    if len(rows) != len(registration) or any(
        compound.row != outcome.row for compound, outcome in zip(rows, registration, strict=True)
    ):
        raise ValueError("compound rows and structure outcomes do not line up")
    if log is not None and stp_dir is None:
        raise ValueError("a submission log needs an STP export directory")

    log_by_file: dict[str, LogRow] = {}
    for entry in log or []:
        if entry.cells["stp_file"] in log_by_file:
            raise ValueError("stp_file is repeated in the submission log")
        log_by_file[entry.cells["stp_file"]] = entry

    wanted_species = species_label(species)
    used: set[int] = set()
    outcomes: list[SubmissionOutcome] = []

    for compound, registered in zip(rows, registration, strict=True):
        entry = log_by_file.get(compound.stp_file) if compound.stp_file else None
        if entry is not None:
            used.add(entry.row)
        if registered.status != "registered":
            outcomes.append(
                SubmissionOutcome(compound.row, compound.compound_id, "not_checked", "", "", [])
            )
            continue
        if entry is None:
            issue = Issue(
                "warning",
                "submission_record_missing",
                "compounds",
                compound.row,
                compound.compound_id,
                "no submission log row belongs to this compound",
            )
            outcomes.append(
                SubmissionOutcome(
                    compound.row, compound.compound_id, "not_recorded", "", "", [issue]
                )
            )
            continue

        cells = entry.cells
        issues: list[Issue] = []

        def add(
            level: str,
            code: str,
            message: str,
            *,
            _issues: list[Issue] = issues,
            _entry: LogRow = entry,
            _compound: CompoundRow = compound,
        ) -> None:
            _issues.append(
                Issue(
                    level,
                    code,
                    "submission_log",
                    _entry.row,
                    _compound.compound_id,
                    message,
                )
            )

        if cells.get("compound", "") and cells["compound"] != compound.name:
            add(
                "error",
                "submission_name_mismatch",
                f"the log names {cells['compound']!r}, not {compound.name!r}",
            )
        if (
            cells.get("pubchem_cid", "")
            and compound.pubchem_cid
            and cells["pubchem_cid"] != compound.pubchem_cid
        ):
            add(
                "error",
                "submission_cid_mismatch",
                f"pubchem_cid {cells['pubchem_cid']} in the log, "
                f"{compound.pubchem_cid} in the compound table",
            )
        if cells["submitted_structure"] != registered.structure["smiles"]:
            add(
                "error",
                "submission_structure_mismatch",
                "the submitted structure is not the registered one",
            )
        if cells["species"] != wanted_species:
            add(
                "error",
                "submission_species_mismatch",
                f"the log says {cells['species']!r}, the run wants {wanted_species!r}",
            )

        export_name = cells["stp_file"]
        actual = ""
        if Path(export_name).name != export_name or not (
            stp_dir / export_name
        ).is_file():
            add(
                "error",
                "submission_export_missing",
                f"export file {export_name!r} was not found",
            )
        else:
            actual = hasher(stp_dir / export_name)
            declared = cells.get("result_sha256", "")
            if not declared:
                add(
                    "warning",
                    "submission_hash_not_declared",
                    "the log declares no result_sha256",
                )
            elif declared != actual:
                add(
                    "error",
                    "submission_hash_mismatch",
                    "the declared sha256 differs from the file",
                )

        has_error = any(issue.level == "error" for issue in issues)
        export_kind = cells.get("export_kind", "")
        if has_error:
            status = "rejected"
            export_kind = ""
        elif export_kind == "native_export":
            status = "verified"
        elif export_kind == "":
            status = "verified_kind_unstated"
        elif export_kind == "reconstructed_from_result_page":
            status = "reconstructed"
            add(
                "warning",
                "submission_export_reconstructed",
                "the export was reconstructed from the result page",
            )
        else:
            raise ValueError(f"unknown export_kind: {export_kind!r}")
        outcomes.append(
            SubmissionOutcome(
                compound.row,
                compound.compound_id,
                status,
                export_kind,
                actual,
                sorted_issues(issues),
            )
        )

    orphan_issues: list[Issue] = []
    for entry in log or []:
        if entry.row not in used:
            orphan_issues.append(
                Issue(
                    "warning",
                    "log_row_without_compound",
                    "submission_log",
                    entry.row,
                    "",
                    f"no compound row has stp_file {entry.cells['stp_file']!r}",
                )
            )
    return BindingResult(outcomes, sorted_issues(orphan_issues))
