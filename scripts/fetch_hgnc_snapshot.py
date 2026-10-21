#!/usr/bin/env python3
"""Fetch the HGNC complete set and derive the case's normalisation table.

HGNC data are CC0 (https://www.genenames.org/about/license/); attribution is recommended.
The script records the source URL, response headers, retrieval time and hashes. It does not
guess a release date: the HTTP Last-Modified value is recorded alongside the retrieval time.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
DEFAULT_URL = "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt"
DEFAULT_OUT = ROOT / "data" / "local" / "reference" / "hgnc_map.tsv"
COLUMNS = [
    "hgnc_id",
    "symbol",
    "status",
    "prev_symbol",
    "alias_symbol",
    "uniprot_ids",
    "entrez_id",
    "locus_group",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--raw", type=Path, default=None, help="keep the downloaded raw file")
    args = parser.parse_args(argv)

    request = urllib.request.Request(args.url, headers={"User-Agent": "rnp-case-prep/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - fixed host
            raw = response.read()
            last_modified = response.headers.get("Last-Modified")
    except OSError as exc:
        print(f"error: HGNC download failed: {exc}", file=sys.stderr)
        return 2

    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_path = args.raw or (
        ROOT / "data" / "local" / "reference" / "hgnc_complete_set.txt"
    )
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    raw_sha = hashlib.sha256(raw).hexdigest()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    approved = 0
    total = 0
    with raw_path.open("r", encoding="utf-8", newline="") as source, args.out.open(
        "w", encoding="utf-8", newline=""
    ) as target:
        reader = csv.DictReader(source, delimiter="\t")
        missing = [column for column in COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            print(f"error: HGNC file missing columns: {missing}", file=sys.stderr)
            return 2
        writer = csv.DictWriter(target, fieldnames=COLUMNS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            total += 1
            if row.get("status") != "Approved":
                continue
            approved += 1
            writer.writerow({column: row.get(column, "") for column in COLUMNS})
    if approved == 0:
        print("error: no Approved HGNC records derived", file=sys.stderr)
        return 2

    metadata = {
        "source": "HGNC complete set",
        "url": args.url,
        "license": "CC0 (HGNC recommends attribution; cite genenames.org)",
        "retrieved_utc": retrieved,
        "http_last_modified": last_modified,
        "raw_sha256": raw_sha,
        "raw_size_bytes": len(raw),
        "raw_total_rows": total,
        "derived_rows_approved": approved,
        "derived_columns": COLUMNS,
        "derived_sha256": _sha256(args.out),
        "committed": False,
    }
    (args.out.parent / "hgnc_map.metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out} ({approved} Approved records; raw {total})")
    print(f"raw sha256: {raw_sha}")
    print(f"derived sha256: {metadata['derived_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
