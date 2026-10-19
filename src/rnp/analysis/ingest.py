"""STP ingest: explicit compound↔export binding, quarantine and stage status.

The ingest stage is where an analysis either has a complete, traceable set of
inputs or it does not. Unbound exports never become formal compound edges: they
are quarantined in the audit and excluded from ``targets.tsv``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import RunConfig, validate_document
from ..errors import InputError, RnpError
from ..io import stp as stp_io
from ..io.tables import write_table
from ..normalize.identities import (
    REGISTRY_COLUMNS,
    RULE_VERSION,
    match_exports,
    register_compounds,
)
from ..output import staged_output, write_table_atomic
from ..provenance import build_manifest, sha256_file, utc_now_iso, write_json

EXPORT_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx"}
COMPOUND_COLUMNS = [
    "compound_id",
    "group",
    "name",
    "stp_file",
    "submission_id",
    "identity_basis",
]


def registry_path(config: RunConfig) -> Path:
    if "compound_registry" in config.data["inputs"]:
        return config.input_path("compound_registry")
    return config.output_dir / "registry" / "compound_registry.tsv"


def _run_id(config: RunConfig, override: str | None) -> str:
    if override:
        return override
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{config.sha256[:8]}"


def _stage_status(file_entries: list[dict[str, Any]], missing: list[dict[str, Any]]) -> str:
    parsed = [entry for entry in file_entries if entry["status"] not in {"quarantined", "error"}]
    if not parsed:
        return "failed"
    has_problem = any(
        entry["status"] in {"error", "invalid_rows", "partial"} for entry in file_entries
    )
    return "partial" if has_problem or missing else "complete"


def run_ingest(
    config: RunConfig,
    *,
    run_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Parse the bound STP exports and write a staged, auditable target table."""
    compounds_path = config.input_path("compounds")
    stp_dir = config.input_path("stp_dir")
    if not stp_dir.is_dir():
        raise InputError(f"inputs.stp_dir is not a directory: {stp_dir}")
    threshold = float(config.data["thresholds"]["stp_probability"])
    allow_filename_match = bool(config.data["inputs"].get("allow_filename_match", False))
    registry = registry_path(config)

    records, registry_rows, notes = register_compounds(
        compounds_path, registry, allow_filename_match=allow_filename_match
    )
    files = sorted(
        path
        for path in stp_dir.iterdir()
        if path.is_file() and path.suffix.lower() in EXPORT_SUFFIXES
    )
    if not files:
        raise InputError(f"inputs.stp_dir contains no export files: {stp_dir}")
    bindings, unbound, match_notes = match_exports(
        records, files, allow_filename_match=allow_filename_match
    )
    notes.extend(match_notes)

    file_entries: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    present = {path.name for path in files}
    for compound in records:
        if compound.stp_file and compound.stp_file not in present:
            missing.append(
                {
                    "compound_id": compound.compound_id,
                    "stp_file": compound.stp_file,
                    "status": "error",
                    "reason": "missing_export",
                }
            )

    unbound_reasons = {item["path"]: item["reason"] for item in unbound}
    for path in files:
        compound = bindings.get(path.name)
        if compound is None:
            file_entries.append(
                {
                    "path": path.name,
                    "format": "xlsx" if path.suffix.lower() == ".xlsx" else "csv",
                    "sha256": sha256_file(path),
                    "status": "quarantined",
                    "reason": unbound_reasons.get(path.name, "not_bound_to_compound"),
                    "warnings": [],
                    "errors": [],
                    "rows_total": 0,
                    "rows_valid": 0,
                    "rows_invalid": 0,
                    "rows_below_threshold": 0,
                    "rows_used": 0,
                }
            )
            continue
        try:
            parsed = stp_io.parse_export(path, threshold=threshold)
        except RnpError as exc:
            file_entries.append(
                {
                    "path": path.name,
                    "format": "xlsx" if path.suffix.lower() == ".xlsx" else "csv",
                    "sha256": sha256_file(path),
                    "status": "error",
                    "compound_id": compound.compound_id,
                    "group": compound.group,
                    "reason": "unreadable_export",
                    "warnings": [],
                    "errors": [{"code": "unreadable_export", "row": None, "message": exc.message}],
                    "rows_total": 0,
                    "rows_valid": 0,
                    "rows_invalid": 0,
                    "rows_below_threshold": 0,
                    "rows_used": 0,
                }
            )
            continue
        entry = stp_io.audit_entry(parsed, compound=compound)
        file_entries.append(entry)
        for record in parsed.records:
            targets.append(
                {
                    **record,
                    "compound_id": compound.compound_id,
                    "group": compound.group,
                    "submission_id": compound.submission_id,
                    "source_file": path.name,
                }
            )

    stage_status = _stage_status(file_entries, missing)
    if stage_status == "failed":
        problems = [
            f"{entry['path']}: {entry['status']}"
            for entry in file_entries
            if entry["status"] == "error"
        ]
        raise InputError(
            "ingest produced no usable export",
            details=problems or ["no export could be parsed"],
        )

    run = _run_id(config, run_id)
    run_dir = config.output_dir / run
    started_at = utc_now_iso()
    with staged_output(run_dir, force=force) as work:
        write_table(
            work / "compounds_registered.tsv",
            [
                {
                    "compound_id": record.compound_id,
                    "group": record.group,
                    "name": record.name,
                    "stp_file": record.stp_file,
                    "submission_id": record.submission_id,
                    "identity_basis": record.identity_basis,
                }
                for record in records
            ],
            COMPOUND_COLUMNS,
        )
        stp_io.write_targets_tsv(targets, work / "targets.tsv")
        compounds_sha = sha256_file(work / "compounds_registered.tsv")
        targets_sha = sha256_file(work / "targets.tsv")

        file_entries.sort(key=lambda entry: entry["path"])
        quarantine = [
            {"path": entry["path"], "sha256": entry["sha256"], "reason": entry.get("reason", "")}
            for entry in file_entries
            if entry["status"] == "quarantined"
        ]
        summary = {
            "files": len(file_entries),
            "files_bound": len(file_entries) - len(quarantine),
            "files_quarantined": len(quarantine),
            "files_missing": len(missing),
            "rows_total": sum(entry["rows_total"] for entry in file_entries),
            "rows_valid": sum(entry["rows_valid"] for entry in file_entries),
            "rows_invalid": sum(entry["rows_invalid"] for entry in file_entries),
            "rows_below_threshold": sum(
                entry["rows_below_threshold"] for entry in file_entries
            ),
            "rows_used": len(targets),
            "compounds_registered": len(records),
            "warnings": sum(len(entry["warnings"]) for entry in file_entries),
            "errors": sum(len(entry["errors"]) for entry in file_entries) + len(missing),
        }
        audit = {
            "schema_version": "1.1",
            "generated_by": "rnp ingest stp",
            "stage_status": stage_status,
            "config": {"path": str(config.path), "sha256": config.sha256},
            "thresholds": {"stp_probability": threshold},
            "files": file_entries,
            "quarantine": quarantine,
            "missing_exports": missing,
            "summary": summary,
            "registry": {
                "path": str(registry),
                "rule_version": RULE_VERSION,
                "entries": len(registry_rows),
            },
            "notes": notes,
            "targets_sha256": targets_sha,
            "compounds_registered_sha256": compounds_sha,
        }
        validate_document(audit, "stp_audit", "stp audit")
        write_json(work / "stp_audit.json", audit)

        exit_code = 0 if stage_status == "complete" else 3
        manifest = build_manifest(
            run_id=run,
            command="ingest stp",
            args={
                "config": str(config.path),
                "stp_dir": str(stp_dir),
                "stp_probability": threshold,
                "allow_filename_match": allow_filename_match,
            },
            config=config,
            inputs=[config.path, compounds_path, *files],
            parents=[],
            started_at=started_at,
            finished_at=utc_now_iso(),
            exit_code=exit_code,
            stage_status=stage_status,
            overwritten=force,
        )
        validate_document(manifest, "run_manifest", "run manifest")
        write_json(work / "run_manifest.json", manifest)

    write_table_atomic(
        registry,
        lambda temporary: write_table(temporary, registry_rows, REGISTRY_COLUMNS),
    )
    return {
        "status": "ok" if stage_status == "complete" else "partial",
        "stage_status": stage_status,
        "run_id": run,
        "run_dir": str(run_dir),
        "summary": summary,
        "quarantine": quarantine,
        "missing_exports": missing,
    }
