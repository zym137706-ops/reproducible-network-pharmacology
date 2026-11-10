"""Immutable value objects and JSON Schema helpers for the structure library."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jsonschema
from jsonschema.validators import validator_for

from ..config import load_schema


@dataclass(frozen=True)
class CompoundRow:
    """One compound row after the compound identity registry assigned its id."""

    row: int
    compound_id: str
    group: str
    name: str
    stp_file: str
    smiles: str
    pubchem_cid: str = ""


@dataclass(frozen=True)
class Issue:
    """One row-level problem with a stable code."""

    level: str
    code: str
    source: str
    row: int
    compound_id: str
    message: str

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


def issue_sort_key(issue: Issue) -> tuple[str, int, int, str, str, str]:
    """Return the single sort key used for every issue list in the library."""
    return (
        issue.source,
        issue.row,
        0 if issue.level == "error" else 1,
        issue.code,
        issue.compound_id,
        issue.message,
    )


def sorted_issues(issues: list[Issue]) -> list[Issue]:
    """Return a new list of issues in the library's canonical order."""
    return sorted(issues, key=issue_sort_key)


_VALIDATORS: dict[str, jsonschema.protocols.Validator] = {}


def schema_problems(schema_name: str, document: Any) -> list[str]:
    """Return schema violations as ``location: message`` strings, sorted by path."""
    if schema_name not in _VALIDATORS:
        schema = load_schema(schema_name)
        _VALIDATORS[schema_name] = validator_for(schema)(schema)
    validator = _VALIDATORS[schema_name]
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    problems: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<row>"
        problems.append(f"{location}: {error.message}")
    return problems
