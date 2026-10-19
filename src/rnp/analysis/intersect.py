"""Compound–target edges, HGNC normalization and disease intersection.

This stage never invents edges for exports that were not bound to a compound: the
ingest stage quarantines unbound files, and only rows carrying a ``compound_id``
reach this module. It also refuses to run on an incomplete upstream stage unless
the caller explicitly asks for an audited override.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..config import RunConfig, validate_document
from ..errors import InputError
from ..io.tables import clean_text, read_table, write_table
from ..normalize.hgnc import GeneMapper, MapResult, map_disease_genes
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

TARGET_COLUMNS = {
    "compound_id",
    "group",
    "submission_id",
    "source_file",
    "target",
    "common_name",
    "uniprot_id",
    "probability",
    "is_complex",
    "multi_symbol_common_name",
    "row_number",
}
COMPOUND_COLUMNS = {"compound_id", "group", "name"}
EXCLUSION_REASONS = (
    "composite_target",
    "multi_symbol_common_name",
    "unmapped_or_conflicting_gene",
)


def _truthy(value: Any) -> bool:
    return clean_text(value).casefold() in {"true", "1", "yes", "y"}


def _read_targets(path: Path) -> list[dict[str, Any]]:
    rows = read_table(path)
    if not rows:
        raise InputError(f"{path.name}: target table is empty")
    missing = TARGET_COLUMNS - set(rows[0])
    if missing:
        raise InputError(
            f"{path.name}: target table was not produced by the current ingest stage",
            details=[f"missing columns: {', '.join(sorted(missing))}"],
        )
    for row in rows:
        try:
            row["probability"] = float(row["probability"])
        except (TypeError, ValueError) as exc:
            raise InputError(
                f"{path.name}: non-numeric probability in row {row.get('row_number')}"
            ) from exc
    return rows


def _read_compounds(path: Path) -> dict[str, dict[str, str]]:
    rows = read_table(path)
    if not rows:
        raise InputError(f"{path.name}: no registered compounds")
    missing = COMPOUND_COLUMNS - set(rows[0])
    if missing:
        raise InputError(
            f"{path.name}: registered compound table is incomplete",
            details=[f"missing columns: {', '.join(sorted(missing))}"],
        )
    return {clean_text(row["compound_id"]): row for row in rows}


def _classify(row: dict[str, Any], mapper: GeneMapper) -> tuple[MapResult | None, str]:
    if _truthy(row.get("is_complex")):
        return None, "composite_target"
    if _truthy(row.get("multi_symbol_common_name")):
        return None, "multi_symbol_common_name"
    mapped = mapper.map(row.get("common_name", ""), row.get("uniprot_id", ""))
    if not mapped.gene_symbol or mapped.mapping_conflict:
        return mapped, "unmapped_or_conflicting_gene"
    return mapped, "selected"


def _rscript() -> str | None:
    return os.environ.get("RNP_RSCRIPT") or shutil.which("Rscript")


def _venn_script() -> Path:
    return r_script("venny.R")


def _plot_venn(
    venn_path: Path, out_dir: Path, groups: list[str], warnings: list[dict[str, str]]
) -> list[str]:
    produced: list[str] = []
    rscript = _rscript()
    script = _venn_script()
    if rscript is None or not script.is_file():
        warnings.append(
            {"code": "venn_plot_skipped", "message": "Rscript or R/venny.R not available"}
        )
        return produced
    for group in groups:
        completed = subprocess.run(
            [rscript, str(script), str(venn_path), str(out_dir), group],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if completed.returncode != 0:
            warnings.append(
                {
                    "code": "venn_plot_failed",
                    "message": f"{group}: {completed.stderr.strip()[:300]}",
                }
            )
            continue
        produced.extend(
            str(out_dir / name) for name in (f"venn_{group}.png", f"venn_{group}.pdf")
        )
    return produced


def run_intersect(
    config: RunConfig,
    targets_path: str | Path,
    out_dir: str | Path,
    *,
    venn_plot: bool = False,
    allow_partial: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Build audited compound–target edges and their intersection with disease genes."""
    targets_path = Path(targets_path).resolve()
    out_dir = Path(out_dir).resolve()
    parent_dir = targets_path.parent
    started_at = utc_now_iso()

    if "hgnc_map" not in config.data["inputs"]:
        raise InputError(
            "config is missing inputs.hgnc_map",
            details=["add the HGNC complete-set TSV path to run.yaml"],
        )
    hgnc_path = config.input_path("hgnc_map")
    disease_path = config.input_path("disease_genes")
    for path, description in (
        (hgnc_path, "HGNC mapping table"),
        (disease_path, "disease gene list"),
    ):
        require_file(path, description)

    audit_path = parent_dir / "stp_audit.json"
    parent_audit, override = load_parent_audit(
        audit_path,
        "stp_audit",
        stage_name="ingest",
        allow_partial=allow_partial,
    )
    check_config_identity(parent_audit, config, "ingest")
    verify_sha256(targets_path, parent_audit.get("targets_sha256"), "targets.tsv")

    compounds_path = parent_dir / "compounds_registered.tsv"
    require_file(compounds_path, "registered compound table")
    verify_sha256(
        compounds_path,
        parent_audit.get("compounds_registered_sha256"),
        "compounds_registered.tsv",
    )

    mapper = GeneMapper(hgnc_path)
    targets = _read_targets(targets_path)
    compounds = _read_compounds(compounds_path)
    disease_audit = map_disease_genes(disease_path, mapper)
    disease_genes = sorted({row["gene_symbol"] for row in disease_audit if row["gene_symbol"]})
    disease_set = set(disease_genes)

    warnings: list[dict[str, str]] = []
    if override:
        warnings.append(
            {
                "code": "upstream_status_override",
                "message": (
                    f"ingest stage_status={parent_audit.get('stage_status')!r}; "
                    "results are explicitly partial"
                ),
            }
        )

    exclusions = {reason: 0 for reason in EXCLUSION_REASONS}
    exclusion_rows: list[dict[str, Any]] = []
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in targets:
        compound_id = clean_text(row["compound_id"])
        registered = compounds.get(compound_id)
        if registered is None:
            raise InputError(
                f"target row references unregistered compound: {compound_id}",
                details=["targets.tsv and compounds_registered.tsv disagree"],
            )
        group = clean_text(row["group"]) or clean_text(registered.get("group")) or "all"
        mapped, reason = _classify(row, mapper)
        if reason != "selected":
            exclusions[reason] = exclusions.get(reason, 0) + 1
            exclusion_rows.append(
                {
                    "compound_id": compound_id,
                    "group": group,
                    "source_file": clean_text(row["source_file"]),
                    "row_number": row.get("row_number", ""),
                    "target": clean_text(row.get("target")),
                    "common_name": clean_text(row.get("common_name")),
                    "uniprot_id": clean_text(row.get("uniprot_id")),
                    "probability": f"{row['probability']:.10g}",
                    "reason": reason,
                    "mapping_status": mapped.mapping_status if mapped else "",
                    "mapping_conflict": mapped.mapping_conflict if mapped else "",
                    "ambiguous_symbols": mapped.ambiguous_symbols if mapped else "",
                }
            )
            continue
        assert mapped is not None
        key = (group, compound_id, mapped.gene_symbol)
        candidate = {
            "group": group,
            "compound_id": compound_id,
            "compound": clean_text(registered.get("name")),
            "submission_id": clean_text(row.get("submission_id")),
            "source_file": clean_text(row["source_file"]),
            "gene": mapped.gene_symbol,
            "hgnc_id": mapped.hgnc_id,
            "entrez_id": mapped.entrez_id,
            "probability": row["probability"],
            "target_raw": clean_text(row.get("target")),
            "common_name_raw": clean_text(row.get("common_name")),
            "uniprot_id": clean_text(row.get("uniprot_id")),
            "mapping_status": mapped.mapping_status,
        }
        if key not in selected or candidate["probability"] > selected[key]["probability"]:
            selected[key] = candidate

    edges = sorted(
        selected.values(),
        key=lambda edge: (edge["group"].casefold(), edge["compound"].casefold(), edge["gene"]),
    )
    groups = sorted(
        {edge["group"] for edge in edges} | {row["group"] for row in compounds.values()}
    )

    group_stats: dict[str, dict[str, Any]] = {}
    venn_groups: dict[str, dict[str, Any]] = {}
    intersection_rows: list[dict[str, Any]] = []
    for group in groups:
        group_edges = [edge for edge in edges if edge["group"] == group]
        group_compounds = [row for row in compounds.values() if row.get("group") == group]
        genes = sorted({edge["gene"] for edge in group_edges})
        intersection = sorted(set(genes) & disease_set)
        linked = sorted({edge["compound_id"] for edge in group_edges})
        per_gene: dict[str, list[float]] = {}
        for edge in group_edges:
            if edge["gene"] in intersection:
                per_gene.setdefault(edge["gene"], []).append(edge["probability"])
        for gene in intersection:
            probabilities = per_gene.get(gene, [])
            mapped_gene = next(edge for edge in group_edges if edge["gene"] == gene)
            intersection_rows.append(
                {
                    "group": group,
                    "gene": gene,
                    "hgnc_id": mapped_gene["hgnc_id"],
                    "entrez_id": mapped_gene["entrez_id"],
                    "n_compounds": len(probabilities),
                    "max_probability": f"{max(probabilities):.10g}" if probabilities else "",
                }
            )
        target_only = sorted(set(genes) - disease_set)
        disease_only = sorted(disease_set - set(genes))
        group_stats[group] = {
            "compounds": len(group_compounds),
            "compounds_linked": len(linked),
            "edges": len(group_edges),
            "targets": len(genes),
            "disease": len(disease_set),
            "intersection": len(intersection),
            "target_only": len(target_only),
            "disease_only": len(disease_only),
            "union": len(set(genes) | disease_set),
            "compounds_without_edges": sorted(
                row["name"] for row in group_compounds if row["compound_id"] not in linked
            ),
        }
        venn_groups[group] = {
            "targets": genes,
            "disease": disease_genes,
            "intersection": intersection,
            "target_only": target_only,
            "disease_only": disease_only,
            "counts": {
                "targets": len(genes),
                "disease": len(disease_set),
                "intersection": len(intersection),
                "target_only": len(target_only),
                "disease_only": len(disease_only),
                "union": len(set(genes) | disease_set),
            },
        }

    disease_label = (
        clean_text(config.data.get("network", {}).get("disease_label")) or config.project
    )
    disease_code = clean_text(config.data.get("network", {}).get("disease_code")) or "Disease"
    venn_payload = {
        "disease_label": disease_label,
        "disease_code": disease_code,
        "disease": disease_genes,
        "groups": venn_groups,
    }
    stage_status = "partial_override" if override else "complete"
    parents = [
        parent_record(
            stage="ingest",
            directory=parent_dir,
            audit_path=audit_path,
            stage_status=str(parent_audit.get("stage_status")),
            override=override,
        )
    ]

    with staged_output(out_dir, force=force) as work:
        write_table(
            work / "edges.tsv",
            edges,
            [
                "group",
                "compound_id",
                "compound",
                "submission_id",
                "source_file",
                "gene",
                "hgnc_id",
                "entrez_id",
                "probability",
                "target_raw",
                "common_name_raw",
                "uniprot_id",
                "mapping_status",
            ],
        )
        write_table(
            work / "intersection_genes.tsv",
            intersection_rows,
            ["group", "gene", "hgnc_id", "entrez_id", "n_compounds", "max_probability"],
        )
        write_table(
            work / "disease_genes.tsv",
            disease_audit,
            [
                "original_gene",
                "gene_symbol",
                "hgnc_id",
                "entrez_id",
                "mapping_status",
                "mapping_conflict",
                "ambiguous_symbols",
                "duplicate",
            ],
        )
        exclusion_columns = [
            "compound_id",
            "group",
            "source_file",
            "row_number",
            "target",
            "common_name",
            "uniprot_id",
            "probability",
            "reason",
            "mapping_status",
            "mapping_conflict",
            "ambiguous_symbols",
        ]
        write_table(work / "target_exclusions.tsv", exclusion_rows, exclusion_columns)
        write_table(
            work / "gene_mapping_conflicts.tsv",
            [row for row in exclusion_rows if row["reason"] == "unmapped_or_conflicting_gene"],
            exclusion_columns,
        )
        write_json(work / "venn.json", venn_payload)

        venn_plots: list[str] = []
        if venn_plot:
            venn_plots = _plot_venn(
                work / "venn.json",
                work,
                [group for group in groups if venn_groups[group]["counts"]["targets"] > 0],
                warnings,
            )
            venn_plots = [str(out_dir / Path(item).name) for item in venn_plots]

        audit = {
            "schema_version": "1.1",
            "generated_by": "rnp intersect",
            "stage_status": stage_status,
            "config": {"path": str(config.path), "sha256": config.sha256},
            "thresholds": {
                "stp_probability": float(config.data["thresholds"]["stp_probability"])
            },
            "inputs": {
                "targets": str(targets_path),
                "targets_sha256": sha256_file(targets_path),
                "compounds_sha256": sha256_file(compounds_path),
                "disease_genes_sha256": sha256_file(disease_path),
                "hgnc_map_sha256": sha256_file(hgnc_path),
            },
            "outputs": {
                "edges_sha256": sha256_file(work / "edges.tsv"),
                "intersection_sha256": sha256_file(work / "intersection_genes.tsv"),
                "disease_sha256": sha256_file(work / "disease_genes.tsv"),
            },
            "parents": parents,
            "disease_label": disease_label,
            "groups": group_stats,
            "exclusions": {reason: exclusions.get(reason, 0) for reason in EXCLUSION_REASONS},
            "warnings": warnings,
            "venn_plots": venn_plots,
        }
        validate_document(audit, "intersection", "intersection audit")
        write_json(work / "intersect_audit.json", audit)

        exit_code = 0
        manifest = build_manifest(
            run_id=out_dir.name,
            command="intersect",
            args={
                "config": str(config.path),
                "targets": str(targets_path),
                "out": str(out_dir),
                "venn_plot": venn_plot,
                "allow_partial": allow_partial,
            },
            config=config,
            inputs=[config.path, targets_path, compounds_path, hgnc_path, disease_path],
            parents=parents,
            started_at=started_at,
            finished_at=utc_now_iso(),
            exit_code=exit_code,
            stage_status=stage_status,
            overwritten=force,
        )
        validate_document(manifest, "run_manifest", "run manifest")
        write_json(work / "run_manifest.json", manifest)

    return {
        "status": "ok",
        "stage_status": stage_status,
        "out_dir": str(out_dir),
        "groups": group_stats,
        "exclusions": audit["exclusions"],
        "warnings": len(warnings),
        "venn_plots": venn_plots,
    }
