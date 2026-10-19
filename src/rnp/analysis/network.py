"""Cytoscape-ready compound–target–disease network tables.

Invariants enforced here (from the audited Cytoscape workflow): edges may only
reference nodes that exist, node types cover exactly the nodes created by the
edge import, and a compound name may not collide with a gene symbol or with the
disease label.

A run with zero intersection genes is a valid **empty** result: header-only
tables plus an audit that says so, never fabricated edges.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import RunConfig, validate_document
from ..errors import InputError
from ..io.tables import clean_text, read_table, write_table
from ..output import staged_output
from ..provenance import build_manifest, sha256_file, utc_now_iso, write_json
from .parents import (
    check_config_identity,
    load_parent_audit,
    parent_record,
    require_file,
    verify_sha256,
)

NETWORK_EDGE_COLUMNS = ["Source", "Target", "Interaction"]
NETWORK_NODE_COLUMNS = ["Node", "Type", "Label"]


def _safe_group(group: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", group).strip("_") or "group"


def _read_required(path: Path, columns: set[str]) -> list[dict[str, str]]:
    require_file(path, path.name)
    rows = read_table(path)
    if not rows:
        return []
    missing = columns - set(rows[0])
    if missing:
        raise InputError(
            f"{path.name}: unexpected table",
            details=[f"missing columns: {', '.join(sorted(missing))}"],
        )
    return rows


def run_network(
    config: RunConfig,
    intersect_dir: str | Path,
    out_dir: str | Path,
    *,
    disease_label: str | None = None,
    allow_partial: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Build per-group node/edge tables for Cytoscape from an intersection run."""
    intersect_dir = Path(intersect_dir).resolve()
    out_dir = Path(out_dir).resolve()
    started_at = utc_now_iso()

    audit_path = intersect_dir / "intersect_audit.json"
    parent_audit, override = load_parent_audit(
        audit_path,
        "intersection",
        stage_name="intersect",
        allow_partial=allow_partial,
    )
    check_config_identity(parent_audit, config, "intersect")

    outputs = parent_audit.get("outputs") or {}
    edges_path = intersect_dir / "edges.tsv"
    intersection_path = intersect_dir / "intersection_genes.tsv"
    disease_path = intersect_dir / "disease_genes.tsv"
    verify_sha256(edges_path, outputs.get("edges_sha256"), "edges.tsv")
    verify_sha256(
        intersection_path, outputs.get("intersection_sha256"), "intersection_genes.tsv"
    )
    verify_sha256(disease_path, outputs.get("disease_sha256"), "disease_genes.tsv")

    edges_rows = _read_required(
        edges_path, {"group", "compound_id", "compound", "gene"}
    )
    intersection_rows = _read_required(
        intersection_path, {"group", "gene"}
    )
    disease_rows = _read_required(disease_path, {"gene_symbol"})
    disease_genes = {clean_text(row["gene_symbol"]) for row in disease_rows if row["gene_symbol"]}

    parent_compounds_path = intersect_dir.parent / "compounds_registered.tsv"
    require_file(parent_compounds_path, "registered compound table")
    verify_sha256(
        parent_compounds_path,
        (parent_audit.get("inputs") or {}).get("compounds_sha256"),
        "compounds_registered.tsv",
    )
    compounds = _read_required(
        parent_compounds_path, {"compound_id", "group", "name"}
    )

    label = (
        clean_text(disease_label)
        or clean_text(config.data.get("network", {}).get("disease_label"))
        or config.project
    )
    groups = sorted({clean_text(row["group"]) for row in compounds})
    groups_with_hits = sorted({clean_text(row["group"]) for row in intersection_rows})
    compound_names = {clean_text(row["name"]) for row in compounds}
    gene_names = {clean_text(row["gene"]) for row in intersection_rows}
    lowered_genes = {gene.casefold() for gene in gene_names}
    collisions = sorted(name for name in compound_names if name.casefold() in lowered_genes)
    if collisions:
        raise InputError(
            "compound names collide with gene symbols; Cytoscape nodes would merge",
            details=[f"colliding names: {', '.join(collisions[:10])}"],
        )
    if label.casefold() in lowered_genes | {name.casefold() for name in compound_names}:
        raise InputError(f"disease label {label!r} collides with a node name")

    parents = [
        parent_record(
            stage="intersect",
            directory=intersect_dir,
            audit_path=audit_path,
            stage_status=str(parent_audit.get("stage_status")),
            override=override,
        )
    ]
    stage_status = (
        "empty"
        if not groups_with_hits
        else ("partial_override" if override else "complete")
    )
    group_summaries: dict[str, Any] = {}
    audits: dict[str, Any] = {}

    with staged_output(out_dir, force=force) as work:
        for group in groups:
            genes = sorted(
                {
                    clean_text(row["gene"])
                    for row in intersection_rows
                    if clean_text(row["group"]) == group
                }
            )
            if not genes:
                continue
            safe = _safe_group(group)
            group_dir = work / safe
            group_edges = [
                row for row in edges_rows if clean_text(row["group"]) == group
            ]
            pairs = sorted(
                {
                    (
                        clean_text(row["compound_id"]),
                        clean_text(row["compound"]),
                        clean_text(row["gene"]),
                    )
                    for row in group_edges
                    if clean_text(row["gene"]) in genes
                },
                key=lambda pair: (pair[1].casefold(), pair[2]),
            )
            linked = sorted({pair[1] for pair in pairs}, key=str.casefold)
            candidates = sorted(
                (
                    clean_text(row["name"])
                    for row in compounds
                    if clean_text(row["group"]) == group
                ),
                key=str.casefold,
            )
            if not candidates:
                candidates = linked
            mol_ids = {name: f"MOL{index:04d}" for index, name in enumerate(candidates, start=1)}

            network_edges = [
                {"Source": compound, "Target": gene, "Interaction": "compound-target"}
                for _, compound, gene in pairs
            ] + [
                {"Source": gene, "Target": label, "Interaction": "target-disease"}
                for gene in genes
            ]
            network_nodes = (
                [{"Node": name, "Type": "Compound", "Label": name} for name in linked]
                + [{"Node": gene, "Type": "Target", "Label": gene} for gene in genes]
                + [{"Node": label, "Type": "Disease", "Label": label}]
            )
            node_attributes = [
                {"Node": node["Node"], "Type": node["Type"], "MOLID": mol_ids.get(node["Node"], "")}
                for node in network_nodes
            ]
            mol_list = [{"MOLID": mol_ids[name], "moleculename": name} for name in candidates]

            node_set = {node["Node"] for node in network_nodes}
            endpoints = {edge["Source"] for edge in network_edges} | {
                edge["Target"] for edge in network_edges
            }
            duplicate_edges = len(network_edges) != len(
                {(edge["Source"], edge["Target"], edge["Interaction"]) for edge in network_edges}
            )
            checks = {
                "endpoints_match_nodes": endpoints == node_set,
                "edge_count_matches_pairs": len(network_edges) == len(pairs) + len(genes),
                "no_duplicate_edges": not duplicate_edges,
                "genes_have_disease_edge": all(gene in disease_genes for gene in genes),
                "all_pairs_reference_known_genes": all(gene in genes for _, _, gene in pairs),
                "molids_cover_candidates": set(mol_ids) == set(candidates),
            }
            failed = [name for name, passed in checks.items() if not passed]
            if failed:
                raise InputError(
                    f"network invariants failed for group {group!r}",
                    details=failed,
                )

            write_table(group_dir / "edges.tsv", network_edges, NETWORK_EDGE_COLUMNS)
            write_table(group_dir / "nodes.tsv", network_nodes, NETWORK_NODE_COLUMNS)
            write_table(group_dir / "mol_list.tsv", mol_list, ["MOLID", "moleculename"])
            write_table(
                group_dir / "node_attributes.tsv",
                node_attributes,
                ["Node", "Type", "MOLID"],
            )
            group_summaries[group] = {
                "group_dir": str(out_dir / safe),
                "compounds_total": len(candidates),
                "compounds_linked": len(linked),
                "targets": len(genes),
                "network_nodes": len(network_nodes),
                "network_edges": len(network_edges),
                "compound_target_edges": len(pairs),
                "disease_edges": len(genes),
            }
            audits[group] = {
                "checks": checks,
                "edges": len(network_edges),
                "nodes": len(network_nodes),
            }

        audit = {
            "schema_version": "1.1",
            "generated_by": "rnp network",
            "stage_status": stage_status,
            "disease_label": label,
            "inputs": {
                "intersect_dir": str(intersect_dir),
                "edges_sha256": sha256_file(edges_path),
                "intersection_sha256": sha256_file(intersection_path),
                "disease_sha256": sha256_file(disease_path),
                "compounds_sha256": sha256_file(parent_compounds_path),
            },
            "parents": parents,
            "groups": audits,
        }
        validate_document(audit, "network", "network audit")
        write_json(work / "network_audit.json", audit)

        manifest = build_manifest(
            run_id=out_dir.name,
            command="network",
            args={
                "config": str(config.path),
                "intersect_dir": str(intersect_dir),
                "out": str(out_dir),
                "disease_label": label,
                "allow_partial": allow_partial,
            },
            config=config,
            inputs=[
                config.path,
                edges_path,
                intersection_path,
                disease_path,
                parent_compounds_path,
            ],
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
        "status": "empty" if stage_status == "empty" else "ok",
        "stage_status": stage_status,
        "out_dir": str(out_dir),
        "disease_label": label,
        "groups": group_summaries,
    }
