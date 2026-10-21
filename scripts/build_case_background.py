#!/usr/bin/env python3
"""Build the pre-declared conditional enrichment background for the public case.

For each requested STP probability threshold ``r``:

* ``T_r`` = all HGNC-normalised, unique target symbols from the thresholded target table
  (before any disease intersection); composite/multi-symbol rows are excluded explicitly;
* background = ``T_r``;
* foreground = ``T_r`` ∩ ``D`` (D = normalised disease genes).

The resulting universe is a **conditional** background within predicted targets. It is not the
whole annotated genome. GO annotation loss is handled later by the R audit; this script only records
the pre-engine mapping loss and hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rnp.io.tables import read_table
from rnp.normalize.hgnc import GeneMapper

ROOT = Path(__file__).parents[1]
DEFAULT_HGNC = ROOT / "examples" / "demo" / "inputs" / "hgnc_map.tsv"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalise(rows: list[dict[str, str]], mapper: GeneMapper) -> tuple[set[str], dict[str, Any]]:
    mapped: set[str] = set()
    counts = {"rows": 0, "mapped": 0, "unmapped": 0, "conflict": 0, "skipped_multi": 0}
    for row in rows:
        counts["rows"] += 1
        if (row.get("multi_symbol_common_name") or "").strip().lower() == "true":
            counts["skipped_multi"] += 1
            continue
        if (row.get("is_complex") or "").strip().lower() == "true":
            counts["skipped_multi"] += 1
            continue
        result = mapper.map(row.get("common_name", ""), row.get("uniprot_id", ""))
        if result.mapping_conflict:
            counts["conflict"] += 1
            continue
        if not result.gene_symbol:
            counts["unmapped"] += 1
            continue
        mapped.add(result.gene_symbol)
        counts["mapped"] += 1
    return mapped, counts


def _write_lines(path: Path, values: set[str]) -> None:
    path.write_text("".join(f"{value}\n" for value in sorted(values)), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--targets",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="threshold label and its rnp targets.tsv (repeat for 0.10 and 0.05)",
    )
    parser.add_argument("--disease-genes", type=Path, required=True)
    parser.add_argument("--hgnc-map", type=Path, default=DEFAULT_HGNC)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "local" / "case" / "backgrounds",
    )
    args = parser.parse_args(argv)

    mapper = GeneMapper(args.hgnc_map)
    disease_symbols = [
        line.strip()
        for line in args.disease_genes.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not disease_symbols:
        raise SystemExit("error: disease gene list is empty")
    disease_mapped, disease_counts = _normalise(
        [
            {"common_name": symbol, "uniprot_id": "", "multi_symbol_common_name": "false"}
            for symbol in sorted(disease_symbols)
        ],
        mapper,
    )
    if not disease_mapped:
        raise SystemExit("error: disease gene list produced no mapped symbols")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summaries: dict[str, Any] = {}
    for spec in args.targets:
        if "=" not in spec:
            raise SystemExit(f"error: --targets expects LABEL=PATH, got {spec!r}")
        label, target_path = spec.split("=", 1)
        if not label or not Path(target_path).is_file():
            raise SystemExit(f"error: bad targets specification: {spec!r}")
        target_rows = read_table(Path(target_path))
        targets, target_counts = _normalise(target_rows, mapper)
        foreground = targets & disease_mapped
        universe_path = args.out_dir / f"universe-{label}.txt"
        foreground_path = args.out_dir / f"foreground-{label}.txt"
        _write_lines(universe_path, targets)
        _write_lines(foreground_path, foreground)
        meta = {
            "rule": (
                "T_r = HGNC-normalised unique targets from the thresholded target table "
                "before disease intersection; background=T_r; foreground=T_r ∩ D; "
                "multi/composite rows excluded"
            ),
            "threshold_label": label,
            "conditional_within_predicted_targets": True,
            "targets_file": str(Path(target_path)),
            "targets_sha256": _sha256(Path(target_path)),
            "hgnc_map": str(args.hgnc_map),
            "disease_genes": str(args.disease_genes),
            "disease_sha256": _sha256(args.disease_genes),
            "target_counts": target_counts,
            "disease_counts": disease_counts,
            "background_size": len(targets),
            "foreground_size": len(foreground),
            "background_sha256": _sha256(universe_path),
            "foreground_sha256": _sha256(foreground_path),
            "generated_utc": retrieved,
            "note": (
                "GO-annotated effective background and mapping loss are recorded by rnp enrich."
            ),
        }
        meta_path = args.out_dir / f"background-{label}.meta.json"
        meta_path.write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        summaries[label] = meta
    print(json.dumps(summaries, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
