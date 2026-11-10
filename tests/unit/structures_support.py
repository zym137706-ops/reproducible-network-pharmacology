"""Fakes and builders shared by the structure tests. No RDKit and no network here."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from rnp.structures import CompoundRow, StructureInfo
from rnp.structures.chem import StructureError

NOW = "2026-11-10T01:00:00Z"
LATER = "2026-11-11T02:30:00Z"
EARLIER = "2026-11-09T00:00:00Z"
TOOLKIT_VERSION = "2026.03.4"
REGISTRY_COLUMNS = [
    "structure_id",
    "compound_id",
    "smiles",
    "inchikey",
    "connectivity_block",
    "formula",
    "net_charge",
    "fragment_count",
    "stereo_status",
    "stereo_elements_specified",
    "stereo_elements_total",
    "standardization",
    "toolkit",
    "toolkit_version",
    "rule_version",
    "status",
    "superseded_by",
    "first_seen_utc",
    "last_seen_utc",
]
STRUCTURES_COLUMNS = [
    "compound_id",
    "group",
    "name",
    "stp_file",
    "row_status",
    "structure_status",
    "structure_id",
    "smiles",
    "inchikey",
    "stereo_status",
    "submission_status",
    "export_kind",
    "export_sha256",
    "issue_codes",
]
SUMMARY_FIELDS = [
    "rows",
    "rows_accepted",
    "rows_quarantined",
    "rows_name_only",
    "structures_new",
    "structures_reused",
    "structures_superseded",
    "submissions_verified",
    "submissions_reconstructed",
    "submissions_not_recorded",
    "submissions_rejected",
    "errors",
    "warnings",
]


def letters(seed: str, count: int) -> str:
    """Deterministic upper-case letters derived from a seed (stands in for an InChIKey block)."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return "".join(chr(ord("A") + digest[index] % 26) for index in range(count))


def fake_key(smiles: str, stereo: str = "A") -> str:
    """A well-formed fake InChIKey: block 1 depends on the string, the rest on `stereo`."""
    return f"{letters(smiles, 14)}-{letters(smiles + stereo, 8)}SA-N"


def fake_info(smiles: str, **fields) -> StructureInfo:
    key = fields.pop("inchikey", None) or fake_key(smiles)
    values = {
        "inchikey": key,
        "connectivity_block": key.split("-")[0],
        "formula": "C2H6O",
        "net_charge": 0,
        "fragment_count": 1,
        "stereo_status": "none_present",
        "stereo_elements_specified": 0,
        "stereo_elements_total": 0,
    }
    values.update(fields)
    return StructureInfo(smiles=smiles, **values)


class Describer:
    """A stand-in for the RDKit adapter that records its calls and can fail on request."""

    def __init__(self, overrides: dict[str, dict] | None = None) -> None:
        self.overrides = overrides or {}
        self.calls: list[str] = []

    def __call__(self, smiles: str) -> StructureInfo:
        self.calls.append(smiles)
        if smiles.startswith("!"):
            raise StructureError(f"{smiles} is not a structure")
        return fake_info(smiles, **self.overrides.get(smiles, {}))


def compound(number: int, smiles: str = "CCO", **fields) -> CompoundRow:
    values = {
        "row": number,
        "compound_id": f"CMP{number:04d}",
        "group": "all",
        "name": f"Compound {number}",
        "stp_file": f"c{number}.xlsx",
        "smiles": smiles,
        "pubchem_cid": "",
    }
    values.update(fields)
    return CompoundRow(**values)


def registry_row(
    compound_id: str,
    number: int,
    smiles: str,
    *,
    status: str = "current",
    superseded_by: str = "",
    inchikey: str | None = None,
    stereo_status: str = "none_present",
    specified: int = 0,
    total: int = 0,
    fragments: int = 1,
    charge: int = 0,
    first: str = EARLIER,
    last: str = EARLIER,
) -> dict[str, str]:
    key = inchikey or fake_key(smiles)
    return {
        "structure_id": f"STR{number:04d}",
        "compound_id": compound_id,
        "smiles": smiles,
        "inchikey": key,
        "connectivity_block": key.split("-")[0],
        "formula": "C2H6O",
        "net_charge": str(charge),
        "fragment_count": str(fragments),
        "stereo_status": stereo_status,
        "stereo_elements_specified": str(specified),
        "stereo_elements_total": str(total),
        "standardization": "not_performed",
        "toolkit": "rdkit",
        "toolkit_version": TOOLKIT_VERSION,
        "rule_version": "v0.2.0-structure-registry",
        "status": status,
        "superseded_by": superseded_by,
        "first_seen_utc": first,
        "last_seen_utc": last,
    }


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_export(directory: Path, name: str, body: str | None = None) -> str:
    """Create an export file in `directory` and return the SHA-256 of what was written."""
    content = (body if body is not None else f"synthetic STP export {name}").encode("utf-8")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def log_row(number: int, sha256: str, **fields) -> dict[str, str]:
    """A complete, valid log row for `compound(number)` with SMILES CCO."""
    row = {
        "compound": f"Compound {number}",
        "pubchem_cid": "",
        "stp_file": f"c{number}.xlsx",
        "submitted_structure": "CCO",
        "species": "Homo sapiens",
        "submitted_date": "2026-10-21",
        "result_sha256": sha256,
        "export_kind": "native_export",
    }
    row.update(fields)
    return row


LOG_COLUMNS = [
    "compound",
    "pubchem_cid",
    "stp_file",
    "submitted_structure",
    "species",
    "submitted_date",
    "result_sha256",
    "export_kind",
    "result_rows",
    "job_id",
]


def write_log(path: Path, rows: list[dict[str, str]]) -> Path:
    return write_tsv(
        path, LOG_COLUMNS, [{key: row.get(key, "") for key in LOG_COLUMNS} for row in rows]
    )
