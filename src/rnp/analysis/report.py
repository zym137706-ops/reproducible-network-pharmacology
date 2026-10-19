"""Markdown report assembled from the audited stage artifacts.

The report never re-computes science. It reads the stage audits, verifies the
recorded hashes, and renders only what the audits and tables support. Missing
stages are reported as "not run"; incomplete stages require an explicit override.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .. import __version__
from ..config import RunConfig, validate_document
from ..errors import InputError
from ..io.tables import read_table
from ..output import staged_output
from ..provenance import build_manifest, sha256_file, utc_now_iso, write_json
from .parents import parent_record

STAGE_SCHEMAS = {
    "ingest": "stp_audit",
    "intersect": "intersection",
    "network": "network",
    "enrichment": "enrichment",
}
STAGE_ORDER = ("ingest", "intersect", "network", "enrichment")
INCOMPLETE = {"partial", "partial_override"}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise InputError(f"required artifact not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read {path.name}: {exc}") from exc


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _count_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    return max(len(lines) - 1, 0)


def _stage_paths(run_dir: Path) -> dict[str, dict[str, Path]]:
    return {
        "ingest": {
            "dir": run_dir,
            "audit": run_dir / "stp_audit.json",
            "manifest": run_dir / "run_manifest.json",
        },
        "intersect": {
            "dir": run_dir / "intersect",
            "audit": run_dir / "intersect" / "intersect_audit.json",
            "manifest": run_dir / "intersect" / "run_manifest.json",
        },
        "network": {
            "dir": run_dir / "network",
            "audit": run_dir / "network" / "network_audit.json",
            "manifest": run_dir / "network" / "run_manifest.json",
        },
        "enrichment": {
            "dir": run_dir / "enrichment",
            "audit": run_dir / "enrichment" / "enrichment_audit.json",
            "manifest": run_dir / "enrichment" / "run_manifest.json",
        },
    }


def _verify_artifact(path: Path, expected: str | None, role: str) -> dict[str, str]:
    if not path.is_file():
        raise InputError(f"artifact not found: {path}")
    if not expected:
        raise InputError(f"no recorded hash for {role}: {path.name}")
    actual = sha256_file(path)
    if actual != expected:
        raise InputError(f"artifact changed since upstream stage: {path.name}")
    return {"role": role, "path": str(path), "sha256": actual}


def _verify_ingest(run_dir: Path, audit: dict[str, Any]) -> list[dict[str, str]]:
    return [
        _verify_artifact(run_dir / "targets.tsv", audit["targets_sha256"], "targets"),
        _verify_artifact(
            run_dir / "compounds_registered.tsv",
            audit["compounds_registered_sha256"],
            "compounds",
        ),
    ]


def _verify_intersect(run_dir: Path, audit: dict[str, Any]) -> list[dict[str, str]]:
    intersect_dir = run_dir / "intersect"
    artifacts = []
    for field, name, role in (
        ("edges_sha256", "edges.tsv", "edges"),
        ("intersection_sha256", "intersection_genes.tsv", "intersection"),
        ("disease_sha256", "disease_genes.tsv", "disease"),
        ("exclusions_sha256", "target_exclusions.tsv", "exclusions"),
        ("conflicts_sha256", "gene_mapping_conflicts.tsv", "conflicts"),
        ("venn_sha256", "venn.json", "venn"),
    ):
        artifacts.append(
            _verify_artifact(intersect_dir / name, audit["outputs"].get(field), role)
        )
    return artifacts


def _verify_network(run_dir: Path, audit: dict[str, Any]) -> None:
    intersect_dir = run_dir / "intersect"
    for field, name in (
        ("edges_sha256", "edges.tsv"),
        ("intersection_sha256", "intersection_genes.tsv"),
        ("disease_sha256", "disease_genes.tsv"),
    ):
        path = intersect_dir / name
        if not path.is_file() or sha256_file(path) != audit["inputs"][field]:
            raise InputError(f"artifact changed since network: {path.name}")
    compounds = run_dir / "compounds_registered.tsv"
    if sha256_file(compounds) != audit["inputs"]["compounds_sha256"]:
        raise InputError("artifact changed since network: compounds_registered.tsv")


def _verify_enrichment(run_dir: Path, audit: dict[str, Any]) -> list[dict[str, str]]:
    intersect_dir = run_dir / "intersect"
    artifacts = []
    for field, path in (
        ("intersection_sha256", intersect_dir / "intersection_genes.tsv"),
        ("disease_sha256", intersect_dir / "disease_genes.tsv"),
        ("universe_sha256", Path(audit["inputs"]["universe_file"])),
    ):
        if not path.is_file() or sha256_file(path) != audit["inputs"][field]:
            raise InputError(f"artifact changed since enrichment: {path.name}")
    artifacts.append(
        _verify_artifact(
            Path(audit["inputs"]["universe_file"]),
            audit["inputs"]["universe_sha256"],
            "universe",
        )
    )
    for group, entry in (audit.get("groups") or {}).items():
        group_dir = run_dir / "enrichment" / _safe_group(group)
        for role, filename, field in (
            ("enrichment_result", "enrichment_result.tsv", "result_sha256"),
            ("enrichment_meta", "enrichment_meta.json", "meta_sha256"),
            ("enrichment_significant", "enrichment_significant.tsv", "significant_sha256"),
        ):
            artifacts.append(
                _verify_artifact(group_dir / filename, entry.get(field), f"{role}:{group}")
            )
    return artifacts


def _verify_parent_links(
    stages: dict[str, dict[str, Any]], paths: dict[str, dict[str, Path]]
) -> None:
    expected_parent = {
        "intersect": "ingest",
        "network": "intersect",
        "enrichment": "intersect",
    }
    ingest_parents = (stages.get("ingest", {}).get("audit") or {}).get("parents") or []
    if ingest_parents:
        raise InputError("ingest audit unexpectedly declares a parent stage")
    for stage, parent in expected_parent.items():
        if stage not in stages:
            continue
        if parent not in stages:
            raise InputError(
                f"{stage} references parent {parent!r}, but that audit is missing"
            )
        parents = (stages[stage]["audit"].get("parents") or [])
        entry = next((item for item in parents if item.get("stage") == parent), None)
        if entry is None:
            raise InputError(f"{stage} audit has no parent record for {parent!r}")
        parent_audit = paths[parent]["audit"]
        actual = sha256_file(parent_audit)
        if entry.get("audit_sha256") != actual:
            raise InputError(
                f"{stage} parent link is stale: {parent} audit hash mismatch"
            )
        if entry.get("stage_status") != stages[parent]["status"]:
            raise InputError(
                f"{stage} parent link records {entry.get('stage_status')!r}, "
                f"but {parent} is {stages[parent]['status']!r}"
            )
        if entry.get("dir") != str(paths[parent]["dir"]):
            raise InputError(f"{stage} parent link points at an unexpected directory")


def _safe_group(group: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", group).strip("_") or "group"


def _top_terms(run_dir: Path, groups: list[str], limit: int = 10) -> list[list[str]]:
    rows: list[dict[str, str]] = []
    for group in groups:
        path = run_dir / "enrichment" / _safe_group(group) / "enrichment_significant.tsv"
        if not path.is_file():
            continue
        for row in read_table(path):
            rows.append({"group": group, **row})

    def key(row: dict[str, str]) -> float:
        try:
            return float(row.get("p.adjust", "1"))
        except (TypeError, ValueError):
            return 1.0

    rows.sort(key=key)
    result = []
    for row in rows[:limit]:
        result.append(
            [
                row.get("group", ""),
                row.get("ID", ""),
                row.get("Description", ""),
                row.get("p.adjust", ""),
                row.get("Count", ""),
            ]
        )
    return result


def run_report(
    config: RunConfig,
    run_dir: str | Path,
    out_dir: str | Path,
    *,
    allow_partial: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Render a Markdown report from a run directory's audited stages."""
    run_dir = Path(run_dir).resolve()
    out_dir = Path(out_dir).resolve()
    started_at = utc_now_iso()
    paths = _stage_paths(run_dir)
    if not paths["ingest"]["audit"].is_file():
        raise InputError(
            f"not an rnp run directory (missing stp_audit.json): {run_dir}",
            details=["run 'rnp ingest stp' first, or pass the results/<run-id> directory"],
        )

    stages: dict[str, dict[str, Any]] = {}
    artifacts: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for stage in STAGE_ORDER:
        audit_path = paths[stage]["audit"]
        if not audit_path.is_file():
            continue
        audit = _load_json(audit_path)
        validate_document(audit, STAGE_SCHEMAS[stage], f"{stage} audit")
        recorded_config = (audit.get("config") or {}).get("sha256")
        if recorded_config != config.sha256:
            raise InputError(
                f"{stage} audit was produced from a different config",
                details=["re-run the pipeline instead of mixing configurations"],
            )
        stages[stage] = {
            "audit_path": audit_path,
            "audit": audit,
            "status": str(audit.get("stage_status", "unknown")),
        }
        if stage == "ingest":
            artifacts.extend(_verify_ingest(run_dir, audit))
        elif stage == "intersect":
            artifacts.extend(_verify_intersect(run_dir, audit))
        elif stage == "network":
            _verify_network(run_dir, audit)
        elif stage == "enrichment":
            artifacts.extend(_verify_enrichment(run_dir, audit))

    _verify_parent_links(stages, paths)

    incomplete = {
        stage: entry["status"]
        for stage, entry in stages.items()
        if entry["status"] in INCOMPLETE
    }
    if incomplete and not allow_partial:
        raise InputError(
            "run contains incomplete stages; report would be summarised as partial",
            details=[
                *(
                    f"{stage}: {status}" for stage, status in sorted(incomplete.items())
                ),
                "fix/re-run the stages, or pass --allow-partial to render a partial report",
            ],
        )
    if incomplete:
        warnings.append(
            {
                "code": "partial_stages",
                "message": (
                    "partial stages included by explicit override: "
                    + ", ".join(f"{stage}={status}" for stage, status in sorted(incomplete.items()))
                ),
            }
        )

    intersect_audit = stages.get("intersect", {}).get("audit")
    groups: list[str] = []
    if intersect_audit:
        groups = sorted(intersect_audit.get("groups", {}))
    empty_result = False
    if intersect_audit and groups:
        empty_result = all(
            intersect_audit["groups"][group].get("intersection", 0) == 0
            for group in groups
        )
    stage_status = "partial_override" if incomplete else ("empty" if empty_result else "complete")

    ingest_audit = stages.get("ingest", {}).get("audit", {})
    network_audit = stages.get("network", {}).get("audit")
    enrichment_audit = stages.get("enrichment", {}).get("audit")

    lines: list[str] = []
    lines.append(f"# {config.project} — network-pharmacology analysis report")
    lines.append("")
    lines.append(
        "> Generated by `rnp report` from the audited stage artifacts of this run. "
        "The report describes **predicted** compound–target associations and "
        "**annotation overlap**; it is not experimental validation and does not establish "
        "mechanism, direction of effect, or efficacy."
    )
    lines.append("")
    lines.append(f"- Run directory: `{run_dir.name}`")
    lines.append(f"- Config: `{config.path}` (sha256 `{config.sha256[:12]}…`)")
    lines.append(f"- Generator: rnp {__version__}")
    if warnings:
        lines.append(f"- Warnings: {len(warnings)} (see §7)")
    lines.append("")

    lines.append("## 1. Run status")
    lines.append("")
    status_rows = []
    for stage in STAGE_ORDER:
        if stage in stages:
            status_rows.append(
                [
                    stage,
                    stages[stage]["status"],
                    f"`{stages[stage]['audit_path'].name}`",
                ]
            )
        else:
            status_rows.append([stage, "not run", "—"])
    lines.append(_table(["Stage", "Status", "Audit"], status_rows))
    lines.append("")

    lines.append("## 2. Inputs and analysis parameters")
    lines.append("")
    ingest_summary = ingest_audit.get("summary", {})
    lines.append(f"- Compounds registered: {ingest_summary.get('compounds_registered', 'n/a')}")
    lines.append(
        "- STP exports: bound {bound}, quarantined {quarantined}, missing {missing}".format(
            bound=ingest_summary.get("files_bound", "n/a"),
            quarantined=ingest_summary.get("files_quarantined", "n/a"),
            missing=ingest_summary.get("files_missing", "n/a"),
        )
    )
    lines.append(
        "- Rows: total {total}, valid {valid}, used at threshold {used}, "
        "below threshold {below}, invalid {invalid}".format(
            total=ingest_summary.get("rows_total", "n/a"),
            valid=ingest_summary.get("rows_valid", "n/a"),
            used=ingest_summary.get("rows_used", "n/a"),
            below=ingest_summary.get("rows_below_threshold", "n/a"),
            invalid=ingest_summary.get("rows_invalid", "n/a"),
        )
    )
    thresholds = ingest_audit.get("thresholds", {})
    lines.append(f"- Probability threshold: {thresholds.get('stp_probability', 'n/a')}")
    if intersect_audit:
        first_group = intersect_audit.get("groups", {}).get(groups[0], {}) if groups else {}
        lines.append(
            f"- Disease label: {intersect_audit.get('disease_label')!r}; "
            f"genes: {first_group.get('disease', 'n/a')}"
        )
    lines.append("")

    lines.append("## 3. Compound–target–disease intersection")
    lines.append("")
    if intersect_audit and groups:
        rows = []
        for group in groups:
            entry = intersect_audit["groups"][group]
            rows.append(
                [
                    group,
                    entry.get("compounds", 0),
                    entry.get("edges", 0),
                    entry.get("targets", 0),
                    entry.get("disease", 0),
                    entry.get("intersection", 0),
                    entry.get("target_only", 0),
                    entry.get("disease_only", 0),
                ]
            )
        lines.append(
            _table(
                [
                    "Group",
                    "Compounds",
                    "Edges",
                    "Targets",
                    "Disease genes",
                    "Intersection",
                    "Target only",
                    "Disease only",
                ],
                rows,
            )
        )
        exclusions = intersect_audit.get("exclusions", {})
        lines.append("")
        lines.append(
            "- Excluded rows: "
            + ", ".join(f"{reason}={count}" for reason, count in sorted(exclusions.items()))
        )
        conflicts = _count_rows(run_dir / "intersect" / "gene_mapping_conflicts.tsv")
        lines.append(f"- Unresolved/conflicting gene mappings: {conflicts}")
    else:
        lines.append("_Intersection stage not run._")
    lines.append("")

    lines.append("## 4. Network")
    lines.append("")
    if network_audit and network_audit.get("groups"):
        rows = []
        for group, entry in sorted(network_audit["groups"].items()):
            rows.append([group, entry.get("nodes", 0), entry.get("edges", 0)])
        lines.append(_table(["Group", "Nodes", "Edges"], rows))
        checks_ok = all(
            all(entry.get("checks", {}).values()) for entry in network_audit["groups"].values()
        )
        lines.append("")
        lines.append(f"- Invariant checks: {'all passed' if checks_ok else 'FAILED'}")
        lines.append(
            "- A network edge means: this compound was predicted to hit this target, and this "
            "target is annotated to this disease."
        )
    else:
        lines.append("_Network stage not run or produced no graph._")
    lines.append("")

    lines.append("## 5. Enrichment")
    lines.append("")
    if enrichment_audit and enrichment_audit.get("groups"):
        rows = []
        for group, entry in sorted(enrichment_audit["groups"].items()):
            rows.append(
                [
                    group,
                    entry.get("status", ""),
                    entry.get("foreground_mapped", "n/a"),
                    entry.get("foreground_unmapped", "n/a"),
                    entry.get("terms_tested", 0),
                    entry.get("significant", 0),
                ]
            )
        lines.append(
            _table(
                ["Group", "Status", "Mapped", "Unmapped", "Terms tested", "Significant"],
                rows,
            )
        )
        terms = _top_terms(run_dir, sorted(enrichment_audit["groups"]))
        if terms:
            lines.append("")
            lines.append("Top significant terms (filtered view; the complete table is in the run):")
            lines.append("")
            lines.append(
                _table(["Group", "ID", "Description", "p.adjust", "Count"], terms)
            )
        else:
            lines.append("")
            lines.append("_No term passed the configured significance cutoffs._")
    else:
        lines.append("_Enrichment stage not run._")
    lines.append("")

    lines.append("## 6. Provenance")
    lines.append("")
    provenance_rows = []
    for stage in STAGE_ORDER:
        if stage not in stages:
            continue
        audit_path = stages[stage]["audit_path"]
        provenance_rows.append(
            [stage, f"`{audit_path.name}`", f"`{sha256_file(audit_path)}`"]
        )
    lines.append(_table(["Stage", "Audit", "SHA-256"], provenance_rows))
    if enrichment_audit:
        env = enrichment_audit.get("environment") or {}
        packages = env.get("packages") or {}
        lines.append("")
        lines.append(
            f"- R {env.get('r_version', 'n/a')}; "
            f"clusterProfiler {packages.get('clusterProfiler', 'n/a')}; "
            f"OrgDb {packages.get('orgdb', 'n/a')}"
        )
        universe = enrichment_audit.get("universe") or {}
        lines.append(
            f"- Background: explicit, input {universe.get('input', 'n/a')}, "
            f"mapped {universe.get('mapped', 'n/a')}, unmapped {universe.get('unmapped', 'n/a')}, "
            f"statistical {universe.get('statistical', 'n/a')}"
        )
    lines.append("")

    lines.append("## 7. Limitations")
    lines.append("")
    lines.append(
        "- Predicted associations are hypotheses; they are not validated mechanisms or efficacy."
    )
    lines.append(
        "- Results depend on the recorded threshold, gene-set release, identifier mapping and "
        "background; changing them changes the answer."
    )
    lines.append(
        "- Excluded and unresolved rows are listed in the intersect audit; they are never guessed."
    )
    for warning in warnings:
        lines.append(f"- {warning['message']}.")
    lines.append("")

    lines.append("## 8. Files")
    lines.append("")
    lines.append(f"- Config: `{config.path}`")
    lines.append(f"- Ingest audit: `{paths['ingest']['audit']}`")
    for stage in ("intersect", "network", "enrichment"):
        if stage in stages:
            lines.append(f"- {stage.capitalize()} audit: `{paths[stage]['audit']}`")
    lines.append("- Tables: see the stage directories next to this report.")
    lines.append("")

    markdown = "\n".join(lines)
    report_bytes = markdown.encode("utf-8")

    parents = [
        parent_record(
            stage=stage,
            directory=paths[stage]["dir"],
            audit_path=paths[stage]["audit"],
            stage_status=stages[stage]["status"],
            override=stages[stage]["status"] in INCOMPLETE,
        )
        for stage in STAGE_ORDER
        if stage in stages
    ]
    inputs = [config.path]
    for stage in STAGE_ORDER:
        if stage in stages:
            inputs.append(paths[stage]["audit"])
            if paths[stage]["manifest"].is_file():
                inputs.append(paths[stage]["manifest"])

    with staged_output(out_dir, force=force) as work:
        (work / "report.md").write_bytes(report_bytes)
        report_sha = sha256_file(work / "report.md")
        audit = {
            "schema_version": "1.0",
            "generated_by": "rnp report",
            "stage_status": stage_status,
            "run_dir": str(run_dir),
            "config": {"path": str(config.path), "sha256": config.sha256},
            "stages": {
                stage: {
                    "status": stages[stage]["status"],
                    "audit": paths[stage]["audit"].name,
                    "audit_sha256": sha256_file(paths[stage]["audit"]),
                    "manifest_sha256": sha256_file(paths[stage]["manifest"])
                    if paths[stage]["manifest"].is_file()
                    else None,
                }
                for stage in STAGE_ORDER
                if stage in stages
            },
            "groups": groups,
            "artifacts": artifacts,
            "warnings": warnings,
            "report_sha256": report_sha,
        }
        validate_document(audit, "report", "report audit")
        write_json(work / "report_audit.json", audit)

        manifest = build_manifest(
            run_id=out_dir.name,
            command="report",
            args={
                "config": str(config.path),
                "run_dir": str(run_dir),
                "out": str(out_dir),
                "allow_partial": allow_partial,
            },
            config=config,
            inputs=inputs,
            parents=parents,
            started_at=started_at,
            finished_at=utc_now_iso(),
            exit_code=0,
            stage_status=stage_status,
            overwritten=force,
        )
        validate_document(manifest, "run_manifest", "run manifest")
        write_json(work / "run_manifest.json", manifest)

    return {
        "status": "ok",
        "stage_status": stage_status,
        "out_dir": str(out_dir),
        "report": str(out_dir / "report.md"),
        "report_sha256": report_sha,
        "stages": {stage: stages[stage]["status"] for stage in stages},
        "warnings": len(warnings),
    }
