"""Freeze one acquisition run and verify a frozen directory offline (ADR-0005).

The record is written last, so a directory without it is an interrupted run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator

from ..config import load_schema, validate_document
from ..errors import ConfigError, InputError, SchemaViolation
from ..provenance import DIST_NAME, package_version, sha256_file, utc_now_iso, write_json
from .endpoints import (
    PDB_ID_REGEX,
    ROLES,
    UNIPROT_ACCESSION_REGEX,
    is_pdb_id,
    is_uniprot_accession,
)
from .retrieve import retrieve
from .transport import DEFAULT_TIMEOUT, Fetcher, urllib_fetcher

RECORD_FILENAME = "acquisition_record.json"
FROZEN_FILE = {
    "structure_mmcif": "{key}/{key}.cif",
    "rcsb_entry": "{key}/rcsb_entry.json",
    "rcsb_graphql": "{key}/rcsb_graphql.json",
    "uniprot_entry": "uniprot/{key}.json",
}


@dataclass(frozen=True)
class AcquisitionResult:
    """The written record plus the directory and record path it was written to."""

    status: str
    record: dict
    out_dir: Path
    record_path: Path


def _slot(role: str, pdb_id: str, accession: str) -> tuple[str, str]:
    return (role, accession if role == "uniprot_entry" else pdb_id)


def _validated_items(items) -> list[tuple[str, str]]:
    """Return the accepted (pdb_id, accession) pairs or raise one InputError."""
    if not items:
        raise InputError("invalid acquisition input", details=["no items given"])
    problems: list[str] = []
    accepted: list[tuple[str, str]] = []
    first_seen: dict[tuple[str, str], int] = {}
    for number, item in enumerate(items, 1):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            problems.append(f"item {number}: expected (pdb_id, uniprot_accession)")
            continue
        pdb_id, accession = item
        good_pdb = is_pdb_id(pdb_id)
        good_accession = is_uniprot_accession(accession)
        if not good_pdb:
            problems.append(f"item {number}: PDB ID {pdb_id!r} must match {PDB_ID_REGEX}")
        if not good_accession:
            problems.append(
                f"item {number}: UniProt accession {accession!r} must be a canonical "
                f"accession without an isoform suffix ({UNIPROT_ACCESSION_REGEX})"
            )
        if not (good_pdb and good_accession):
            continue
        pair = (pdb_id, accession)
        if pair in first_seen:
            problems.append(f"item {number}: duplicate of item {first_seen[pair]}")
        else:
            first_seen[pair] = number
            accepted.append(pair)
    if problems:
        raise InputError("invalid acquisition input", details=problems)
    return accepted


def _check_destination(destination: Path) -> None:
    if not destination.exists():
        return
    if not destination.is_dir():
        raise InputError(f"output path exists and is not a directory: {destination}")
    if any(destination.iterdir()):
        raise InputError(f"output directory is not empty: {destination}")


def _default_acquisition_id(started_at: str, pairs: list[tuple[str, str]]) -> str:
    listing = "\n".join(f"{pdb}:{accession}" for pdb, accession in sorted(pairs))
    digest = hashlib.sha256(listing.encode("utf-8")).hexdigest()
    return started_at.replace("-", "").replace(":", "") + "_" + digest[:8]


def acquire(
    items,
    out_dir,
    *,
    fetcher: Fetcher = urllib_fetcher,
    now=utc_now_iso,
    timeout: float = DEFAULT_TIMEOUT,
    acquisition_id: str | None = None,
) -> AcquisitionResult:
    """Retrieve and freeze every record of every item, then write the record."""
    pairs = _validated_items(items)
    destination = Path(out_dir)
    _check_destination(destination)

    started_at = now()
    run_id = acquisition_id or _default_acquisition_id(started_at, pairs)
    known: dict[tuple[str, str], tuple[str, object]] = {}
    requests: list[dict] = []
    warnings: list[str] = []
    record_items: list[dict] = []

    for number, (pdb_id, accession) in enumerate(pairs, 1):
        request_ids: list[str] = []
        for role in ROLES:
            slot = _slot(role, pdb_id, accession)
            if slot not in known:
                retrieval = retrieve(role, slot[1], fetcher=fetcher, now=now, timeout=timeout)
                request_id = f"r{len(requests) + 1}"
                frozen_file = None
                if retrieval.ok:
                    frozen_file = FROZEN_FILE[role].format(key=slot[1])
                    path = destination / frozen_file
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb") as handle:
                        handle.write(retrieval.body)
                else:
                    warnings.append(retrieval.message)
                requests.append(retrieval.as_request(request_id, frozen_file))
                known[slot] = (request_id, retrieval)
            request_ids.append(known[slot][0])
        complete = all(known[_slot(role, pdb_id, accession)][1].ok for role in ROLES)
        record_items.append(
            {
                "item_id": f"i{number}",
                "pdb_id": pdb_id,
                "uniprot_accession": accession,
                "status": "complete" if complete else "failed",
                "request_ids": request_ids,
            }
        )

    finished_at = now()
    complete_items = sum(1 for item in record_items if item["status"] == "complete")
    if complete_items == len(record_items):
        status = "complete"
    elif complete_items == 0:
        status = "failed"
    else:
        status = "partial"

    record = {
        "schema_version": "1.0",
        "acquisition_id": run_id,
        "tool": {"name": DIST_NAME, "version": package_version()},
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "status": status,
        "items": record_items,
        "requests": requests,
        "warnings": warnings,
    }
    try:
        validate_document(record, "acquisition_record", "acquisition record")
    except ConfigError as error:
        raise SchemaViolation(
            "the acquisition record built by rnp does not satisfy its schema",
            details=error.details,
        ) from error

    record_path = destination / RECORD_FILENAME
    write_json(record_path, record)
    return AcquisitionResult(
        status=status,
        record=record,
        out_dir=destination,
        record_path=record_path,
    )


def verify_acquisition(directory) -> list[str]:
    """Check a frozen directory against its record without writing anything."""
    root = Path(directory)
    if not root.is_dir():
        return [f"{root}: not a directory"]
    record_path = root / RECORD_FILENAME
    if not record_path.is_file():
        return [f"{RECORD_FILENAME}: missing in {root}"]
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return [f"{RECORD_FILENAME}: cannot be read as JSON: {error}"]

    validator = Draft202012Validator(load_schema("acquisition_record"))
    problems = sorted(
        validator.iter_errors(record),
        key=lambda error: ([str(part) for part in error.absolute_path], error.message),
    )
    if problems:
        rendered = []
        for error in problems:
            location = "/".join(str(part) for part in error.absolute_path) or "<root>"
            rendered.append(f"schema: {location}: {error.message}")
        return rendered

    return _cross_record_problems(record) + _file_problems(root, record)


def _cross_record_problems(record) -> list[str]:
    requests = record["requests"]
    items = record["items"]
    by_id = {entry["request_id"]: entry for entry in requests}
    problems: list[str] = []

    counts: dict[str, int] = {}
    for entry in requests:
        counts[entry["request_id"]] = counts.get(entry["request_id"], 0) + 1
    for request_id in sorted(name for name, count in counts.items() if count > 1):
        problems.append(f"requests: duplicate request_id {request_id}")

    referenced: set[str] = set()
    for item in items:
        referenced.update(item["request_ids"])
        missing = [name for name in item["request_ids"] if name not in by_id]
        for request_id in missing:
            problems.append(f"{item['item_id']}: request_id {request_id} is not in requests")
        if missing:
            continue
        outcomes = [by_id[name]["outcome"] for name in item["request_ids"]]
        derived = "complete" if all(outcome == "ok" for outcome in outcomes) else "failed"
        if derived != item["status"]:
            problems.append(
                f"{item['item_id']}: status is {item['status']} but its requests give {derived}"
            )

    for entry in requests:
        if entry["request_id"] not in referenced:
            problems.append(f"{entry['request_id']} {entry['url']}: not referenced by any item")

    frozen_uses: dict[str, int] = {}
    for entry in requests:
        frozen = entry["frozen_file"]
        if frozen is not None:
            frozen_uses[frozen] = frozen_uses.get(frozen, 0) + 1
    for frozen in sorted(path for path, count in frozen_uses.items() if count > 1):
        problems.append(f"requests: frozen_file {frozen} is used by more than one request")
    return problems


def _file_problems(root: Path, record) -> list[str]:
    problems: list[str] = []
    listed: set[str] = set()
    for entry in record["requests"]:
        frozen = entry["frozen_file"]
        if frozen is None:
            continue
        listed.add(frozen)
        label = f"{entry['request_id']} {entry['url']}"
        path = root / frozen
        if not path.is_file():
            problems.append(f"{label}: frozen file {frozen} is missing")
            continue
        actual_size = path.stat().st_size
        if actual_size != entry["bytes"]:
            problems.append(
                f"{label}: {frozen} has {actual_size} bytes, "
                f"the record says {entry['bytes']}"
            )
        actual_digest = sha256_file(path)
        if actual_digest != entry["sha256"]:
            problems.append(
                f"{label}: sha256 of {frozen} is {actual_digest}, "
                f"the record says {entry['sha256']}"
            )

    expected = {RECORD_FILENAME} | listed
    actual = sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    )
    for relative in actual:
        if relative not in expected:
            problems.append(f"{relative}: unexpected file not listed in the record")
    return problems
