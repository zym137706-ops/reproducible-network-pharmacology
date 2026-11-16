"""The selection stage: the researcher's decisions applied to the candidates of a compounds stage.

The stage reads the compounds stage directory and the decision table, derives the full candidate
table (no candidate is dropped), the selected list, the audit and the manifest. It writes no
registry and never touches the compounds stage: a change of decisions only reruns this step.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config import RunConfig, validate_document
from ..errors import InputError, SchemaViolation
from ..output import staged_output
from ..provenance import build_manifest, sha256_file, utc_now_iso, write_json
from ..selection import (
    RULE_VERSION,
    check_selection,
    derive_selection,
    read_decisions,
    selected_rows,
    summarize,
    write_selection_table,
)
from .compounds_link import load_compounds_stage
from .parents import parent_record

AUDIT_NAME = "selection_audit.json"
TABLE_NAME = "selection_decisions.tsv"
SELECTED_NAME = "selected_compounds.tsv"
MANIFEST_NAME = "run_manifest.json"
UNRESOLVED_STATUSES = ("needs_review", "quarantined")


def _run_id(config: RunConfig, override: str | None, now: str) -> str:
    if override:
        base = override
    else:
        stamp = now.replace("-", "").replace(":", "")
        base = f"{stamp}_{config.sha256[:8]}"
    return f"{base}_selection"


def _notes(extra_columns: list[str]) -> list[dict[str, str]]:
    if not extra_columns:
        return []
    return [
        {
            "code": "extra_columns_ignored",
            "message": "ignored columns of the selection table: "
            + ", ".join(extra_columns),
        }
    ]


def _stage_status(rows: list[dict[str, str]]) -> str:
    if any(row["selection_status"] in UNRESOLVED_STATUSES for row in rows):
        return "partial"
    return "complete"


def _unresolved(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "compound_id": row["compound_id"],
            "selection_status": row["selection_status"],
            "issue_codes": row["issue_codes"].split(";") if row["issue_codes"] else [],
        }
        for row in rows
        if row["selection_status"] in UNRESOLVED_STATUSES
    ]


def run_selection(
    config: RunConfig,
    *,
    compounds: str | Path,
    run_id: str | None = None,
    force: bool = False,
    now: Callable[[], str] = utc_now_iso,
) -> dict[str, Any]:
    """Run the selection stage and return its summary."""
    if "selection" not in config.data["inputs"]:
        raise InputError(
            "inputs.selection is not set: rnp compounds select needs the table of decisions",
            details=[
                "add inputs.selection to the run config before the first rnp ingest compounds run: "
                "the stages are tied together by the hash of the run config"
            ],
        )
    decisions_path = config.input_path("selection")
    if not decisions_path.is_file():
        raise InputError(f"inputs.selection is not a file: {decisions_path}")
    compounds_path = Path(compounds)
    stage = load_compounds_stage(compounds_path, config, config.input_path("compounds"))
    started_at = now()
    decisions = read_decisions(decisions_path)
    derivation = derive_selection(stage.rows, decisions)
    selected = selected_rows(derivation.rows)
    summary = summarize(derivation.rows, derivation.issues)
    problems = check_selection(
        derivation.rows,
        selected,
        stage.rows,
        issues=derivation.issues,
        summary=summary,
    )
    if problems:
        raise SchemaViolation("the selection stage is internally inconsistent", details=problems)
    stage_status = _stage_status(derivation.rows)
    run = _run_id(config, run_id, started_at)
    run_dir = config.output_dir / run
    notes = _notes(decisions.extra_columns)

    with staged_output(run_dir, force=force) as work:
        write_selection_table(work / TABLE_NAME, derivation.rows)
        write_selection_table(work / SELECTED_NAME, selected)
        audit = {
            "schema_version": "1.0",
            "generated_by": "rnp compounds select",
            "stage_status": stage_status,
            "identity_mode": stage.identity_mode,
            "config": {"path": str(config.path), "sha256": sha256_file(config.path)},
            "inputs": {
                "compounds_stage": {
                    "dir": str(compounds_path),
                    "audit_sha256": sha256_file(stage.audit_path),
                    "table_sha256": sha256_file(stage.table_path),
                    "stage_status": stage.stage_status,
                },
                "selection": {
                    "path": str(decisions_path),
                    "sha256": sha256_file(decisions_path),
                    "rows": len(decisions.rows),
                },
            },
            "rule_versions": {"selection": RULE_VERSION},
            "summary": summary,
            "issues": [issue.as_dict() for issue in derivation.issues],
            "notes": notes,
            "selection_decisions_sha256": sha256_file(work / TABLE_NAME),
            "selected_compounds_sha256": sha256_file(work / SELECTED_NAME),
        }
        validate_document(audit, "selection_audit", "selection audit")
        write_json(work / AUDIT_NAME, audit)

        manifest = build_manifest(
            run_id=run,
            command="compounds select",
            args={
                "config": str(config.path),
                "compounds": str(compounds_path),
                "selection": str(decisions_path),
            },
            config=config,
            inputs=[
                config.path,
                decisions_path,
                stage.audit_path,
                stage.table_path,
            ],
            parents=[
                parent_record(
                    stage="ingest compounds",
                    directory=compounds_path,
                    audit_path=stage.audit_path,
                    stage_status=stage.stage_status,
                    override=False,
                )
            ],
            started_at=started_at,
            finished_at=now(),
            exit_code=0 if stage_status == "complete" else 3,
            stage_status=stage_status,
            overwritten=force,
        )
        validate_document(manifest, "run_manifest", "run manifest")
        write_json(work / MANIFEST_NAME, manifest)

    return {
        "status": "ok" if stage_status == "complete" else "partial",
        "stage_status": stage_status,
        "identity_mode": stage.identity_mode,
        "run_id": run,
        "run_dir": str(run_dir),
        "summary": summary,
        "unresolved": _unresolved(derivation.rows),
    }
