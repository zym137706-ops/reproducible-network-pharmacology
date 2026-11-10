"""Entry-A structure registration library.

This is a library only: it has no command yet. RDKit is imported lazily by
:mod:`rnp.structures.chem`, so ``import rnp.structures`` does not require the
optional ``chem`` extra.
"""

from __future__ import annotations

from .checks import check_registry
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

__all__ = [
    "REGISTRY_COLUMNS",
    "ChemUnavailable",
    "CompoundRow",
    "Issue",
    "RegistrationResult",
    "StructureError",
    "StructureInfo",
    "StructureOutcome",
    "check_registry",
    "describe_smiles",
    "read_registry",
    "register_structures",
    "toolkit_version",
    "write_registry",
]
