"""Entry-A structure registration library.

This is a library only: it has no command yet. RDKit is imported lazily by
:mod:`rnp.structures.chem`, so ``import rnp.structures`` does not require the
optional ``chem`` extra.
"""

from __future__ import annotations

from .checks import (
    check_issues,
    check_registry,
    check_summary,
    check_table,
)
from .chem import ChemUnavailable, StructureError, StructureInfo, describe_smiles, toolkit_version
from .model import CompoundRow, Issue
from .registry import (
    REGISTRY_COLUMNS,
    RegistrationResult,
    StructureOutcome,
    read_registry,
    register_structures,
    write_registry,
)
from .submissions import (
    BindingResult,
    LogRow,
    SubmissionOutcome,
    bind_submissions,
    read_submission_log,
    species_label,
)
from .table import (
    STRUCTURES_COLUMNS,
    SUMMARY_FIELDS,
    build_name_only_rows,
    build_structure_rows,
    collect_issues,
    summarize,
    write_structures_table,
)

__all__ = [
    "REGISTRY_COLUMNS",
    "STRUCTURES_COLUMNS",
    "SUMMARY_FIELDS",
    "BindingResult",
    "ChemUnavailable",
    "CompoundRow",
    "Issue",
    "LogRow",
    "RegistrationResult",
    "StructureError",
    "StructureInfo",
    "StructureOutcome",
    "SubmissionOutcome",
    "bind_submissions",
    "build_name_only_rows",
    "build_structure_rows",
    "check_issues",
    "check_registry",
    "check_summary",
    "check_table",
    "collect_issues",
    "describe_smiles",
    "read_registry",
    "read_submission_log",
    "register_structures",
    "species_label",
    "summarize",
    "toolkit_version",
    "write_registry",
    "write_structures_table",
]
