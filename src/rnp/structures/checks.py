"""Cross-row checks that JSON Schema cannot express."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

_STRUCTURE_ID = re.compile(r"STR[0-9]{4,}")


def structure_number(structure_id: str) -> int:
    """Return the numeric part of a structure id, or raise ``ValueError``."""
    if not _STRUCTURE_ID.fullmatch(structure_id):
        raise ValueError(f"not a structure id: {structure_id!r}")
    return int(structure_id[3:])


def check_registry(rows: list[dict[str, str]]) -> list[str]:
    """Return consistency problems of a structure registry, in a stable order."""
    problems: list[str] = []
    id_counts = Counter(row["structure_id"] for row in rows)
    for structure_id in sorted(
        structure_id for structure_id, count in id_counts.items() if count > 1
    ):
        problems.append(f"structure_id {structure_id} appears {id_counts[structure_id]} times")

    string_counts = Counter((row["compound_id"], row["smiles"]) for row in rows)
    for compound_id, smiles in sorted(key for key, count in string_counts.items() if count > 1):
        problems.append(
            f"{compound_id} has the structure {smiles} registered "
            f"{string_counts[(compound_id, smiles)]} times"
        )

    by_compound: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_compound[row["compound_id"]].append(row)
    for compound_id in sorted(by_compound):
        current = sum(1 for row in by_compound[compound_id] if row["status"] == "current")
        if current != 1:
            problems.append(f"{compound_id} has {current} current structures, expected exactly 1")

    first_by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        first_by_id.setdefault(row["structure_id"], row)
    for number, row in enumerate(rows, start=1):
        where = f"row {number} ({row['structure_id']})"
        if row["status"] == "superseded":
            target = row["superseded_by"]
            target_row = first_by_id.get(target)
            if target_row is None:
                problems.append(f"{where}: superseded_by {target} is not in the registry")
            elif target_row["compound_id"] != row["compound_id"]:
                problems.append(f"{where}: superseded_by {target} belongs to another compound")
            elif target == row["structure_id"]:
                problems.append(f"{where}: superseded_by points to itself")

        expected_block = row["inchikey"].split("-")[0]
        if row["connectivity_block"] != expected_block:
            problems.append(f"{where}: connectivity_block is not the first block of the inchikey")
        if row["stereo_status"] == "defined" and (
            row["stereo_elements_specified"] != row["stereo_elements_total"]
        ):
            problems.append(
                f"{where}: stereo_status is defined but only "
                f"{row['stereo_elements_specified']} of {row['stereo_elements_total']} are"
            )
        if row["stereo_status"] == "partially_defined" and not (
            int(row["stereo_elements_specified"]) < int(row["stereo_elements_total"])
        ):
            problems.append(
                f"{where}: stereo_status is partially_defined but "
                f"{row['stereo_elements_specified']} of {row['stereo_elements_total']}"
            )
        if row["first_seen_utc"] > row["last_seen_utc"]:
            problems.append(f"{where}: first_seen_utc is later than last_seen_utc")
    return problems
