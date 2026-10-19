"""HGNC symbol normalization.

The mapping rules were extracted from the author's audited workflow and are kept
deliberately conservative:

* only ``Approved`` records are indexed;
* an old/alias symbol is converted only when it resolves to exactly one gene;
* a unique UniProt accession may resolve a symbol;
* if the symbol and the UniProt accession disagree, the row is flagged as a
  conflict and excluded from the single-gene main table instead of being
  silently "fixed".
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..errors import InputError

REQUIRED_COLUMNS = (
    "hgnc_id",
    "symbol",
    "status",
    "prev_symbol",
    "alias_symbol",
    "uniprot_ids",
    "entrez_id",
    "locus_group",
)

_PLACEHOLDERS = {"NA", "N/A", "NONE", "-"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


@dataclass(frozen=True)
class MapResult:
    gene_symbol: str
    hgnc_id: str
    entrez_id: str
    locus_group: str
    mapping_status: str
    mapping_conflict: bool
    ambiguous_symbols: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class GeneMapper:
    """Map (symbol, optional UniProt) pairs onto approved HGNC symbols."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.approved: dict[str, dict[str, str]] = {}
        self.previous: dict[str, list[dict[str, str]]] = {}
        self.alias: dict[str, list[dict[str, str]]] = {}
        self.uniprot: dict[str, list[dict[str, str]]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            raise InputError(f"HGNC mapping table not found: {self.path}")
        try:
            with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                columns = reader.fieldnames or []
                missing = [column for column in REQUIRED_COLUMNS if column not in columns]
                if missing:
                    raise InputError(
                        f"{self.path.name}: missing HGNC columns",
                        details=[f"missing: {', '.join(missing)}"],
                    )
                for row in reader:
                    if _clean(row.get("status")) != "Approved":
                        continue
                    symbol = _clean(row["symbol"])
                    if not symbol:
                        continue
                    self.approved[symbol.upper()] = row
                    for field, index in (
                        ("prev_symbol", self.previous),
                        ("alias_symbol", self.alias),
                        ("uniprot_ids", self.uniprot),
                    ):
                        for token in _clean(row.get(field)).split("|"):
                            token = token.strip().upper()
                            if token:
                                index.setdefault(token, []).append(row)
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise InputError(f"cannot read HGNC table {self.path.name}: {exc}") from exc
        if not self.approved:
            raise InputError(f"{self.path.name}: no Approved HGNC records found")

    def map(self, symbol: str, uniprot_id: str = "") -> MapResult:
        key = _clean(symbol).upper()
        if key in _PLACEHOLDERS:
            key = ""
        accession = _clean(uniprot_id).upper()

        record: dict[str, str] | None = None
        status = "unmapped"
        ambiguous: list[str] = []
        uniprot_records = {
            row["hgnc_id"]: row for row in self.uniprot.get(accession, []) if accession
        }

        if key in self.approved:
            record = self.approved[key]
            status = "approved_symbol"
        else:
            for index, label in ((self.previous, "previous_symbol"), (self.alias, "alias_symbol")):
                candidates = {row["hgnc_id"]: row for row in index.get(key, [])} if key else {}
                if len(candidates) == 1:
                    record = next(iter(candidates.values()))
                    status = label
                    break
                if candidates and uniprot_records:
                    shared = set(candidates) & set(uniprot_records)
                    if len(shared) == 1:
                        record = candidates[next(iter(shared))]
                        status = f"{label}_resolved_by_UniProt"
                        break
                ambiguous.extend(row["symbol"] for row in candidates.values())
            if record is None and len(uniprot_records) == 1:
                record = next(iter(uniprot_records.values()))
                status = "unique_UniProt"

        conflict = bool(record and uniprot_records and record["hgnc_id"] not in uniprot_records)
        if conflict:
            status += ";symbol_UniProt_conflict"

        return MapResult(
            gene_symbol=_clean(record["symbol"]) if record else "",
            hgnc_id=_clean(record["hgnc_id"]) if record else "",
            entrez_id=_clean(record["entrez_id"]) if record else "",
            locus_group=_clean(record["locus_group"]) if record else "",
            mapping_status=status,
            mapping_conflict=conflict,
            ambiguous_symbols=";".join(sorted(set(ambiguous))),
        )


def map_disease_genes(path: str | Path, mapper: GeneMapper) -> list[dict[str, Any]]:
    """Map a one-symbol-per-line disease gene list; raise on unresolved rows."""
    gene_path = Path(path)
    if not gene_path.is_file():
        raise InputError(f"disease gene list not found: {gene_path}")
    audit: list[dict[str, Any]] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    for line in gene_path.read_text(encoding="utf-8-sig").splitlines():
        raw = _clean(line)
        if not raw or raw.startswith("#"):
            continue
        result = mapper.map(raw)
        entry = {"original_gene": raw, **result.as_dict()}
        audit.append(entry)
        if not result.gene_symbol or result.mapping_conflict:
            unresolved.append(raw)
        elif result.gene_symbol in seen:
            entry["duplicate"] = True
        else:
            seen.add(result.gene_symbol)
    if unresolved:
        raise InputError(
            "disease gene list contains symbols that cannot be mapped unambiguously",
            details=[
                f"unresolved: {', '.join(sorted(set(unresolved))[:15])}",
                "fix the input or use an HGNC snapshot that contains these symbols",
            ],
        )
    return audit
