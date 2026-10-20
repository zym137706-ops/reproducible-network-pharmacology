#!/usr/bin/env python3
"""Fetch public PubChem structures for the frozen case CIDs, without committing them.

The output goes to ``data/local/case/`` (git-ignored). The repository keeps only the source
record and the reproducible fetch recipe; structures are committed only after the PubChem
terms for the requested use are checked. This script does not submit anything to STP.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
DEFAULT_COMPOUNDS = ROOT / "examples" / "demo" / "inputs" / "compounds.tsv"
DEFAULT_OUT = ROOT / "data" / "local" / "case"


def _fetch(cid: str) -> dict:
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
        f"{cid}/property/CanonicalSMILES,IsomericSMILES/JSON"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "rnp-case-prep/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed host
        payload = json.loads(response.read().decode("utf-8"))
    properties = payload["PropertyTable"]["Properties"][0]
    return {
        "pubchem_cid": str(properties["CID"]),
        "canonical_smiles": properties.get("CanonicalSMILES", ""),
        "isomeric_smiles": properties.get("IsomericSMILES", ""),
        "source_url": url,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compounds", type=Path, default=DEFAULT_COMPOUNDS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    with args.compounds.open(encoding="utf-8", newline="") as handle:
        compounds = list(csv.DictReader(handle, delimiter="\t"))
    if not compounds:
        print("error: compound table is empty", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for compound in compounds:
        cid = (compound.get("pubchem_cid") or "").strip()
        if not cid:
            print(f"error: missing pubchem_cid for {compound.get('name')!r}", file=sys.stderr)
            return 2
        try:
            fetched = _fetch(cid)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            print(f"error: PubChem fetch failed for CID {cid}: {exc}", file=sys.stderr)
            return 2
        rows.append(
            {
                "name": compound["name"],
                "pubchem_cid": fetched["pubchem_cid"],
                "canonical_smiles": fetched["canonical_smiles"],
                "isomeric_smiles": fetched["isomeric_smiles"],
                "source_url": fetched["source_url"],
                "retrieved_utc": retrieved_at,
            }
        )

    table = args.out / "pubchem_structures.tsv"
    with table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    metadata = {
        "source": "PubChem PUG REST",
        "retrieved_utc": retrieved_at,
        "license_status": "check PubChem terms before committing or redistributing",
        "committed": False,
        "files": {
            table.name: {
                "sha256": _sha256(table),
                "row_count": len(rows),
                "columns": list(rows[0]),
            }
        },
    }
    (args.out / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(f"wrote {table} ({len(rows)} rows)")
    print(f"wrote {args.out / 'metadata.json'} (local only; do not commit without a licence check)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
