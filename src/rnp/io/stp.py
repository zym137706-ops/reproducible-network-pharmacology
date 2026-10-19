"""SwissTargetPrediction export parsing.

Status taxonomy (one per file, never conflated):

* ``ok`` — at least one valid row at/above the threshold, no invalid rows
* ``partial`` — valid rows at/above threshold **and** invalid rows
* ``below_threshold`` — valid rows exist, none reaches the threshold
* ``invalid_rows`` — rows exist, every probability is invalid
* ``no_predictions`` — the table is structurally valid but empty
* ``error`` — unreadable file or missing required columns (fatal for that file)

``rows_invalid`` is never counted as ``rows_below_threshold``: an unparseable
row is a data problem, not a prediction that failed the cutoff.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..errors import InputError
from ..provenance import sha256_file

REQUIRED_HEADERS = ("target", "common name", "uniprot id", "probability")
HEADER_SCAN_LIMIT = 10

_COLUMN_ALIASES = {
    "target": ("target",),
    "common name": ("common name", "commonname", "common_name"),
    "uniprot id": ("uniprot id", "uniprotid", "uniprot_id", "uniprot"),
    "probability": ("probability", "probability*", "proba"),
    "chembl id": ("chembl id", "chemblid", "chembl_id"),
    "target class": ("target class", "targetclass", "target_class"),
    "known actives": ("known actives", "knownactives", "known actives (3d/2d)"),
}

_TARGETS_COLUMNS = (
    "compound_id",
    "group",
    "submission_id",
    "source_file",
    "target",
    "common_name",
    "uniprot_id",
    "target_class",
    "chembl_id",
    "probability",
    "is_complex",
    "multi_symbol_common_name",
    "row_number",
)

FILE_STATUSES = (
    "ok",
    "partial",
    "below_threshold",
    "invalid_rows",
    "no_predictions",
    "error",
)


def normalise_header(cell: Any) -> str:
    text = "" if cell is None else str(cell)
    text = text.replace("*", " ").strip().lower()
    return " ".join(text.split())


def _match_column(normalised: str) -> str | None:
    for canonical, aliases in _COLUMN_ALIASES.items():
        if normalised in aliases:
            return canonical
    return None


def _read_rows(path: Path) -> tuple[list[list[Any]], str]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise InputError("openpyxl is required to read .xlsx exports") from exc
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001 - openpyxl raises many types
            raise InputError(f"{path.name}: cannot open workbook: {exc}") from exc
        try:
            sheet = workbook.active
            if sheet is None:
                raise InputError(f"{path.name}: workbook has no active sheet")
            return [list(row) for row in sheet.iter_rows(values_only=True)], "xlsx"
        finally:
            workbook.close()

    if suffix in {".csv", ".tsv", ".txt"}:
        delimiters = ["\t"] if suffix in {".tsv", ".txt"} else [",", "\t"]
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            for delimiter in delimiters:
                try:
                    with path.open("r", encoding=encoding, newline="") as handle:
                        sample = handle.read(4096)
                        handle.seek(0)
                        dialect = _sniff_dialect(sample, delimiter)
                        return [list(row) for row in csv.reader(handle, dialect)], "csv"
                except (UnicodeDecodeError, csv.Error) as exc:
                    last_error = exc
                    continue
        raise InputError(f"{path.name}: cannot decode as text ({last_error})")

    raise InputError(f"{path.name}: unsupported export type (expected .xlsx, .csv or .tsv)")


def _sniff_dialect(sample: str, fallback_delimiter: str) -> type[csv.Dialect] | csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        return csv.excel_tab if fallback_delimiter == "\t" else csv.excel


@dataclass
class ExportParseResult:
    path: Path
    fmt: str
    sha256: str
    header_row_index: int | None
    columns: dict[str, str] = field(default_factory=dict)
    records: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    rows_total: int = 0
    rows_valid: int = 0
    rows_invalid: int = 0
    rows_below_threshold: int = 0
    rows_used: int = 0
    empty_table: bool = False

    @property
    def status(self) -> str:
        if self.empty_table:
            return "no_predictions"
        if self.rows_valid == 0:
            return "invalid_rows" if self.rows_total else "no_predictions"
        if self.rows_used == 0:
            return "below_threshold"
        if self.rows_invalid:
            return "partial"
        return "ok"

    @property
    def has_error(self) -> bool:
        return self.status in {"invalid_rows", "partial"}


def _find_header(rows: list[list[Any]]) -> tuple[int, dict[int, str]] | None:
    for index, row in enumerate(rows[:HEADER_SCAN_LIMIT]):
        mapping: dict[int, str] = {}
        for column, cell in enumerate(row):
            canonical = _match_column(normalise_header(cell))
            if canonical and canonical not in mapping.values():
                mapping[column] = canonical
        if len(set(mapping.values()) & set(REQUIRED_HEADERS)) >= 3:
            return index, mapping
    return None


def parse_probability(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        if text.count(",") == 1 and "." not in text:
            try:
                number = float(text.replace(",", "."))
            except ValueError:
                return None
        else:
            return None
    if not math.isfinite(number) or number < 0 or number > 1:
        return None
    return number


def _looks_like_symbols(common_name: str) -> bool:
    tokens = [token for token in common_name.replace(";", " ").split() if token]
    return len(tokens) > 1 and all(token[:1].isalpha() for token in tokens)


def parse_export(path: Path, *, threshold: float) -> ExportParseResult:
    """Parse one export file. Raises :class:`InputError` only for fatal problems."""
    path = Path(path)
    if not path.is_file():
        raise InputError(f"export not found: {path}")
    rows, fmt = _read_rows(path)
    result = ExportParseResult(
        path=path, fmt=fmt, sha256=sha256_file(path), header_row_index=None
    )
    if not rows:
        raise InputError(f"{path.name}: file is empty")

    header = _find_header(rows)
    if header is None:
        seen = [str(cell) for cell in rows[0] if cell not in (None, "")][:6]
        raise InputError(
            f"{path.name}: header not found in the first {HEADER_SCAN_LIMIT} rows",
            details=[f"first row cells: {seen or '<empty>'}"],
        )
    header_index, columns = header
    detected = set(columns.values())
    missing = [name for name in REQUIRED_HEADERS if name not in detected]
    if missing:
        raise InputError(
            f"{path.name}: header is missing required columns",
            details=[f"missing: {', '.join(missing)}"],
        )
    result.header_row_index = header_index
    result.columns = {name: str(index) for index, name in sorted(columns.items())}
    by_name = {name: index for index, name in columns.items()}

    data_rows = [
        row for row in rows[header_index + 1 :] if any(cell not in (None, "") for cell in row)
    ]
    result.empty_table = not data_rows
    if result.empty_table:
        return result

    for offset, row in enumerate(data_rows, start=header_index + 2):
        result.rows_total += 1
        values = {
            name: (row[index] if index < len(row) else None) for name, index in by_name.items()
        }

        target = str(values.get("target") or "").strip()
        common_name = str(values.get("common name") or "").strip()
        uniprot_id = str(values.get("uniprot id") or "").strip()
        probability = parse_probability(values.get("probability"))

        if not target and not common_name and not uniprot_id:
            result.warnings.append(
                {"code": "empty_target_row", "row": offset, "message": "row has no target fields"}
            )
            result.rows_invalid += 1
            continue
        if probability is None:
            result.errors.append(
                {
                    "code": "invalid_probability",
                    "row": offset,
                    "message": (
                        f"probability {values.get('probability')!r} is not a finite 0-1 number"
                    ),
                }
            )
            result.rows_invalid += 1
            continue

        result.rows_valid += 1
        is_complex = "&" in uniprot_id or "&" in common_name or common_name.upper() == "N/A"
        multi_symbol = (not is_complex) and _looks_like_symbols(common_name)
        if is_complex:
            result.warnings.append(
                {
                    "code": "complex_target",
                    "row": offset,
                    "message": f"composite target kept as one row: {uniprot_id or common_name}",
                }
            )
        if multi_symbol:
            result.warnings.append(
                {
                    "code": "multi_symbol_common_name",
                    "row": offset,
                    "message": f"common name holds several symbols: {common_name}",
                }
            )
        if not uniprot_id:
            result.warnings.append(
                {"code": "missing_uniprot_id", "row": offset, "message": "no UniProt ID"}
            )

        if probability < threshold:
            result.rows_below_threshold += 1
            continue
        result.records.append(
            {
                "target": target,
                "common_name": common_name,
                "uniprot_id": uniprot_id,
                "target_class": str(values.get("target class") or "").strip(),
                "chembl_id": str(values.get("chembl id") or "").strip(),
                "probability": probability,
                "is_complex": is_complex,
                "multi_symbol_common_name": multi_symbol,
                "row_number": offset,
            }
        )
        result.rows_used += 1
    return result


def write_targets_tsv(records: list[dict[str, Any]], path: Path) -> None:
    """Write the audited target table in a stable order, full probability precision."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        records,
        key=lambda r: (r["source_file"], -r["probability"], r["target"], r["row_number"]),
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_TARGETS_COLUMNS, delimiter="\t")
        writer.writeheader()
        for record in ordered:
            row = dict(record)
            row["probability"] = f"{record['probability']:.10g}"
            writer.writerow(row)


def audit_entry(result: ExportParseResult, *, compound: Any = None) -> dict[str, Any]:
    entry = {
        "path": result.path.name,
        "format": result.fmt,
        "sha256": result.sha256,
        "status": result.status,
        "header_row_index": result.header_row_index,
        "columns_detected": result.columns,
        "rows_total": result.rows_total,
        "rows_valid": result.rows_valid,
        "rows_invalid": result.rows_invalid,
        "rows_below_threshold": result.rows_below_threshold,
        "rows_used": result.rows_used,
        "warnings": result.warnings,
        "errors": result.errors,
    }
    if compound is not None:
        entry["compound_id"] = compound.compound_id
        entry["group"] = compound.group
        entry["submission_id"] = compound.submission_id
    return entry
