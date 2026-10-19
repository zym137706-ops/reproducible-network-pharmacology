"""Stage-state checks: downstream commands refuse incomplete upstream artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import validate_document
from ..errors import InputError
from ..provenance import sha256_file

COMPLETE_STATES = {"complete"}


def load_parent_audit(
    audit_path: str | Path,
    schema_name: str,
    *,
    stage_name: str,
    allow_partial: bool,
) -> tuple[dict[str, Any], bool]:
    """Load and validate a parent audit; return ``(audit, override_used)``."""
    path = Path(audit_path)
    if not path.is_file():
        raise InputError(
            f"{stage_name} audit not found: {path}",
            details=["re-run the upstream stage so its status can be verified"],
        )
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read {stage_name} audit {path.name}: {exc}") from exc
    validate_document(audit, schema_name, f"{stage_name} audit")
    status = audit.get("stage_status", "unknown")
    override = False
    if status not in COMPLETE_STATES:
        if not allow_partial:
            raise InputError(
                f"upstream {stage_name} stage is {status!r}, not 'complete'",
                details=[
                    "fix the upstream inputs and re-run, or pass --allow-partial to "
                    "explicitly continue with an audited override",
                ],
            )
        override = True
    return audit, override


def check_config_identity(audit: dict[str, Any], config, stage_name: str) -> None:
    recorded = (audit.get("config") or {}).get("sha256")
    if recorded != config.sha256:
        raise InputError(
            f"run config changed since the {stage_name} stage",
            details=[
                "the parent audit was produced from a different config; "
                "re-run the upstream stage instead of mixing identities",
            ],
        )


def parent_record(
    *,
    stage: str,
    directory: Path,
    audit_path: Path,
    stage_status: str,
    override: bool,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "dir": str(directory),
        "audit": audit_path.name,
        "audit_sha256": sha256_file(audit_path),
        "stage_status": stage_status,
        "status_override": override,
    }


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise InputError(f"{description} not found: {path}")


def verify_sha256(path: Path, expected: str | None, description: str) -> None:
    if not expected:
        raise InputError(f"{description}: no recorded SHA-256 to verify against")
    actual = sha256_file(path)
    if actual != expected:
        raise InputError(
            f"{description} changed since the upstream stage",
            details=[f"expected {expected}", f"actual   {actual}"],
        )
