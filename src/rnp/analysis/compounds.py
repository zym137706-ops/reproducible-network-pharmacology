"""The compounds stage: name-only identity or structure registration plus submission binding.

Structure mode is selected by the presence of a smiles column in the compound table. The stage
never trusts an unregistered structure: the persistent structure registry is the source of
identity, and the submission log is checked against both the registry and the export bytes.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config import RunConfig, validate_document
from ..errors import InputError, SchemaViolation
from ..io.tables import clean_text, read_table, write_table
from ..normalize.identities import (
    REGISTRY_COLUMNS,
    register_compounds,
)
from ..normalize.identities import (
    RULE_VERSION as COMPOUND_RULE_VERSION,
)
from ..output import staged_output, write_table_atomic
from ..provenance import build_manifest, sha256_file, utc_now_iso, write_json
from ..structures import (
    CompoundRow,
    Issue,
    StructureInfo,
    bind_submissions,
    build_name_only_rows,
    build_structure_rows,
    check_issues,
    check_summary,
    check_table,
    collect_issues,
    read_registry,
    read_submission_log,
    register_structures,
    summarize,
    write_registry,
    write_structures_table,
)
from ..structures import toolkit_version as rdkit_version
from ..structures.chem import TOOLKIT
from ..structures.registry import RULE_VERSION as STRUCTURE_RULE_VERSION
from ..structures.submissions import RULE_VERSION as BINDING_RULE_VERSION
from .ingest import registry_path

TABLE_NAME = "compound_structures.tsv"
AUDIT_NAME = "compounds_audit.json"
MANIFEST_NAME = "run_manifest.json"

Summary = dict[str, int]


def _run_id(config: RunConfig, override: str | None, now: str) -> str:
    if override:
        base = override
    else:
        stamp = now.replace("-", "").replace(":", "")
        base = f"{stamp}_{config.sha256[:8]}"
    return f"{base}_compounds"


def structure_registry_path(config: RunConfig) -> Path:
    """Return the path of the persistent structure registry of this run."""
    if "structure_registry" in config.data["inputs"]:
        return config.input_path("structure_registry")
    return config.output_dir / "registry" / "structure_registry.tsv"


def _reject_structure_inputs(config: RunConfig) -> None:
    details = [
        f"inputs.{key} is only used in structure mode: remove it or add a smiles column"
        for key in ("submission_log", "structure_registry")
        if key in config.data["inputs"]
    ]
    if details:
        raise InputError(
            "the compound table has no smiles column, so the stage runs in name-only mode",
            details=details,
        )


def _check_duplicate_ids(records: list[Any]) -> None:
    seen: dict[str, list[int]] = {}
    for number, record in enumerate(records, start=1):
        seen.setdefault(record.compound_id, []).append(number)
    problems = [
        f"{compound_id}: rows {', '.join(str(row) for row in rows)}"
        for compound_id, rows in sorted(seen.items())
        if len(rows) > 1
    ]
    if problems:
        raise InputError(
            "the identity registry gave one compound_id to more than one row",
            details=problems,
        )


def _compound_rows(raw_rows: list[dict[str, str]], records: list[Any]) -> list[CompoundRow]:
    return [
        CompoundRow(
            row=number,
            compound_id=record.compound_id,
            group=record.group,
            name=record.name,
            stp_file=record.stp_file,
            smiles=raw.get("smiles", ""),
            pubchem_cid=clean_text(raw.get("pubchem_cid", "")),
        )
        for number, (raw, record) in enumerate(zip(raw_rows, records, strict=True), start=1)
    ]


def _stage_status(table: list[dict[str, str]]) -> str:
    return "partial" if any(row["row_status"] == "quarantined" for row in table) else "complete"


def _quarantine(table: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "compound_id": row["compound_id"],
            "issue_codes": [code for code in row["issue_codes"].split(";") if code],
        }
        for row in table
        if row["row_status"] == "quarantined"
    ]


def _self_check(
    table: list[dict[str, str]],
    compounds: list[CompoundRow],
    *,
    registry: list[dict[str, str]],
    issues: list[Issue],
    summary: Summary,
) -> None:
    errors = sum(1 for issue in issues if issue.level == "error")
    warnings = len(issues) - errors
    problems = [
        *check_table(table, registry, compounds),
        *check_issues(table, issues),
        *check_summary(summary, table, errors, warnings),
    ]
    if problems:
        raise SchemaViolation("the compounds stage is internally inconsistent", details=problems)

def _audit(
    config: RunConfig,
    *,
    identity_mode: str,
    compounds_path: Path,
    compound_rows: list[dict[str, str]],
    submission_log: Path | None,
    log_rows: int,
    stp_dir: Path | None,
    files_hashed: int,
    toolkit: dict[str, str] | None,
    structure_rule_version: str | None,
    binding_rule_version: str | None,
    summary: Summary,
    issues: list[Issue],
    compound_registry: Path,
    compound_registry_entries: int,
    structure_registry: Path | None,
    structure_registry_entries: int,
    notes: list[dict[str, str]],
    table_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_by": "rnp ingest compounds",
        "stage_status": "partial" if summary["rows_quarantined"] else "complete",
        "identity_mode": identity_mode,
        "config": {"path": str(config.path), "sha256": config.sha256},
        "inputs": {
            "compounds": {
                "path": str(compounds_path),
                "sha256": sha256_file(compounds_path),
                "rows": len(compound_rows),
            },
            "submission_log": (
                {
                    "path": str(submission_log),
                    "sha256": sha256_file(submission_log),
                    "rows": log_rows,
                }
                if submission_log is not None
                else None
            ),
            "stp_dir": (
                {"path": str(stp_dir), "files_hashed": files_hashed}
                if stp_dir is not None
                else None
            ),
        },
        "toolkit": toolkit,
        "rule_versions": {
            "compound_identity": COMPOUND_RULE_VERSION,
            "structure_identity": structure_rule_version,
            "submission_binding": binding_rule_version,
        },
        "summary": summary,
        "issues": [issue.as_dict() for issue in issues],
        "registries": {
            "compound_registry": {
                "path": str(compound_registry),
                "rule_version": COMPOUND_RULE_VERSION,
                "entries": compound_registry_entries,
            },
            "structure_registry": (
                {
                    "path": str(structure_registry),
                    "rule_version": STRUCTURE_RULE_VERSION,
                    "entries": structure_registry_entries,
                }
                if structure_registry is not None
                else None
            ),
        },
        "notes": notes,
        "compound_structures_sha256": table_sha256,
    }


def _write_compound_registry(path: Path, rows: list[dict[str, str]]) -> None:
    write_table_atomic(
        path,
        lambda temporary: write_table(temporary, rows, REGISTRY_COLUMNS),
    )

def run_compounds(
    config: RunConfig,
    *,
    run_id: str | None = None,
    force: bool = False,
    now: Callable[[], str] = utc_now_iso,
    describe: Callable[[str], StructureInfo] | None = None,
    toolkit_version: Callable[[], str] = rdkit_version,
) -> dict[str, Any]:
    """Run the compounds stage and return its summary."""
    compounds_path = config.input_path("compounds")
    raw_rows = read_table(compounds_path)
    if not raw_rows:
        raise InputError(f"{compounds_path.name}: compound table is empty")
    structure_mode = "smiles" in raw_rows[0]

    if not structure_mode:
        _reject_structure_inputs(config)

    compound_registry = registry_path(config)
    registry_file: Path | None = None
    registration = None
    if structure_mode:
        submission_log = (
            config.input_path("submission_log")
            if "submission_log" in config.data["inputs"]
            else None
        )
        if submission_log is not None:
            if not submission_log.is_file():
                raise InputError(f"inputs.submission_log is not a file: {submission_log}")
            stp_dir = config.input_path("stp_dir")
            if not stp_dir.is_dir():
                raise InputError(f"inputs.stp_dir is not a directory: {stp_dir}")
            log_rows = read_submission_log(submission_log)
        else:
            stp_dir = None
            log_rows = None
        registry_file = structure_registry_path(config)
        structure_registry = read_registry(registry_file)
    else:
        submission_log = None
        stp_dir = None
        log_rows = None
        structure_registry = []

    # Identity registration reads the table again but performs no writes; its notes are part of
    # the audit, and a duplicate identity is a table-level error before anything is staged.
    records, compound_registry_rows, notes = register_compounds(
        compounds_path,
        compound_registry,
        allow_filename_match=bool(config.data["inputs"].get("allow_filename_match", False)),
    )
    _check_duplicate_ids(records)
    compounds = _compound_rows(raw_rows, records)
    started_at = now()
    run = _run_id(config, run_id, started_at)
    run_dir = config.output_dir / run
    hashed: list[Path] = []

    if not structure_mode:
        table = build_name_only_rows(compounds)
        summary = summarize(table, None, [])
        issues: list[Issue] = []
        _self_check(table, compounds, registry=[], issues=issues, summary=summary)
        toolkit = None
        structure_rule = None
        binding_rule = None
        structure_entries = 0
    else:
        def counting_hasher(path: Path) -> str:
            hashed.append(path)
            return sha256_file(path)

        # Structure mode needs the toolkit even when every structure is already registered: the
        # audit records the version of this run, not whatever the registry was written with.
        version = toolkit_version()
        registration = register_structures(
            compounds,
            structure_registry,
            toolkit_version=version,
            now=started_at,
            describe=describe,
        )
        binding = bind_submissions(
            compounds,
            registration.outcomes,
            log_rows,
            stp_dir=stp_dir,
            species=config.data["species"],
            hasher=counting_hasher,
        )
        table = build_structure_rows(compounds, registration, binding)
        issues = collect_issues(registration, binding)
        summary = summarize(table, registration, issues)
        _self_check(
            table,
            compounds,
            registry=registration.registry,
            issues=issues,
            summary=summary,
        )
        toolkit = {"name": TOOLKIT, "version": version}
        structure_rule = STRUCTURE_RULE_VERSION
        binding_rule = BINDING_RULE_VERSION if log_rows is not None else None
        structure_entries = len(registration.registry)

    stage_status = _stage_status(table)

    with staged_output(run_dir, force=force) as work:
        write_structures_table(work / TABLE_NAME, table)
        table_sha = sha256_file(work / TABLE_NAME)
        audit = _audit(
            config,
            identity_mode="structure" if structure_mode else "name_only",
            compounds_path=compounds_path,
            compound_rows=raw_rows,
            submission_log=submission_log,
            log_rows=len(log_rows or []),
            stp_dir=stp_dir,
            files_hashed=len(hashed),
            toolkit=toolkit,
            structure_rule_version=structure_rule,
            binding_rule_version=binding_rule,
            summary=summary,
            issues=issues,
            compound_registry=compound_registry,
            compound_registry_entries=len(compound_registry_rows),
            structure_registry=registry_file,
            structure_registry_entries=structure_entries,
            notes=notes,
            table_sha256=table_sha,
        )
        validate_document(audit, "compounds_audit", "compounds audit")
        write_json(work / AUDIT_NAME, audit)

        manifest = build_manifest(
            run_id=run,
            command="ingest compounds",
            args={
                "config": str(config.path),
                "identity_mode": "structure" if structure_mode else "name_only",
                "species": config.data["species"],
                "allow_filename_match": bool(
                    config.data["inputs"].get("allow_filename_match", False)
                ),
                "submission_log": str(submission_log) if submission_log is not None else None,
            },
            config=config,
            inputs=[
                config.path,
                compounds_path,
                *([submission_log] if submission_log is not None else []),
                *hashed,
            ],
            parents=[],
            started_at=started_at,
            finished_at=now(),
            exit_code=0 if stage_status == "complete" else 3,
            stage_status=stage_status,
            overwritten=force,
        )
        validate_document(manifest, "run_manifest", "run manifest")
        write_json(work / MANIFEST_NAME, manifest)

    _write_compound_registry(compound_registry, compound_registry_rows)
    if registration is not None and registry_file is not None:
        # Registration itself has already produced the complete registry (including rows that
        # were reused); write it only after the staged output is in place.
        write_registry(registry_file, registration.registry)

    return {
        "status": "ok" if stage_status == "complete" else "partial",
        "stage_status": stage_status,
        "identity_mode": "structure" if structure_mode else "name_only",
        "run_id": run,
        "run_dir": str(run_dir),
        "summary": summary,
        "quarantine": _quarantine(table),
    }
