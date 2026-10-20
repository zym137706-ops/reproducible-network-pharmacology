"""ORA enrichment stage (R clusterProfiler bridge).

The complete tested-term table is always written; significance is a *filter view*
on top of it. A failed analysis, an unmappable explicit background and a valid
zero-significant result are three different outcomes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..config import RunConfig, validate_document
from ..errors import ExternalToolError, InputError
from ..io.tables import clean_text, read_table, write_table
from ..output import staged_output
from ..provenance import build_manifest, sha256_file, utc_now_iso, write_json
from ..resources import r_script
from .parents import (
    check_config_identity,
    load_parent_audit,
    parent_record,
    require_file,
    verify_sha256,
)

RESULT_COLUMNS = (
    "ID",
    "Description",
    "GeneRatio",
    "BgRatio",
    "pvalue",
    "p.adjust",
    "qvalue",
    "geneID",
    "Count",
)
SERVICE_STATUSES = {"kegg_unavailable", "analysis_failed"}


def _resolve_rscript(override: str | None) -> str | None:
    return override or os.environ.get("RNP_RSCRIPT") or shutil.which("Rscript")


def _invoke_ora(
    rscript_path: str,
    ora_script: Path,
    request_path: Path,
    group_dir: Path,
    *,
    group: str,
) -> subprocess.CompletedProcess[str]:
    """Run the R bridge and make the process status authoritative.

    The R script may have written a normal-looking ``enrichment_meta.json`` and
    result table before dying (native crash, kill, wrapper failure). A non-zero
    status is therefore propagated as a failure regardless of those files.
    """
    try:
        completed = subprocess.run(
            [rscript_path, str(ora_script), str(request_path), str(group_dir)],
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExternalToolError(
            f"R enrichment timed out for group {group!r}",
            details=["the staged output directory was discarded", "rerun after checking R"],
        ) from exc
    except OSError as exc:
        raise ExternalToolError(
            f"could not start Rscript for group {group!r}: {exc}",
            details=[f"Rscript: {rscript_path}"],
        ) from exc

    meta_path = group_dir / "enrichment_meta.json"
    meta_status: str | None = None
    if meta_path.is_file():
        try:
            meta_status = json.loads(meta_path.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            meta_status = "<unreadable meta>"

    if completed.returncode != 0:
        details = [
            f"R exit code: {completed.returncode}",
            f"R meta status: {meta_status or '<no meta written>'}",
            completed.stderr.strip()[-800:] or "no stderr",
        ]
        if completed.returncode == 2:
            raise InputError(
                f"enrichment input/background error for group {group!r}",
                details=details,
            )
        raise ExternalToolError(
            f"R enrichment process failed for group {group!r}",
            details=details,
        )
    if meta_status is None:
        raise ExternalToolError(
            f"R exited 0 but wrote no enrichment_meta.json for group {group!r}",
            details=[completed.stderr.strip()[-800:] or "no stderr"],
        )
    return completed


def _read_gene_list(path: Path) -> list[str]:
    genes: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        gene = clean_text(line)
        if not gene or gene.startswith("#") or gene in seen:
            continue
        seen.add(gene)
        genes.append(gene)
    return genes


def _safe_group(group: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_-]+", "_", group).strip("_") or "group"


def _significant(row: dict[str, str], pvalue_cutoff: float, qvalue_cutoff: float) -> bool:
    try:
        if float(row["p.adjust"]) > pvalue_cutoff:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    raw_q = row.get("qvalue", "")
    if raw_q not in (None, ""):
        try:
            if float(raw_q) > qvalue_cutoff:
                return False
        except (TypeError, ValueError):
            return False
    return True


def run_enrich(
    config: RunConfig,
    intersect_dir: str | Path,
    out_dir: str | Path,
    *,
    allow_partial: bool = False,
    force: bool = False,
    rscript: str | None = None,
) -> dict[str, Any]:
    """Run ORA on each intersection group with an explicit background."""
    intersect_dir = Path(intersect_dir).resolve()
    out_dir = Path(out_dir).resolve()
    started_at = utc_now_iso()

    enrichment_cfg = config.data["enrichment"]
    universe_file_cfg = enrichment_cfg.get("universe_file")
    if not universe_file_cfg:
        raise InputError(
            "config is missing enrichment.universe_file",
            details=[
                "an explicit background is required for enrichment;",
                "add enrichment.universe_file to run.yaml (one gene per line)",
            ],
        )
    universe_file = config.resolve(universe_file_cfg)
    require_file(universe_file, "enrichment universe file")
    universe_genes = _read_gene_list(universe_file)
    if not universe_genes:
        raise InputError(f"enrichment universe file is empty: {universe_file}")

    audit_path = intersect_dir / "intersect_audit.json"
    parent_audit, override = load_parent_audit(
        audit_path, "intersection", stage_name="intersect", allow_partial=allow_partial
    )
    check_config_identity(parent_audit, config, "intersect")
    outputs = parent_audit.get("outputs") or {}
    intersection_path = intersect_dir / "intersection_genes.tsv"
    disease_path = intersect_dir / "disease_genes.tsv"
    verify_sha256(
        intersection_path, outputs.get("intersection_sha256"), "intersection_genes.tsv"
    )
    verify_sha256(disease_path, outputs.get("disease_sha256"), "disease_genes.tsv")

    rows = read_table(intersection_path)
    groups: dict[str, list[str]] = {}
    for row in rows:
        group = clean_text(row.get("group")) or "all"
        gene = clean_text(row.get("gene"))
        if gene:
            groups.setdefault(group, []).append(gene)
    groups = {group: sorted(set(genes)) for group, genes in groups.items()}

    rscript_path = _resolve_rscript(rscript)
    parents = [
        parent_record(
            stage="intersect",
            directory=intersect_dir,
            audit_path=audit_path,
            stage_status=str(parent_audit.get("stage_status")),
            override=override,
        )
    ]
    warnings: list[dict[str, str]] = []
    if override:
        warnings.append(
            {
                "code": "upstream_status_override",
                "message": (
                    f"intersect stage_status={parent_audit.get('stage_status')!r}; "
                    "enrichment is explicitly partial"
                ),
            }
        )

    params = {
        "gene_sets": enrichment_cfg["gene_sets"],
        "p_adjust": enrichment_cfg.get("p_adjust", "BH"),
        "pvalue_cutoff": float(enrichment_cfg.get("pvalue_cutoff", 0.05)),
        "qvalue_cutoff": float(enrichment_cfg.get("qvalue_cutoff", 0.2)),
        "min_gssize": int(enrichment_cfg.get("min_gssize", 10)),
        "max_gssize": int(enrichment_cfg.get("max_gssize", 500)),
    }

    if not groups:
        stage_status = "empty"
        with staged_output(out_dir, force=force) as work:
            audit = {
                "schema_version": "1.0",
                "generated_by": "rnp enrich",
                "stage_status": "empty",
                "config": {"path": str(config.path), "sha256": config.sha256},
                "inputs": {
                    "intersect_dir": str(intersect_dir),
                    "intersection_sha256": sha256_file(intersection_path),
                    "disease_sha256": sha256_file(disease_path),
                    "universe_file": str(universe_file),
                    "universe_sha256": sha256_file(universe_file),
                },
                "parents": parents,
                "universe": {
                    "source": "explicit",
                    "input": len(universe_genes),
                    "mapped": None,
                    "unmapped": None,
                    "statistical": None,
                },
                "groups": {},
                "warnings": warnings
                + [
                    {
                        "code": "no_foreground_genes",
                        "message": "intersection has no genes; nothing to enrich",
                    }
                ],
                "environment": {},
            }
            validate_document(audit, "enrichment", "enrichment audit")
            write_json(work / "enrichment_audit.json", audit)
            manifest = build_manifest(
                run_id=out_dir.name,
                command="enrich",
                args={
                    "config": str(config.path),
                    "intersect_dir": str(intersect_dir),
                    "out": str(out_dir),
                },
                config=config,
                inputs=[config.path, intersection_path, disease_path, universe_file],
                parents=parents,
                started_at=started_at,
                finished_at=utc_now_iso(),
                exit_code=0,
                stage_status="empty",
                overwritten=force,
            )
            validate_document(manifest, "run_manifest", "run manifest")
            write_json(work / "run_manifest.json", manifest)
        return {
            "status": "empty",
            "stage_status": "empty",
            "out_dir": str(out_dir),
            "groups": {},
        }

    if rscript_path is None:
        raise InputError(
            "Rscript is required for enrichment but was not found",
            details=[
                "install R with clusterProfiler and the OrgDb annotation package,",
                "or pass --rscript / set RNP_RSCRIPT",
            ],
        )
    if not Path(rscript_path).is_file() and shutil.which(rscript_path) is None:
        raise InputError(f"Rscript not found: {rscript_path}")
    ora_script = r_script("ora.R")
    if not ora_script.is_file():
        raise InputError(f"packaged R/ora.R not found: {ora_script}")

    group_audits: dict[str, Any] = {}
    environment: dict[str, Any] = {}
    universe_summary: dict[str, Any] = {
        "source": "explicit",
        "input": len(universe_genes),
        "mapped": None,
        "unmapped": None,
        "statistical": None,
    }
    service_failure = False

    with staged_output(out_dir, force=force) as work:
        for group, genes in groups.items():
            group_dir = work / _safe_group(group)
            group_dir.mkdir(parents=True, exist_ok=True)
            request = {
                "genes": genes,
                "gene_id_type": "SYMBOL",
                "species": config.species,
                "gene_sets": params["gene_sets"],
                "p_adjust": params["p_adjust"],
                "pvalue_cutoff": params["pvalue_cutoff"],
                "qvalue_cutoff": params["qvalue_cutoff"],
                "min_gssize": params["min_gssize"],
                "max_gssize": params["max_gssize"],
                "universe": universe_genes,
                "output_dir": str(group_dir),
            }
            request_path = group_dir / "request.json"
            write_json(request_path, request)
            completed = _invoke_ora(
                rscript_path,
                ora_script,
                request_path,
                group_dir,
                group=group,
            )
            result_path = group_dir / "enrichment_result.tsv"
            meta_path = group_dir / "enrichment_meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            status = meta.get("status", "analysis_failed")
            if universe_summary["mapped"] is None:
                universe_meta = meta.get("universe") or {}
                universe_summary["mapped"] = universe_meta.get("mapped")
                universe_summary["unmapped"] = universe_meta.get("unmapped")
                universe_summary["statistical"] = universe_meta.get("statistical")
                environment = meta.get("environment") or {}
            if status == "background_mapping_failed":
                raise InputError(
                    "explicit background could not be mapped",
                    details=[f"universe file: {universe_file}"],
                )
            if not result_path.is_file():
                result_rows: list[dict[str, str]] = []
            else:
                result_rows = read_table(result_path)
                if result_rows:
                    missing = [column for column in RESULT_COLUMNS if column not in result_rows[0]]
                    if missing:
                        raise InputError(
                            f"enrichment result table is missing columns: {', '.join(missing)}"
                        )
            significant = [
                row
                for row in result_rows
                if _significant(row, params["pvalue_cutoff"], params["qvalue_cutoff"])
            ]
            if result_rows:
                write_table(
                    group_dir / "enrichment_significant.tsv", significant, list(RESULT_COLUMNS)
                )
            else:
                write_table(group_dir / "enrichment_significant.tsv", [], list(RESULT_COLUMNS))

            if status == "ok":
                group_status = "ok" if significant else "completed_no_significant_terms"
            elif status == "no_mapped_genes":
                group_status = "no_mapped_foreground"
            elif status == "no_ontology_annotation":
                group_status = "no_ontology_annotation"
            elif status in SERVICE_STATUSES:
                group_status = "service_unavailable"
                service_failure = True
                warnings.append(
                    {
                        "code": status,
                        "message": f"{group}: {completed.stderr.strip()[-500:] or status}",
                    }
                )
            else:
                group_status = "analysis_failed"
                service_failure = True
                warnings.append(
                    {
                        "code": f"unexpected_status_{status}",
                        "message": f"{group}: unexpected R status {status!r}",
                    }
                )
            counts = meta.get("counts") or {}
            effective = meta.get("effective") or {}
            foreground_set = group_dir / "effective_foreground.tsv"
            background_set = group_dir / "effective_background.tsv"
            group_audits[group] = {
                "status": group_status,
                "foreground_input": len(genes),
                "foreground_mapped": counts.get("mapped"),
                "foreground_unmapped": counts.get("unmapped"),
                "effective_foreground": effective.get("foreground"),
                "effective_background": effective.get("background"),
                "effective_foreground_sha256": sha256_file(foreground_set)
                if foreground_set.is_file()
                else None,
                "effective_background_sha256": sha256_file(background_set)
                if background_set.is_file()
                else None,
                "terms_tested": len(result_rows),
                "significant": len(significant),
                "result_sha256": sha256_file(result_path) if result_path.is_file() else None,
                "meta_sha256": sha256_file(meta_path),
                "significant_sha256": sha256_file(
                    group_dir / "enrichment_significant.tsv"
                ),
                "r_exit_code": completed.returncode,
            }

        stage_status = "partial_override" if override else "complete"
        if service_failure:
            stage_status = "partial"
        audit = {
            "schema_version": "1.0",
            "generated_by": "rnp enrich",
            "stage_status": stage_status,
            "config": {"path": str(config.path), "sha256": config.sha256},
            "inputs": {
                "intersect_dir": str(intersect_dir),
                "intersection_sha256": sha256_file(intersection_path),
                "disease_sha256": sha256_file(disease_path),
                "universe_file": str(universe_file),
                "universe_sha256": sha256_file(universe_file),
            },
            "parents": parents,
            "universe": universe_summary,
            "groups": group_audits,
            "warnings": warnings,
            "environment": environment,
        }
        validate_document(audit, "enrichment", "enrichment audit")
        write_json(work / "enrichment_audit.json", audit)
        manifest = build_manifest(
            run_id=out_dir.name,
            command="enrich",
            args={
                "config": str(config.path),
                "intersect_dir": str(intersect_dir),
                "out": str(out_dir),
                "params": params,
                "allow_partial": allow_partial,
            },
            config=config,
            inputs=[config.path, intersection_path, disease_path, universe_file],
            parents=parents,
            started_at=started_at,
            finished_at=utc_now_iso(),
            exit_code=3 if service_failure else 0,
            stage_status=stage_status,
            r_version=str(environment.get("r_version") or ""),
            overwritten=force,
        )
        validate_document(manifest, "run_manifest", "run manifest")
        write_json(work / "run_manifest.json", manifest)

    return {
        "status": "partial" if service_failure else "ok",
        "stage_status": stage_status,
        "out_dir": str(out_dir),
        "groups": group_audits,
        "universe": universe_summary,
    }
