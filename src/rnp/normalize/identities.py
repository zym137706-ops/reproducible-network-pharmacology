"""Stable compound identity registry (v0.1 migration scope).

The registry persists ``compound_id`` values so that downstream tables do not
depend on row order or on a display name. v0.1 deliberately does **not** register
chemical structures: a name-only migration is recorded as such and must not be
presented as a verified structure identity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..errors import InputError
from ..io.tables import clean_text, name_key, read_table
from ..provenance import utc_now_iso

RULE_VERSION = "v0.1.0-name-registry"
_ID_PATTERN = re.compile(r"^CMP(\d{4,})$")
REGISTRY_COLUMNS = [
    "compound_id",
    "group",
    "name",
    "stp_file",
    "submission_id",
    "identity_basis",
    "rule_version",
    "first_seen_utc",
    "last_seen_utc",
    "status",
]


@dataclass(frozen=True)
class CompoundRecord:
    compound_id: str
    group: str
    name: str
    stp_file: str
    submission_id: str
    identity_basis: str


def _read_registry(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    rows = read_table(path)
    if rows and "compound_id" not in rows[0]:
        raise InputError(f"{path.name}: registry has no compound_id column")
    return rows


def _allocate_id(used_ids: set[str]) -> str:
    """Next free ``CMPnnnn`` that is not already used or reserved."""
    maximum = 0
    for value in used_ids:
        match = _ID_PATTERN.match(clean_text(value))
        if match:
            maximum = max(maximum, int(match.group(1)))
    candidate = maximum + 1
    while f"CMP{candidate:04d}" in used_ids:
        candidate += 1
    return f"CMP{candidate:04d}"


def register_compounds(
    compounds_path: str | Path,
    registry_path: str | Path,
    *,
    allow_filename_match: bool = False,
) -> tuple[list[CompoundRecord], list[dict[str, str]], list[dict[str, str]]]:
    """Resolve every input row to a persistent ``compound_id``.

    Returns ``(records, registry_rows, notes)``. The caller persists the registry
    only after the run has produced usable output.
    """
    compounds = read_table(compounds_path)
    if not compounds:
        raise InputError(f"{Path(compounds_path).name}: compound table is empty")
    if "name" not in compounds[0]:
        raise InputError(f"{Path(compounds_path).name}: compound table needs a 'name' column")

    registry_path = Path(registry_path)
    registry_rows = _read_registry(registry_path)
    by_name = {
        (clean_text(row.get("group")) or "all", clean_text(row.get("name"))): row
        for row in registry_rows
    }
    by_name_casefold = {
        (clean_text(row.get("group")) or "all", clean_text(row.get("name")).casefold()): row
        for row in registry_rows
    }
    by_file = {clean_text(row.get("stp_file")): row for row in registry_rows if row.get("stp_file")}
    reserved_explicit = {
        clean_text(row.get("compound_id"))
        for row in compounds
        if clean_text(row.get("compound_id"))
    }
    used_ids = {
        clean_text(row.get("compound_id")) for row in registry_rows if row.get("compound_id")
    } | reserved_explicit

    notes: list[dict[str, str]] = []
    records: list[CompoundRecord] = []
    explicit_seen: set[str] = set()
    seen_names: set[tuple[str, str]] = set()
    seen_files: set[str] = set()
    for row in compounds:
        name = clean_text(row.get("name"))
        if not name:
            raise InputError(f"{Path(compounds_path).name}: row with empty compound name")
        group = clean_text(row.get("group")) or "all"
        stp_file = clean_text(row.get("stp_file"))
        explicit_id = clean_text(row.get("compound_id"))
        submission_id = clean_text(row.get("submission_id")) or (
            f"STP-{Path(stp_file).stem}" if stp_file else ""
        )
        name_key_pair = (group, name)
        folded = (group.casefold(), name.casefold())
        if folded in seen_names:
            raise InputError(f"duplicate compound name within group {group!r}: {name}")
        seen_names.add(folded)
        if stp_file:
            if stp_file in seen_files:
                raise InputError(f"stp_file bound to more than one compound: {stp_file}")
            seen_files.add(stp_file)
        if not stp_file and not allow_filename_match:
            raise InputError(
                f"compound {name!r} has no explicit stp_file",
                details=[
                    "bind each compound to its export with a stp_file column,",
                    "or set inputs.allow_filename_match: true for a recorded compatibility mode",
                ],
            )

        identity_basis = "new"
        record: dict[str, str] | None = by_name.get(name_key_pair)
        if explicit_id:
            if explicit_id in explicit_seen:
                raise InputError(f"compound_id repeated in input: {explicit_id}")
            explicit_seen.add(explicit_id)
            existing = next(
                (item for item in registry_rows if item.get("compound_id") == explicit_id), None
            )
            if existing is not None:
                registered_name = clean_text(existing.get("name"))
                registered_group = clean_text(existing.get("group")) or "all"
                if registered_name != name or registered_group != group:
                    raise InputError(
                        f"compound_id {explicit_id} is already registered as "
                        f"{registered_name!r} in group {registered_group!r}",
                        details=[
                            "choose a different compound_id or reconcile the registry;",
                            "an existing identity is not silently reassigned",
                        ],
                    )
                existing["stp_file"] = stp_file or clean_text(existing.get("stp_file"))
                existing["submission_id"] = submission_id or clean_text(
                    existing.get("submission_id")
                )
                existing["last_seen_utc"] = utc_now_iso()
            else:
                registry_rows.append(
                    {
                        "compound_id": explicit_id,
                        "group": group,
                        "name": name,
                        "stp_file": stp_file,
                        "submission_id": submission_id,
                        "identity_basis": "explicit",
                        "rule_version": RULE_VERSION,
                        "first_seen_utc": utc_now_iso(),
                        "last_seen_utc": utc_now_iso(),
                        "status": "active",
                    }
                )
                notes.append(
                    {
                        "code": "compound_registered_explicit",
                        "message": f"{name!r} registered with explicit id {explicit_id}",
                    }
                )
            identity_basis = "explicit"
            compound_id = explicit_id
        elif record is not None:
            compound_id = clean_text(record["compound_id"])
            identity_basis = "registry_name"
        elif (casefold := by_name_casefold.get((group, name.casefold()))) is not None:
            compound_id = clean_text(casefold["compound_id"])
            identity_basis = "registry_name_casefold"
            notes.append(
                {
                    "code": "identity_matched_case_insensitively",
                    "message": f"{name!r} matched registered identity {compound_id}",
                }
            )
        elif stp_file and stp_file in by_file:
            compound_id = clean_text(by_file[stp_file]["compound_id"])
            identity_basis = "registry_stp_file"
            notes.append(
                {
                    "code": "identity_matched_by_stp_file",
                    "message": (
                        f"{name!r} matched {compound_id} by export file; "
                        "the display name changed, the identity was kept"
                    ),
                }
            )
        else:
            compound_id = _allocate_id(used_ids)
            identity_basis = "new"
            registry_rows.append(
                {
                    "compound_id": compound_id,
                    "group": group,
                    "name": name,
                    "stp_file": stp_file,
                    "submission_id": submission_id,
                    "identity_basis": identity_basis,
                    "rule_version": RULE_VERSION,
                    "first_seen_utc": utc_now_iso(),
                    "last_seen_utc": utc_now_iso(),
                    "status": "active",
                }
            )
            notes.append(
                {
                    "code": "compound_registered",
                    "message": f"{name!r} registered as {compound_id} (name-based identity)",
                }
            )
        used_ids.add(compound_id)
        registered = next(
            (item for item in registry_rows if item.get("compound_id") == compound_id), None
        )
        if registered is not None:
            registered["last_seen_utc"] = utc_now_iso()
        records.append(
            CompoundRecord(
                compound_id=compound_id,
                group=group,
                name=name,
                stp_file=stp_file,
                submission_id=submission_id,
                identity_basis=identity_basis,
            )
        )

    if not registry_path.is_file():
        notes.append(
            {
                "code": "registry_created",
                "message": f"created compound identity registry at {registry_path}",
            }
        )
    return records, registry_rows, notes


def match_exports(
    records: list[CompoundRecord],
    files: list[Path],
    *,
    allow_filename_match: bool,
) -> tuple[dict[str, CompoundRecord], list[dict[str, str]], list[dict[str, str]]]:
    """Bind export filenames to compounds; quarantining is the caller's job.

    Returns ``(file_bindings, unbound_files, notes)`` where ``unbound_files`` are
    the exports that must be quarantined instead of becoming formal edges.
    """
    by_explicit = {record.stp_file: record for record in records if record.stp_file}
    by_name: dict[str, list[CompoundRecord]] = {}
    for record in records:
        by_name.setdefault(name_key(record.name), []).append(record)

    bindings: dict[str, CompoundRecord] = {}
    unbound: list[dict[str, str]] = []
    notes: list[dict[str, str]] = []
    for path in files:
        if path.name in by_explicit:
            bindings[path.name] = by_explicit[path.name]
            continue
        if not allow_filename_match:
            unbound.append({"path": path.name, "reason": "not_bound_to_compound"})
            continue
        candidates = by_name.get(name_key(path.stem), [])
        if len(candidates) == 1:
            bindings[path.name] = candidates[0]
            notes.append(
                {
                    "code": "filename_compatibility_match",
                    "message": (
                        f"{path.name} matched {candidates[0].name!r} by filename; "
                        "this compatibility mode is recorded in the audit"
                    ),
                }
            )
        else:
            reason = "ambiguous_filename" if candidates else "not_bound_to_compound"
            unbound.append({"path": path.name, "reason": reason})
    return bindings, unbound, notes
