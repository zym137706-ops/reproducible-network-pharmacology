"""Apply the decisions of a selection stage while it still describes the inputs.

`rnp ingest stp --compounds DIR --selection DIR2` reads the directory written by
`rnp compounds select` so only the exports of the selected compounds are parsed: an exclusion is
a recorded decision, not evidence of a problem, so the export is reported as `not_selected` with
its reason instead of being quarantined. A stage that is not current is refused before anything is
written: a changed audit, table, list, decision table or compounds stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import RunConfig
from ..errors import InputError
from ..provenance import sha256_file
from ..structures.model import schema_problems
from ..structures.tables import read_rows
from .compounds_link import CompoundsStage
from .parents import check_config_identity, load_parent_audit

AUDIT_NAME = "selection_audit.json"
TABLE_NAME = "selection_decisions.tsv"
LIST_NAME = "selected_compounds.tsv"
UNRESOLVED_STATUSES = ("needs_review", "quarantined")


@dataclass(frozen=True)
class SelectionStage:
    """The selection stage directory, read back for the ingest stage."""

    directory: Path
    audit_path: Path
    table_path: Path
    list_path: Path
    decisions_path: Path
    audit: dict[str, Any]
    rows: list[dict[str, str]]

    @property
    def stage_status(self) -> str:
        """Return the stage status the selection stage recorded."""
        return self.audit["stage_status"]

    @property
    def statuses(self) -> dict[str, str]:
        """Return the selection status of every candidate, by compound id."""
        return {row["compound_id"]: row["selection_status"] for row in self.rows}

    @property
    def quarantined(self) -> set[str]:
        """Return the compound ids the selection stage still holds as quarantined."""
        return {
            row["compound_id"] for row in self.rows if row["selection_status"] == "quarantined"
        }

    def count(self, status: str) -> int:
        """Return how many candidates have the given selection status."""
        return sum(1 for row in self.rows if row["selection_status"] == status)


def load_selection_stage(
    directory: str | Path, config: RunConfig, compounds: CompoundsStage
) -> SelectionStage:
    """Read a selection stage directory and refuse it unless it is still current."""
    root = Path(directory).resolve()
    if not root.is_dir():
        raise InputError(f"selection stage directory not found: {root}")
    audit_path = root / AUDIT_NAME
    audit, _ = load_parent_audit(
        audit_path, "selection_audit", stage_name="selection", allow_partial=True
    )
    check_config_identity(audit, config, "selection")
    table_path = root / TABLE_NAME
    if not table_path.is_file():
        raise InputError(f"selection stage table not found: {table_path}")
    if sha256_file(table_path) != audit["selection_decisions_sha256"]:
        raise InputError(
            f"{TABLE_NAME} does not match its audit",
            details=[
                "the table changed after the selection stage wrote it; "
                "re-run rnp compounds select"
            ],
        )
    list_path = root / LIST_NAME
    if not list_path.is_file():
        raise InputError(f"selection stage list not found: {list_path}")
    if sha256_file(list_path) != audit["selected_compounds_sha256"]:
        raise InputError(
            f"{LIST_NAME} does not match its audit",
            details=[
                "the list changed after the selection stage wrote it; "
                "re-run rnp compounds select"
            ],
        )
    if "selection" not in config.data["inputs"]:
        raise InputError("inputs.selection is not set")
    decisions_path = config.input_path("selection")
    if not decisions_path.is_file():
        raise InputError(f"inputs.selection is not a file: {decisions_path}")
    if sha256_file(decisions_path) != audit["inputs"]["selection"]["sha256"]:
        raise InputError(
            "the decision table changed since the selection stage",
            details=["re-run rnp compounds select so the selection matches the decisions"],
        )
    if (
        audit["inputs"]["compounds_stage"]["audit_sha256"]
        != sha256_file(compounds.audit_path)
    ):
        raise InputError(
            "the selection stage was made from another compounds stage",
            details=[
                "re-run rnp compounds select on the compounds stage given with --compounds"
            ],
        )
    _, rows = read_rows(table_path)
    problems = [
        f"row {number}: {problem}"
        for number, row in enumerate(rows, start=1)
        for problem in schema_problems("selection_decisions_row", row)
    ]
    if problems:
        raise InputError(f"{TABLE_NAME} is not valid", details=problems)
    candidates = [row["compound_id"] for row in rows]
    registered = [row["compound_id"] for row in compounds.rows]
    if candidates != registered:
        if len(candidates) != len(registered):
            details = [
                f"{len(candidates)} rows in the selection stage, {len(registered)} compounds now"
            ]
        else:
            details = ["the candidates are not the compounds of the compounds stage, in order"]
        raise InputError("the selection stage does not match the compounds stage", details=details)
    return SelectionStage(
        root, audit_path, table_path, list_path, decisions_path, audit, rows
    )
