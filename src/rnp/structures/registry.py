"""Persistent structure registry: describe, supersede, reuse and write rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..errors import InputError, SchemaViolation
from ..io.tables import write_table
from ..output import write_table_atomic
from .checks import check_registry, structure_number
from .chem import TOOLKIT, StructureError, StructureInfo
from .model import CompoundRow, Issue, schema_problems, sorted_issues
from .tables import read_rows

RULE_VERSION = "v0.2.0-structure-registry"
REGISTRY_COLUMNS = [
    "structure_id",
    "compound_id",
    "smiles",
    "inchikey",
    "connectivity_block",
    "formula",
    "net_charge",
    "fragment_count",
    "stereo_status",
    "stereo_elements_specified",
    "stereo_elements_total",
    "standardization",
    "toolkit",
    "toolkit_version",
    "rule_version",
    "status",
    "superseded_by",
    "first_seen_utc",
    "last_seen_utc",
]


@dataclass
class StructureOutcome:
    """The result of registering one input compound row."""

    row: int
    compound_id: str
    status: str
    structure: dict[str, str] | None
    issues: list[Issue]


@dataclass
class RegistrationResult:
    """The outcomes, the complete new registry and the three counters."""

    outcomes: list[StructureOutcome]
    registry: list[dict[str, str]]
    new: int
    reused: int
    superseded: int


def _issue(
    level: str,
    code: str,
    source: str,
    row: CompoundRow,
    message: str,
) -> Issue:
    return Issue(level, code, source, row.row, row.compound_id, message)


def _warning_codes(row: dict[str, str], compound: CompoundRow) -> list[Issue]:
    issues: list[Issue] = []
    if row["stereo_status"] in {"partially_defined", "undefined"}:
        issues.append(
            _issue(
                "warning",
                "stereo_undefined",
                "compounds",
                compound,
                f"stereo status is {row['stereo_status']}",
            )
        )
    if int(row["fragment_count"]) > 1:
        issues.append(
            _issue(
                "warning",
                "multi_fragment",
                "compounds",
                compound,
                f"{row['fragment_count']} fragments (salt or mixture)",
            )
        )
    if int(row["net_charge"]) != 0:
        issues.append(
            _issue(
                "warning",
                "charged_structure",
                "compounds",
                compound,
                f"net charge {row['net_charge']}",
            )
        )
    return issues


def _new_row(
    compound: CompoundRow,
    smiles: str,
    info: StructureInfo,
    *,
    toolkit_version: str,
    now: str,
    structure_id: str,
) -> dict[str, str]:
    return {
        "structure_id": structure_id,
        "compound_id": compound.compound_id,
        "smiles": smiles,
        "inchikey": info.inchikey,
        "connectivity_block": info.connectivity_block,
        "formula": info.formula,
        "net_charge": str(info.net_charge),
        "fragment_count": str(info.fragment_count),
        "stereo_status": info.stereo_status,
        "stereo_elements_specified": str(info.stereo_elements_specified),
        "stereo_elements_total": str(info.stereo_elements_total),
        "standardization": "not_performed",
        "toolkit": TOOLKIT,
        "toolkit_version": toolkit_version,
        "rule_version": RULE_VERSION,
        "status": "current",
        "superseded_by": "",
        "first_seen_utc": now,
        "last_seen_utc": now,
    }


def _max_id(registry: list[dict[str, str]]) -> int:
    values: list[int] = []
    for row in registry:
        try:
            values.append(structure_number(row["structure_id"]))
        except ValueError:
            continue
    return max(values, default=0)


def _next_id(registry: list[dict[str, str]]) -> str:
    return f"STR{_max_id(registry) + 1:04d}"


def _find_exact(
    registry: list[dict[str, str]], compound_id: str, smiles: str
) -> dict[str, str] | None:
    for row in registry:
        if row["compound_id"] == compound_id and row["smiles"] == smiles:
            return row
    return None


def _current_for(registry: list[dict[str, str]], compound_id: str) -> dict[str, str] | None:
    for row in registry:
        if row["compound_id"] == compound_id and row["status"] == "current":
            return row
    return None


def register_structures(
    rows: list[CompoundRow],
    registry: list[dict[str, str]],
    *,
    toolkit_version: str,
    now: str,
    describe: Callable[[str], StructureInfo] | None = None,
) -> RegistrationResult:
    """Register every input row, returning the new registry and per-row outcomes."""
    compound_ids = [row.compound_id for row in rows]
    if len(compound_ids) != len(set(compound_ids)):
        raise ValueError("compound_id is repeated in the input rows")

    work = [dict(row) for row in registry]
    outcomes: list[StructureOutcome] = []
    new = reused = superseded = 0

    for compound in rows:
        text = compound.smiles.strip()
        issues: list[Issue] = []
        trimmed = text != compound.smiles
        if not text:
            issues.append(
                _issue(
                    "error",
                    "missing_structure",
                    "compounds",
                    compound,
                    "no SMILES string was given for this compound",
                )
            )
            outcomes.append(
                StructureOutcome(compound.row, compound.compound_id, "not_registered", None, issues)
            )
            continue

        found = _find_exact(work, compound.compound_id, text)
        if trimmed:
            issues.append(
                _issue(
                    "warning",
                    "smiles_whitespace_trimmed",
                    "compounds",
                    compound,
                    "surrounding whitespace was removed",
                )
            )
        if found is not None:
            reused += 1
            found["last_seen_utc"] = max(found["last_seen_utc"], now)
            if found["status"] == "superseded":
                old_current = _current_for(work, compound.compound_id)
                if old_current is not None and old_current is not found:
                    old_current["status"] = "superseded"
                    old_current["superseded_by"] = found["structure_id"]
                    superseded += 1
                found["status"] = "current"
                found["superseded_by"] = ""
                issues.append(
                    _issue(
                        "warning",
                        "structure_reactivated",
                        "compounds",
                        compound,
                        f"{found['structure_id']} is the current structure again",
                    )
                )
            issues.extend(_warning_codes(found, compound))
            outcomes.append(
                StructureOutcome(
                    compound.row,
                    compound.compound_id,
                    "registered",
                    dict(found),
                    issues,
                )
            )
            continue

        if describe is None:
            from . import chem

            describe = chem.describe_smiles
        try:
            info = describe(text)
        except StructureError as exc:
            message = f"{text!r} cannot be registered: {exc}"
            issues.append(_issue("error", "invalid_smiles", "compounds", compound, message))
            outcomes.append(
                StructureOutcome(
                    compound.row,
                    compound.compound_id,
                    "not_registered",
                    None,
                    sorted_issues(issues),
                )
            )
            continue

        structure_id = _next_id(work)
        row = _new_row(
            compound,
            text,
            info,
            toolkit_version=toolkit_version,
            now=now,
            structure_id=structure_id,
        )
        problems = schema_problems("structure_registry_row", row)
        if problems:
            raise SchemaViolation(
                "the structure description does not fit the registry schema",
                details=problems,
            )
        old_current = _current_for(work, compound.compound_id)
        if old_current is not None:
            old_current["status"] = "superseded"
            old_current["superseded_by"] = structure_id
            superseded += 1
            issues.append(
                _issue(
                    "warning",
                    "structure_changed",
                    "compounds",
                    compound,
                    f"{old_current['structure_id']} was replaced by {structure_id}",
                )
            )
        work.append(row)
        new += 1
        issues.extend(_warning_codes(row, compound))
        outcomes.append(
            StructureOutcome(compound.row, compound.compound_id, "registered", dict(row), issues)
        )

    final_by_id = {row["structure_id"]: row for row in work}
    for outcome in outcomes:
        if outcome.structure is not None:
            outcome.structure = dict(final_by_id[outcome.structure["structure_id"]])

    current_rows = [row for row in work if row["status"] == "current"]
    for outcome in outcomes:
        if outcome.structure is None:
            continue
        same_key = sorted(
            {
                row["compound_id"]
                for row in current_rows
                if row["compound_id"] != outcome.compound_id
                and row["inchikey"] == outcome.structure["inchikey"]
            }
        )
        if same_key:
            outcome.issues.append(
                Issue(
                    "warning",
                    "shared_structure",
                    "compounds",
                    outcome.row,
                    outcome.compound_id,
                    f"the same InChIKey is registered for {', '.join(same_key)}",
                )
            )
        same_connectivity = sorted(
            {
                row["compound_id"]
                for row in current_rows
                if row["compound_id"] != outcome.compound_id
                and row["connectivity_block"] == outcome.structure["connectivity_block"]
                and row["inchikey"] != outcome.structure["inchikey"]
            }
        )
        if same_connectivity:
            outcome.issues.append(
                Issue(
                    "warning",
                    "same_connectivity_different_stereo",
                    "compounds",
                    outcome.row,
                    outcome.compound_id,
                    "same connectivity, different stereochemistry: " + ", ".join(same_connectivity),
                )
            )

    for outcome in outcomes:
        outcome.issues = sorted_issues(outcome.issues)

    return RegistrationResult(
        outcomes=outcomes,
        registry=sorted(work, key=lambda row: structure_number(row["structure_id"])),
        new=new,
        reused=reused,
        superseded=superseded,
    )


def read_registry(path: str | Path) -> list[dict[str, str]]:
    """Read and validate a structure registry; a missing file is an empty registry."""
    registry_path = Path(path)
    if not registry_path.is_file():
        return []
    header, rows = read_rows(registry_path)
    if header != REGISTRY_COLUMNS:
        raise InputError(
            f"{registry_path.name}: the registry does not have the expected columns",
            details=[f"expected, in order: {', '.join(REGISTRY_COLUMNS)}"],
        )
    problems: list[str] = []
    for number, row in enumerate(rows, start=1):
        problems.extend(
            f"row {number}: {problem}" for problem in schema_problems("structure_registry_row", row)
        )
    if not problems:
        problems = check_registry(rows)
    if problems:
        raise InputError(
            f"{registry_path.name}: the structure registry is not valid", details=problems
        )
    return rows


def write_registry(path: str | Path, rows: list[dict[str, str]]) -> None:
    """Validate and atomically write a structure registry, sorted by structure id."""
    problems: list[str] = []
    for number, row in enumerate(rows, start=1):
        problems.extend(
            f"row {number}: {problem}" for problem in schema_problems("structure_registry_row", row)
        )
    ordered = rows
    if not problems:
        ordered = sorted(rows, key=lambda row: structure_number(row["structure_id"]))
        problems = check_registry(ordered)
    if problems:
        raise SchemaViolation("the structure registry to write is not valid", details=problems)
    write_table_atomic(
        path,
        lambda temporary: write_table(temporary, ordered, REGISTRY_COLUMNS),
    )
