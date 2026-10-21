#!/usr/bin/env python3
"""Independent checks for a completed rnp case run.

This reads the run's target/intersection/network/enrichment tables and re-derives the case sets and
statistics from the declared disease genes and HGNC map. It deliberately does not call the analysis
functions that produced the outputs and does not use their summary counts as the expected values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from rnp.io.tables import read_table
from rnp.normalize.hgnc import GeneMapper


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bh(pvalues: list[float]) -> list[float]:
    n = len(pvalues)
    order = sorted(range(n), key=lambda i: pvalues[i])
    adjusted = [0.0] * n
    previous = 1.0
    for rank, index in enumerate(reversed(order), start=1):
        i = n - rank + 1
        value = min(previous, pvalues[index] * n / i)
        adjusted[index] = value
        previous = value
    return adjusted


def hypergeom_sf(k: int, population: int, successes: int, draws: int) -> float:
    total = math.comb(population, draws)
    upper = min(successes, draws)
    return (
        sum(
            math.comb(successes, i) * math.comb(population - successes, draws - i)
            for i in range(k, upper + 1)
        )
        / total
    )


def normalise_targets(rows: list[dict[str, str]], mapper: GeneMapper) -> set[str]:
    symbols: set[str] = set()
    for row in rows:
        if (
            str(row.get("multi_symbol_common_name", "")).lower() == "true"
            or str(row.get("is_complex", "")).lower() == "true"
        ):
            continue
        mapped = mapper.map(row.get("common_name", ""), row.get("uniprot_id", ""))
        if mapped.mapping_conflict:
            continue
        if mapped.gene_symbol:
            symbols.add(mapped.gene_symbol)
    return symbols


def check_run(
    label: str,
    run: Path,
    background_dir: Path,
    disease: set[str],
    mapper: GeneMapper,
) -> dict[str, object]:
    targets = read_table(run / "targets.tsv")
    t_r = normalise_targets(targets, mapper)
    foreground = t_r & disease
    bg_text = (background_dir / f"universe-{label}.txt").read_text(encoding="utf-8")
    fg_text = (background_dir / f"foreground-{label}.txt").read_text(encoding="utf-8")
    background = set(bg_text.split())
    if background != t_r:
        raise AssertionError(f"{label}: background T_r mismatch")
    if set(fg_text.split()) != foreground:
        raise AssertionError(f"{label}: foreground mismatch")

    intersect_audit = json.loads((run / "intersect" / "intersect_audit.json").read_text())
    group = intersect_audit["groups"]["all"]
    if group["targets"] != len(t_r):
        raise AssertionError(f"{label}: intersection target count mismatch")
    if group["intersection"] != len(foreground):
        raise AssertionError(f"{label}: intersection count mismatch")
    if len(read_table(run / "intersect" / "intersection_genes.tsv")) != group["intersection"]:
        raise AssertionError(f"{label}: intersection table row count mismatch")

    network_audit = json.loads((run / "network" / "network_audit.json").read_text())
    network = network_audit["groups"]["all"]
    if not all(network["checks"].values()):
        raise AssertionError(f"{label}: network invariant failed")

    enrich_audit = json.loads((run / "enrichment" / "enrichment_audit.json").read_text())
    enrich = enrich_audit["groups"]["all"]
    effective_fg = enrich["effective_foreground"]
    effective_bg = enrich["effective_background"]
    result_path = run / "enrichment" / "all" / "enrichment_result.tsv"
    rows = read_table(result_path)
    pvalues = []
    for row in rows:
        population = int(row["BgRatio"].split("/")[1])
        successes = int(row["BgRatio"].split("/")[0])
        if population != effective_bg:
            raise AssertionError(f"{label}: result BgRatio does not match audit background")
        p = hypergeom_sf(int(row["Count"]), population, successes, effective_fg)
        if not math.isclose(float(row["pvalue"]), p, rel_tol=1e-9, abs_tol=1e-12):
            raise AssertionError(f"{label}: p-value mismatch for {row['ID']}")
        pvalues.append(p)
    for row, expected in zip(rows, bh(pvalues), strict=True):
        if not math.isclose(float(row["p.adjust"]), expected, rel_tol=1e-8, abs_tol=1e-12):
            raise AssertionError(f"{label}: BH mismatch for {row['ID']}")

    report_audit = json.loads((run / "report" / "report_audit.json").read_text())
    return {
        "run_dir": str(run),
        "T_r": len(t_r),
        "foreground": len(foreground),
        "intersection": group["intersection"],
        "network_nodes": network["nodes"],
        "network_edges": network["edges"],
        "effective_foreground": effective_fg,
        "effective_background": effective_bg,
        "terms_tested": len(rows),
        "significant": int(enrich["significant"]),
        "enrichment_status": enrich["status"],
        "report_sha256": report_audit["report_sha256"],
        "stage_status": {
            "intersect": intersect_audit["stage_status"],
            "network": network_audit["stage_status"],
            "enrichment": enrich_audit["stage_status"],
            "report": report_audit["stage_status"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="LABEL=DIR",
        help="threshold label and run dir",
    )
    parser.add_argument("--background-dir", type=Path, required=True)
    parser.add_argument("--disease-genes", type=Path, required=True)
    parser.add_argument("--hgnc-map", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    mapper = GeneMapper(args.hgnc_map)
    disease = {
        line.strip()
        for line in args.disease_genes.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    disease = {
        mapped.gene_symbol
        for symbol in disease
        if (mapped := mapper.map(symbol)).gene_symbol
    }
    if not disease:
        raise SystemExit("disease gene list produced no mapped symbols")
    result: dict[str, object] = {
        "disease_sha256": sha256(args.disease_genes),
        "hgnc_sha256": sha256(args.hgnc_map),
        "runs": {},
    }
    for spec in args.run:
        label, raw_path = spec.split("=", 1)
        result["runs"][label] = check_run(
            label, Path(raw_path).resolve(), args.background_dir.resolve(), disease, mapper
        )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
