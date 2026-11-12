"""Apply the decisions of a compounds stage while it still describes the inputs.

`rnp ingest stp --compounds DIR` reads the directory written by `rnp ingest compounds` so a
quarantined compound takes its export out of the analysis and, in structure mode, the registered
table gains the structure columns. A stage that is not current is refused before anything is
written: a changed audit or table, a changed compound table, a different run config, other compound
identities, or export bytes that no longer hash to what the stage checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..errors import InputError
from ..normalize.identities import CompoundRecord
from ..provenance import sha256_file
from ..structures.model import schema_problems
from ..structures.tables import read_rows
from .parents import check_config_identity, load_parent_audit

AUDIT_NAME = "compounds_audit.json"
TABLE_NAME = "compound_structures.tsv"
CHECKED_SUBMISSIONS = {"verified", "verified_kind_unstated", "reconstructed"}
IDENTITY_FIELDS = ("compound_id", "group", "name", "stp_file")


@dataclass(frozen=True)
class CompoundsStage:
    """The compounds stage directory, read back for the ingest stage."""

    directory: Path
    audit_path: Path
    table_path: Path
    audit: dict[str, Any]
    rows: list[dict[str, str]]

    @property
    def identity_mode(self) -> str:
        """Return the identity mode the stage ran in."""
        return self.audit["identity_mode"]

    @property
    def stage_status(self) -> str:
        """Return the stage status the compounds stage recorded."""
        return self.audit["stage_status"]

    @property
    def quarantined(self) -> set[str]:
        """Return the compound ids the stage quarantined."""
        return {
            row["compound_id"] for row in self.rows if row["row_status"] == "quarantined"
        }


def load_compounds_stage(
    directory: str | Path, config: RunConfig, compounds_path: Path
) -> CompoundsStage:
    """Read a compounds stage directory and refuse it unless it is still current."""
    root = Path(directory).resolve()
    if not root.is_dir():
        raise InputError(f"compounds stage directory not found: {root}")
    audit_path = root / AUDIT_NAME
    audit, _ = load_parent_audit(
        audit_path, "compounds_audit", stage_name="compounds", allow_partial=True
    )
    check_config_identity(audit, config, "compounds")
    table_path = root / TABLE_NAME
    if not table_path.is_file():
        raise InputError(f"compounds stage table not found: {table_path}")
    if sha256_file(table_path) != audit["compound_structures_sha256"]:
        raise InputError(
            f"{TABLE_NAME} does not match its audit",
            details=[
                "the table changed after the compounds stage wrote it; "
                "re-run rnp ingest compounds"
            ],
        )
    _, rows = read_rows(table_path)
    problems = [
        f"row {number}: {problem}"
        for number, row in enumerate(rows, start=1)
        for problem in schema_problems("compound_structures_row", row)
    ]
    if problems:
        raise InputError(f"{TABLE_NAME} is not valid", details=problems)
    if sha256_file(compounds_path) != audit["inputs"]["compounds"]["sha256"]:
        raise InputError(
            "the compound table changed since the compounds stage",
            details=["re-run rnp ingest compounds so the structures match the table"],
        )
    return CompoundsStage(root, audit_path, table_path, audit, rows)


def check_identities(stage: CompoundsStage, records: list[CompoundRecord]) -> None:
    """Refuse a stage whose rows no longer name the compounds registered now."""
    if len(stage.rows) != len(records):
        raise InputError(
            "the compounds stage does not match the compound table",
            details=[f"{len(stage.rows)} rows in the stage, {len(records)} compounds now"],
        )
    problems = []
    for number, (row, record) in enumerate(zip(stage.rows, records, strict=True), start=1):
        for field in IDENTITY_FIELDS:
            now = getattr(record, field)
            was = row[field]
            if now != was:
                problems.append(
                    f"row {number}: {field} is {now!r} now, {was!r} in the compounds stage"
                )
    if problems:
        raise InputError(
            "the compounds stage does not match the compound identities registered now",
            details=[*problems, "re-run rnp ingest compounds"],
        )


def check_exports(
    stage: CompoundsStage,
    records: list[CompoundRecord],
    sha256_by_export: dict[str, str],
) -> None:
    """Refuse exports whose bytes no longer hash to what the compounds stage checked."""
    problems = []
    for row, record in zip(stage.rows, records, strict=True):
        if row["row_status"] == "quarantined":
            continue
        if row["submission_status"] not in CHECKED_SUBMISSIONS:
            continue
        expected = row["export_sha256"]
        actual = sha256_by_export.get(record.stp_file)
        if expected and actual is not None and expected != actual:
            problems.append(
                f"{record.stp_file}: sha256 is {actual}, "
                f"the compounds stage checked {expected}"
            )
    if problems:
        raise InputError(
            "an export changed since the compounds stage",
            details=[
                *problems,
                "re-run rnp ingest compounds so the log is checked against the current exports",
            ],
        )
