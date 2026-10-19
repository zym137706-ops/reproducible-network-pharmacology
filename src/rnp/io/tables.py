"""Delimited-table helpers shared by the pipeline commands."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..errors import InputError


def detect_delimiter(path: Path) -> str:
    """Return ``\\t`` or ``,`` based on the header line (tabs win on ties)."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        header = handle.readline()
    return "\t" if header.count("\t") >= header.count(",") else ","


def read_table(path: str | Path) -> list[dict[str, str]]:
    """Read a TSV/CSV with a header row into plain string dictionaries."""
    table_path = Path(path)
    if not table_path.is_file():
        raise InputError(f"table not found: {table_path}")
    delimiter = detect_delimiter(table_path)
    try:
        with table_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            if not reader.fieldnames:
                raise InputError(f"{table_path.name}: table has no header row")
            return [
                {str(key): (value if value is not None else "") for key, value in row.items()}
                for row in reader
                if any((value or "").strip() for value in row.values())
            ]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise InputError(f"cannot read {table_path.name}: {exc}") from exc


def write_table(
    path: str | Path,
    rows: Iterable[dict[str, Any]],
    columns: list[str],
    *,
    delimiter: str = "\t",
) -> None:
    """Write rows in a fixed column order, UTF-8 without BOM (Cytoscape-friendly)."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    materialised = list(rows)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            delimiter=delimiter,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(materialised)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def name_key(value: str) -> str:
    """Normalise a compound/file name for matching (case- and punctuation-insensitive)."""
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).casefold())
