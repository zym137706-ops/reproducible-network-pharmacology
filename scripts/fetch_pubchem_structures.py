#!/usr/bin/env python3
"""Fetch public PubChem structures for the frozen case CIDs, without committing them.

PubChem's PUG REST property names changed: the current endpoint returns ``SMILES``
(stereochemistry included where defined) and ``ConnectivitySMILES`` (connectivity only).
The old ``CanonicalSMILES``/``IsomericSMILES`` names are not returned by this endpoint, so
reading them silently produced empty strings. This script validates the response, requires
both non-empty structure fields, checks the returned CID, and records the raw response hashes.

Output goes to ``data/local/case/`` (git-ignored). The repository keeps only source records and
this reproducible recipe; structures are committed only after PubChem terms are checked.
This script does not submit anything to STP.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
DEFAULT_COMPOUNDS = ROOT / "examples" / "demo" / "inputs" / "compounds.tsv"
DEFAULT_OUT = ROOT / "data" / "local" / "case"

FIELD_MEANINGS = {
    "SMILES": "PubChem SMILES; includes stereochemistry where the record defines it",
    "ConnectivitySMILES": "PubChem connectivity SMILES; no stereochemistry",
}


class PubChemError(RuntimeError):
    """The PubChem response is missing required structure data or is inconsistent."""


def _fetch_payload(cid: str) -> tuple[str, dict]:
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
        f"{cid}/property/SMILES,ConnectivitySMILES/JSON"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "rnp-case-prep/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed host
        return url, json.loads(response.read().decode("utf-8"))


def _parse_properties(payload: dict, requested_cid: str) -> dict:
    """Parse and validate one current PubChem property response.

    The old code read ``CanonicalSMILES``/``IsomericSMILES`` and silently wrote empty
    strings. Missing fields, empty structures or a CID mismatch must be hard failures.
    """
    try:
        properties = payload["PropertyTable"]["Properties"]
    except (KeyError, TypeError) as exc:
        raise PubChemError("response has no PropertyTable.Properties") from exc
    if not isinstance(properties, list) or len(properties) != 1:
        raise PubChemError("response must contain exactly one property record")
    record = properties[0]
    returned_cid = str(record.get("CID", "")).strip()
    if returned_cid != str(requested_cid):
        raise PubChemError(
            f"CID mismatch: requested {requested_cid!r}, received {returned_cid!r}"
        )
    smiles = record.get("SMILES")
    connectivity = record.get("ConnectivitySMILES")
    for field, value in (("SMILES", smiles), ("ConnectivitySMILES", connectivity)):
        if not isinstance(value, str) or not value.strip():
            raise PubChemError(f"missing or empty {field} for CID {requested_cid}")
    return {
        "pubchem_cid": returned_cid,
        "smiles": smiles.strip(),
        "connectivity_smiles": connectivity.strip(),
    }


def _fetch(cid: str) -> dict:
    url, payload = _fetch_payload(cid)
    parsed = _parse_properties(payload, cid)
    parsed["source_url"] = url
    parsed["raw_response_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return parsed


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
    raw_files: dict[str, dict[str, str]] = {}
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for compound in compounds:
        cid = (compound.get("pubchem_cid") or "").strip()
        if not cid:
            print(f"error: missing pubchem_cid for {compound.get('name')!r}", file=sys.stderr)
            return 2
        try:
            url, payload = _fetch_payload(cid)
            fetched = _parse_properties(payload, cid)
        except (PubChemError, urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            print(f"error: PubChem fetch failed for CID {cid}: {exc}", file=sys.stderr)
            return 2
        raw_name = f"{cid}.json"
        raw_path = args.out / "raw" / raw_name
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raw_files[raw_name] = {
            "sha256": _sha256(raw_path),
            "source_url": url,
        }
        raw_sha = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        rows.append(
            {
                "name": compound["name"],
                "pubchem_cid": fetched["pubchem_cid"],
                "smiles": fetched["smiles"],
                "connectivity_smiles": fetched["connectivity_smiles"],
                "source_url": url,
                "retrieved_utc": retrieved_at,
                "raw_response_sha256": raw_sha,
            }
        )

    table = args.out / "pubchem_structures.tsv"
    # Atomic replace so a failed/empty fetch cannot masquerade as a successful table.
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=args.out, delete=False
    ) as handle:
        temp_path = Path(handle.name)
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    temp_path.replace(table)

    metadata = {
        "source": "PubChem PUG REST property endpoint",
        "requested_fields": ["SMILES", "ConnectivitySMILES"],
        "field_meanings": FIELD_MEANINGS,
        "endpoint_template": (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
            "{cid}/property/SMILES,ConnectivitySMILES/JSON"
        ),
        "retrieved_utc": retrieved_at,
        "license_status": "check PubChem terms before committing or redistributing",
        "committed": False,
        "row_count": len(rows),
        "files": {
            table.name: {
                "sha256": _sha256(table),
                "row_count": len(rows),
                "columns": list(rows[0]),
            }
        },
        "raw_files": raw_files,
    }
    (args.out / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {table} ({len(rows)} rows, SMILES and ConnectivitySMILES checked non-empty)")
    print(f"wrote {args.out / 'metadata.json'} (local only; do not commit without a licence check)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
