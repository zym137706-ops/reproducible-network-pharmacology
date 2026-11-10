"""Strict reading of the delimited tables accepted by the structure library."""

from __future__ import annotations

import csv
from pathlib import Path

from ..errors import InputError
from ..io.tables import detect_delimiter


def read_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a TSV/CSV with a header, preserving raw cell strings and row numbers."""
    table_path = Path(path)
    if not table_path.is_file():
        raise InputError(f"table not found: {table_path}")
    try:
        delimiter = detect_delimiter(table_path)
        with table_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle, delimiter=delimiter))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise InputError(f"cannot read {table_path.name}: {exc}") from exc

    if not rows or not any(cell.strip() for cell in rows[0]):
        raise InputError(f"{table_path.name}: table has no header row")
    header = rows[0]
    if len(set(header)) != len(header):
        raise InputError(f"{table_path.name}: the header repeats a column name")

    too_long: list[str] = []
    parsed: list[dict[str, str]] = []
    data_number = 0
    for raw in rows[1:]:
        if not any(cell.strip() for cell in raw):
            continue
        data_number += 1
        if len(raw) > len(header):
            too_long.append(
                f"row {data_number}: {len(raw)} cells but the header has {len(header)} columns"
            )
            continue
        cells = raw + [""] * (len(header) - len(raw))
        parsed.append(dict(zip(header, cells, strict=True)))
    if too_long:
        raise InputError(
            f"{table_path.name}: some rows have more cells than the header",
            details=too_long,
        )
    return header, parsed
