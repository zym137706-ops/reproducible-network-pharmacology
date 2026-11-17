#!/usr/bin/env python3
"""Independent checks for a completed rnp case run.

This reads the run's target/intersection/network/enrichment tables and re-derives the case sets and
statistics from the declared disease genes and HGNC map. It deliberately does not call the analysis
functions that produced the outputs and does not use their summary counts as the expected values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from pathlib import Path

from rnp.io.tables import read_table
from rnp.normalize.hgnc import GeneMapper

BINDING_RULE = "case-binding-recheck-v1"
CHECKED_STATUSES = ("verified", "verified_kind_unstated", "reconstructed")
DERIVED_COLUMNS = (
    "name",
    "group",
    "stp_file",
    "smiles",
    "submission_status",
    "export_kind",
    "export_sha256",
)
SELECTION_RULE = "case-selection-recheck-v1"
SELECTION_COLUMNS = (
    "decision_id",
    "compound_id",
    "group",
    "name",
    "stp_file",
    "structure_id",
    "compound_row_status",
    "decision",
    "decision_source",
    "selection_status",
    "reason_codes",
    "rules_version",
    "reviewer",
    "evidence_refs",
    "issue_codes",
)
SELECTION_DECISIONS = {"include": "selected", "exclude": "excluded", "needs_review": "needs_review"}
DECISION_ID_FIELDS = (
    "compound_id",
    "structure_id",
    "decision",
    "decision_source",
    "reason_codes",
    "rules_version",
    "reviewer",
    "evidence_refs",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bh(pvalues: list[float]) -> list[float]:
    n = len(pvalues)
    order = sorted(range(n), key=lambda i: pvalues[i])
    adjusted = [0.0] * n
    previous = 1.0
    for rank, index in enumerate(reversed(order), start=1):
        i = n - rank + 1
        value = min(previous, pvalues[index] * n / i)
        adjusted[index] = value
        previous = value
    return adjusted


def hypergeom_sf(k: int, population: int, successes: int, draws: int) -> float:
    total = math.comb(population, draws)
    upper = min(successes, draws)
    return (
        sum(
            math.comb(successes, i) * math.comb(population - successes, draws - i)
            for i in range(k, upper + 1)
        )
        / total
    )


def normalise_targets(rows: list[dict[str, str]], mapper: GeneMapper) -> set[str]:
    symbols: set[str] = set()
    for row in rows:
        if (
            str(row.get("multi_symbol_common_name", "")).lower() == "true"
            or str(row.get("is_complex", "")).lower() == "true"
        ):
            continue
        mapped = mapper.map(row.get("common_name", ""), row.get("uniprot_id", ""))
        if mapped.mapping_conflict:
            continue
        if mapped.gene_symbol:
            symbols.add(mapped.gene_symbol)
    return symbols


def check_run(
    label: str,
    run: Path,
    background_dir: Path,
    disease: set[str],
    mapper: GeneMapper,
) -> dict[str, object]:
    targets = read_table(run / "targets.tsv")
    t_r = normalise_targets(targets, mapper)
    foreground = t_r & disease
    bg_text = (background_dir / f"universe-{label}.txt").read_text(encoding="utf-8")
    fg_text = (background_dir / f"foreground-{label}.txt").read_text(encoding="utf-8")
    background = set(bg_text.split())
    if background != t_r:
        raise AssertionError(f"{label}: background T_r mismatch")
    if set(fg_text.split()) != foreground:
        raise AssertionError(f"{label}: foreground mismatch")

    intersect_audit = json.loads((run / "intersect" / "intersect_audit.json").read_text())
    group = intersect_audit["groups"]["all"]
    if group["targets"] != len(t_r):
        raise AssertionError(f"{label}: intersection target count mismatch")
    if group["intersection"] != len(foreground):
        raise AssertionError(f"{label}: intersection count mismatch")
    if len(read_table(run / "intersect" / "intersection_genes.tsv")) != group["intersection"]:
        raise AssertionError(f"{label}: intersection table row count mismatch")

    network_audit = json.loads((run / "network" / "network_audit.json").read_text())
    network = network_audit["groups"]["all"]
    if not all(network["checks"].values()):
        raise AssertionError(f"{label}: network invariant failed")

    enrich_audit = json.loads((run / "enrichment" / "enrichment_audit.json").read_text())
    enrich = enrich_audit["groups"]["all"]
    effective_fg = enrich["effective_foreground"]
    effective_bg = enrich["effective_background"]
    result_path = run / "enrichment" / "all" / "enrichment_result.tsv"
    rows = read_table(result_path)
    pvalues = []
    for row in rows:
        population = int(row["BgRatio"].split("/")[1])
        successes = int(row["BgRatio"].split("/")[0])
        if population != effective_bg:
            raise AssertionError(f"{label}: result BgRatio does not match audit background")
        p = hypergeom_sf(int(row["Count"]), population, successes, effective_fg)
        if not math.isclose(float(row["pvalue"]), p, rel_tol=1e-9, abs_tol=1e-12):
            raise AssertionError(f"{label}: p-value mismatch for {row['ID']}")
        pvalues.append(p)
    for row, expected in zip(rows, bh(pvalues), strict=True):
        if not math.isclose(float(row["p.adjust"]), expected, rel_tol=1e-8, abs_tol=1e-12):
            raise AssertionError(f"{label}: BH mismatch for {row['ID']}")

    report_audit = json.loads((run / "report" / "report_audit.json").read_text())
    return {
        "run_dir": str(run),
        "T_r": len(t_r),
        "foreground": len(foreground),
        "intersection": group["intersection"],
        "network_nodes": network["nodes"],
        "network_edges": network["edges"],
        "effective_foreground": effective_fg,
        "effective_background": effective_bg,
        "terms_tested": len(rows),
        "significant": int(enrich["significant"]),
        "enrichment_status": enrich["status"],
        "report_sha256": report_audit["report_sha256"],
        "stage_status": {
            "intersect": intersect_audit["stage_status"],
            "network": network_audit["stage_status"],
            "enrichment": enrich_audit["stage_status"],
            "report": report_audit["stage_status"],
        },
    }


def _fold_binding_cell(text: str) -> str:
    """Collapse the whitespace of a compound-table cell the way the core reads it."""
    return " ".join(text.replace("\u00a0", " ").split())


def _read_binding_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read one table with the binding rules and return its header and its non-empty rows."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        text = handle.read()
    header_line = text.split("\n", 1)[0]
    delimiter = "\t" if header_line.count("\t") >= header_line.count(",") else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows or not any(cell.strip() for cell in rows[0]):
        raise AssertionError(f"{path.name}: the table has no header row")
    header = rows[0]
    table: list[dict[str, str]] = []
    for row in rows[1:]:
        if len(row) > len(header):
            raise AssertionError(f"{path.name}: a row has more cells than the header has columns")
        cells = row + [""] * (len(header) - len(row))
        table.append(dict(zip(header, cells, strict=True)))
    return header, table


def _compound_binding_rows(path: Path) -> list[dict[str, str]]:
    """Read the compound table and clean the columns that the binding rules compare."""
    header, rows = _read_binding_table(path)
    for column in ("name", "smiles"):
        if column not in header:
            raise AssertionError(f"{path.name}: the compound table has no {column!r} column")
    table = []
    for row in rows:
        table.append(
            {
                "name": _fold_binding_cell(row.get("name", "")),
                "group": _fold_binding_cell(row.get("group", "")) or "all",
                "stp_file": _fold_binding_cell(row.get("stp_file", "")),
                "pubchem_cid": _fold_binding_cell(row.get("pubchem_cid", "")),
                "smiles": row.get("smiles", "").strip(),
            }
        )
    return table


def _submission_log_rows(path: Path) -> list[dict[str, str]]:
    """Read the submission log, require its columns and refuse a repeated export."""
    header, rows = _read_binding_table(path)
    required = ("stp_file", "submitted_structure", "species", "submitted_date")
    missing = [column for column in required if column not in header]
    if missing:
        raise AssertionError(
            f"{path.name}: the submission log lacks required column(s): {', '.join(missing)}"
        )
    if len(set(header)) != len(header):
        raise AssertionError(f"{path.name}: the header repeats a column name")
    table = []
    seen: set[str] = set()
    for row in rows:
        cells = {column: value.strip() for column, value in row.items()}
        export = cells.get("stp_file", "")
        if export:
            if export in seen:
                raise AssertionError(f"{path.name}: stp_file {export!r} appears more than once")
            seen.add(export)
        table.append(cells)
    return table


def _derive_compounds(
    compounds: Path, stp_dir: Path, log: Path, species: str
) -> tuple[list[dict[str, object]], int, list[dict[str, str]]]:
    """Derive the submission status, export kind and export hash of every compound."""
    table = _compound_binding_rows(compounds)
    log_rows = _submission_log_rows(log)
    by_file = {row.get("stp_file", ""): row for row in log_rows if row.get("stp_file", "")}
    expected_species = species.replace("_", " ")
    derived: list[dict[str, object]] = []
    hashed = 0
    for compound in table:
        name = compound["name"]
        stp_file = compound["stp_file"]
        smiles = compound["smiles"]
        export = stp_dir / stp_file if stp_file else None
        export_sha256 = sha256(export) if export is not None and export.is_file() else ""
        row = by_file.get(stp_file) if stp_file else None
        record: dict[str, object] = {
            "name": name,
            "group": compound["group"],
            "stp_file": stp_file,
            "smiles": smiles,
            "submission_status": "",
            "export_kind": "",
            "export_sha256": "",
            "reasons": [],
            "log_row": row,
        }
        if not smiles:
            record["submission_status"] = "not_checked"
        elif row is None:
            record["submission_status"] = "not_recorded"
        else:
            reasons = []
            if row.get("compound") and row["compound"] != name:
                reasons.append("compound")
            if (
                row.get("pubchem_cid")
                and compound["pubchem_cid"]
                and row["pubchem_cid"] != compound["pubchem_cid"]
            ):
                reasons.append("pubchem_cid")
            if row.get("submitted_structure", "") != smiles:
                reasons.append("submitted_structure")
            if row.get("species", "") != expected_species:
                reasons.append("species")
            if Path(stp_file).name != stp_file or export is None or not export.is_file():
                reasons.append("stp_file")
            if (
                export is not None
                and export.is_file()
                and row.get("result_sha256")
                and row["result_sha256"] != export_sha256
            ):
                reasons.append("result_sha256")
            record["reasons"] = reasons
            record["export_sha256"] = export_sha256
            if reasons:
                record["submission_status"] = "rejected"
            else:
                kind = row.get("export_kind", "")
                record["export_kind"] = kind
                record["submission_status"] = {
                    "": "verified_kind_unstated",
                    "native_export": "verified",
                    "reconstructed_from_result_page": "reconstructed",
                }.get(kind, "unknown_export_kind")
            if export is not None and export.is_file():
                hashed += 1
        derived.append(record)
    return derived, hashed, log_rows


def _binding_input_problems(
    compounds: Path,
    log: Path,
    derived: list[dict[str, object]],
    log_rows: list[dict[str, str]],
) -> list[str]:
    """Return one line per input problem, in compound-table order and then for orphan log rows."""
    lines = []
    for record in derived:
        entry = f"entry {record['name']!r} ({record['stp_file']})"
        status = record["submission_status"]
        if status == "not_checked":
            lines.append(f"{compounds.name}: {entry} smiles: empty, so no structure was submitted")
        elif status == "not_recorded":
            lines.append(
                f"{log.name}: {entry} stp_file: no submission log row belongs to this compound"
            )
        elif status == "rejected":
            reasons = ", ".join(record["reasons"])
            lines.append(
                f"{log.name}: {entry} submission_status: derived 'rejected' from the inputs "
                f"({reasons}), not a checked submission"
            )
        elif status not in CHECKED_STATUSES:
            lines.append(
                f"{log.name}: {entry} export_kind: {record['export_kind']!r} "
                "is not a known export kind"
            )
        row = record["log_row"]
        if (
            row is not None
            and not row.get("result_sha256")
            and record["export_sha256"]
        ):
            lines.append(f"{log.name}: {entry} result_sha256: the log does not declare it")
    known = {record["stp_file"] for record in derived}
    for number, row in enumerate(log_rows, start=1):
        export = row.get("stp_file", "")
        if export and export not in known:
            lines.append(
                f"{log.name}: row {number} stp_file: no compound row has stp_file {export!r}"
            )
    return lines


def _binding_value(document: object, path: str) -> object:
    """Read a dotted path from a JSON document, returning None when it is absent."""
    value = document
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _threshold_binding_problems(
    label: str,
    stage_dir: Path,
    run_dir: Path,
    derived: list[dict[str, object]],
    hashed: int,
    compounds_sha256: str,
    log_sha256: str,
    log_rows: int,
) -> tuple[list[str], str | None]:
    """Compare the four files of one threshold with the derived bindings."""
    files = (
        ("compound_structures.tsv", stage_dir / "compound_structures.tsv"),
        ("compounds_audit.json", stage_dir / "compounds_audit.json"),
        ("compounds_registered.tsv", run_dir / "compounds_registered.tsv"),
        ("stp_audit.json", run_dir / "stp_audit.json"),
    )
    missing = [(name, path) for name, path in files if not path.is_file()]
    if missing:
        return [f"{label}: {name}: not found in {path.parent}" for name, path in missing], None

    stage_path = stage_dir / "compound_structures.tsv"
    audit_path = stage_dir / "compounds_audit.json"
    registered_path = run_dir / "compounds_registered.tsv"
    ingest_path = run_dir / "stp_audit.json"
    stage_sha256 = sha256(stage_path)
    _, stage_rows = _read_binding_table(stage_path)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    _, registered_rows = _read_binding_table(registered_path)
    ingest = json.loads(ingest_path.read_text(encoding="utf-8"))
    lines: list[str] = []
    if len(stage_rows) != len(derived):
        lines.append(
            f"{label}: compound_structures.tsv: rows: expected {len(derived)} "
            f"from the compound table, found {len(stage_rows)}"
        )
    compound_ids: set[str] = set()
    structure_ids: set[str] = set()
    for compound, row in zip(derived, stage_rows, strict=False):
        entry = f"entry {compound['name']!r} ({compound['stp_file']})"
        for column in DERIVED_COLUMNS:
            expected = compound[column]
            actual = row.get(column)
            if actual != expected:
                lines.append(
                    f"{label}: compound_structures.tsv: {entry} {column}: "
                    f"expected {expected!r} from the inputs, found {actual!r}"
                )
        actual = row.get("row_status")
        if actual != "accepted":
            lines.append(
                f"{label}: compound_structures.tsv: {entry} row_status: "
                f"{actual!r}, not 'accepted'"
            )
        actual = row.get("structure_status")
        if actual != "registered":
            lines.append(
                f"{label}: compound_structures.tsv: {entry} structure_status: "
                f"{actual!r}, not 'registered'"
            )
        value = row.get("compound_id", "")
        if not value or value in compound_ids:
            lines.append(
                f"{label}: compound_structures.tsv: {entry} compound_id: "
                f"{value!r} is empty or repeated"
            )
        compound_ids.add(value)
        value = row.get("structure_id", "")
        if not re.fullmatch(r"STR[0-9]{4,}", value) or value in structure_ids:
            lines.append(
                f"{label}: compound_structures.tsv: {entry} structure_id: "
                f"{value!r} is not a structure id or is repeated"
            )
        structure_ids.add(value)
        inchikey = row.get("inchikey")
        if inchikey is None or not re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", inchikey):
            lines.append(
                f"{label}: compound_structures.tsv: {entry} inchikey: "
                f"{inchikey!r} is not an InChIKey"
            )

    accepted = sum(1 for row in stage_rows if row.get("row_status") == "accepted")
    quarantined = sum(1 for row in stage_rows if row.get("row_status") == "quarantined")
    statuses = [compound["submission_status"] for compound in derived]
    verified = sum(1 for status in statuses if status in ("verified", "verified_kind_unstated"))
    checks = (
        ("identity_mode", "structure", "the case policy"),
        ("stage_status", "complete", "the case policy"),
        ("inputs.compounds.sha256", compounds_sha256, "the inputs"),
        ("inputs.compounds.rows", len(derived), "the inputs"),
        ("inputs.submission_log.sha256", log_sha256, "the inputs"),
        ("inputs.submission_log.rows", log_rows, "the inputs"),
        ("inputs.stp_dir.files_hashed", hashed, "the inputs"),
        ("compound_structures_sha256", stage_sha256, "compound_structures.tsv"),
        ("summary.rows", len(derived), "the inputs"),
        ("summary.rows_accepted", accepted, "compound_structures.tsv"),
        ("summary.rows_quarantined", quarantined, "compound_structures.tsv"),
        ("summary.rows_name_only", 0, "the case policy"),
        ("summary.submissions_verified", verified, "the inputs"),
        ("summary.submissions_reconstructed", statuses.count("reconstructed"), "the inputs"),
        ("summary.submissions_not_recorded", statuses.count("not_recorded"), "the inputs"),
        ("summary.submissions_rejected", statuses.count("rejected"), "the inputs"),
        ("summary.errors", 0, "the case policy"),
    )
    for field, expected, source in checks:
        actual = _binding_value(audit, field)
        if actual != expected:
            lines.append(
                f"{label}: compounds_audit.json: {field}: expected {expected!r} "
                f"from {source}, found {actual!r}"
            )

    if len(registered_rows) != len(derived):
        lines.append(
            f"{label}: compounds_registered.tsv: rows: expected {len(derived)} "
            f"from the compound table, found {len(registered_rows)}"
        )
    for index, (compound, row) in enumerate(zip(derived, registered_rows, strict=False)):
        entry = f"entry {compound['name']!r} ({compound['stp_file']})"
        for column in ("name", "group", "stp_file"):
            expected = compound[column]
            actual = row.get(column)
            if actual != expected:
                lines.append(
                    f"{label}: compounds_registered.tsv: {entry} {column}: "
                    f"expected {expected!r} from the inputs, found {actual!r}"
                )
        for column in ("compound_id", "structure_id", "structure_status"):
            expected = stage_rows[index].get(column) if index < len(stage_rows) else None
            actual = row.get(column)
            if actual != expected:
                lines.append(
                    f"{label}: compounds_registered.tsv: {entry} {column}: "
                    f"expected {expected!r} from compound_structures.tsv, found {actual!r}"
                )
    registered_sha256 = sha256(registered_path)
    actual = ingest.get("compounds_registered_sha256") if isinstance(ingest, dict) else None
    if actual != registered_sha256:
        lines.append(
            f"{label}: stp_audit.json: compounds_registered_sha256: "
            f"expected {registered_sha256!r} from compounds_registered.tsv, found {actual!r}"
        )
    return lines, stage_sha256


def check_bindings(
    compounds: Path,
    stp_dir: Path,
    log: Path,
    species: str,
    stages: dict[str, Path],
    runs: dict[str, Path],
) -> dict[str, object]:
    """Re-derive the submission bindings from the raw inputs and compare every compounds stage."""
    derived, hashed, log_rows = _derive_compounds(compounds, stp_dir, log, species)
    compounds_sha256 = sha256(compounds)
    log_sha256 = sha256(log)
    problems = _binding_input_problems(compounds, log, derived, log_rows)
    readable: dict[str, str] = {}
    for label in sorted(stages):
        lines, stage_sha256 = _threshold_binding_problems(
            label,
            stages[label],
            runs[label],
            derived,
            hashed,
            compounds_sha256,
            log_sha256,
            len(log_rows),
        )
        problems.extend(lines)
        if stage_sha256 is not None:
            readable[label] = stage_sha256
    ordered = sorted(readable)
    if ordered:
        first = ordered[0]
        for label in ordered[1:]:
            if readable[label] != readable[first]:
                problems.append(
                    f"{label}: compound_structures.tsv: sha256: expected {readable[first]!r} "
                    f"from the stage of threshold {first}, found {readable[label]!r}"
                )
    if problems:
        raise AssertionError("\n".join(problems))
    counts: dict[str, int] = {}
    for compound in derived:
        status = str(compound["submission_status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "rule": BINDING_RULE,
        "species": species.replace("_", " "),
        "compounds_sha256": compounds_sha256,
        "submission_log_sha256": log_sha256,
        "rows": len(derived),
        "submission_status_counts": {status: counts[status] for status in sorted(counts)},
        "derived_columns": list(DERIVED_COLUMNS),
        "thresholds": {
            label: {"stage_table_sha256": readable[label]} for label in sorted(readable)
        },
    }


def _selection_name_key(text: str) -> str:
    """Fold a compound name to the key the core pairs a decision with."""
    return re.sub(r"[^a-z0-9]+", "", _fold_binding_cell(text).casefold())


def _selection_codes(text: str) -> str:
    """Normalise reason codes the way the core records them."""
    return ";".join(sorted({part.strip() for part in text.split(";") if part.strip()}))


def _selection_id(row: dict[str, str]) -> str:
    """`DEC-` and the first 12 hex digits of the eight decision fields joined by U+001F."""
    text = "\x1f".join(row[field] for field in DECISION_ID_FIELDS)
    return "DEC-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _read_decisions(decisions: Path) -> list[dict[str, str]]:
    """Read the decision table with the binding rules and clean the fields it compares."""
    header, rows = _read_binding_table(decisions)
    required = ("compound", "decision", "reason_codes", "rules_version", "reviewer")
    missing = [column for column in required if column not in header]
    if missing:
        raise AssertionError(
            f"{decisions.name}: the decision table lacks required column(s): {', '.join(missing)}"
        )
    table = []
    for row in rows:
        table.append(
            {
                "compound": _fold_binding_cell(row.get("compound", "")),
                "group": _fold_binding_cell(row.get("group", "")) or "all",
                "decision": row.get("decision", "").strip(),
                "reason_codes": _selection_codes(row.get("reason_codes", "")),
                "rules_version": _fold_binding_cell(row.get("rules_version", "")),
                "reviewer": _fold_binding_cell(row.get("reviewer", "")),
                "evidence_refs": _fold_binding_cell(row.get("evidence_refs", "")),
            }
        )
    return table


def _selection_pairs(
    source: str, compounds: list[dict[str, str]], decisions: list[dict[str, str]]
) -> tuple[list[str], dict[int, int]]:
    """Pair every decision with a compound and hold the table to the case policy."""
    problems: list[str] = []
    by_key: dict[tuple[str, str], int] = {}
    for index, compound in enumerate(compounds):
        key = (_selection_name_key(compound["name"]), compound["group"])
        by_key.setdefault(key, index)
    paired: dict[int, int] = {}
    for number, decision in enumerate(decisions, start=1):
        value = decision["decision"]
        if value not in SELECTION_DECISIONS:
            problems.append(
                f"{source}: row {number} decision: {value!r} "
                "is not include, exclude or needs_review"
            )
            continue
        key = (_selection_name_key(decision["compound"]), decision["group"])
        index = by_key.get(key)
        if index is None:
            problems.append(
                f"{source}: row {number} compound: no compound row matches "
                f"{decision['compound']!r} (group {decision['group']!r})"
            )
            continue
        if index in paired:
            problems.append(
                f"{source}: row {number} compound: {decision['compound']!r} "
                f"(group {decision['group']!r}) is decided more than once"
            )
            continue
        paired[index] = number - 1
    for index, compound in enumerate(compounds):
        entry = f"entry {compound['name']!r} ({compound['stp_file']})"
        if index not in paired:
            problems.append(
                f"{source}: {entry} decision: no decision is recorded, "
                "so the candidate is held for review"
            )
        elif decisions[paired[index]]["decision"] == "needs_review":
            problems.append(
                f"{source}: {entry} decision: needs_review, not a decided candidate"
            )
    if not any(decisions[at]["decision"] == "include" for at in paired.values()):
        problems.append(f"{source}: no compound is selected")
    return problems, paired


def _selection_expected(
    compounds: list[dict[str, str]],
    decisions: list[dict[str, str]],
    paired: dict[int, int],
    stage_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Derive the selection row of every compound from the inputs and its compounds stage."""
    expected = []
    for index, compound in enumerate(compounds):
        stage = stage_rows[index] if index < len(stage_rows) else {}
        at = paired.get(index)
        row = {column: "" for column in SELECTION_COLUMNS}
        row["compound_id"] = stage.get("compound_id", "")
        row["structure_id"] = stage.get("structure_id", "")
        row["compound_row_status"] = stage.get("row_status", "")
        row["group"] = compound["group"]
        row["name"] = compound["name"]
        row["stp_file"] = compound["stp_file"]
        if at is None:
            row["decision"] = "needs_review"
            row["decision_source"] = "not_recorded"
            row["issue_codes"] = "no_decision_recorded"
        else:
            decision = decisions[at]
            row["decision"] = decision["decision"]
            row["decision_source"] = "recorded"
            row["reason_codes"] = decision["reason_codes"]
            row["rules_version"] = decision["rules_version"]
            row["reviewer"] = decision["reviewer"]
            row["evidence_refs"] = decision["evidence_refs"]
        row["selection_status"] = SELECTION_DECISIONS.get(row["decision"], "needs_review")
        row["decision_id"] = _selection_id(row)
        expected.append(row)
    return expected


def _selection_cell_problems(
    label: str,
    filename: str,
    entries: list[str],
    columns: tuple[str, ...],
    expected: list[dict[str, str]],
    actual: list[dict[str, str]],
    source: str,
) -> list[str]:
    """Compare the cells of the rows that both tables have."""
    lines: list[str] = []
    for index in range(min(len(expected), len(actual))):
        for column in columns:
            if actual[index].get(column) != expected[index][column]:
                lines.append(
                    f"{label}: {filename}: {entries[index]} {column}: "
                    f"expected {expected[index][column]!r} from {source}, "
                    f"found {actual[index].get(column)!r}"
                )
    return lines


def _threshold_selection_problems(
    label: str,
    compounds: list[dict[str, str]],
    decisions: Path,
    decision_rows: list[dict[str, str]],
    paired: dict[int, int],
    stage_dir: Path,
    selection_dir: Path,
    run_dir: Path,
) -> tuple[list[str], dict[str, str] | None]:
    """Compare the files of one threshold with the derivation; return lines and hashes."""
    files = (
        ("compounds_audit.json", stage_dir / "compounds_audit.json"),
        ("compound_structures.tsv", stage_dir / "compound_structures.tsv"),
        ("selection_decisions.tsv", selection_dir / "selection_decisions.tsv"),
        ("selected_compounds.tsv", selection_dir / "selected_compounds.tsv"),
        ("selection_audit.json", selection_dir / "selection_audit.json"),
        ("compounds_registered.tsv", run_dir / "compounds_registered.tsv"),
        ("stp_audit.json", run_dir / "stp_audit.json"),
        ("targets.tsv", run_dir / "targets.tsv"),
        ("intersect_audit.json", run_dir / "intersect" / "intersect_audit.json"),
    )
    missing = [(name, path) for name, path in files if not path.is_file()]
    if missing:
        return [f"{label}: {name}: not found in {path.parent}" for name, path in missing], None

    _, stage_rows = _read_binding_table(stage_dir / "compound_structures.tsv")
    expected = _selection_expected(compounds, decision_rows, paired, stage_rows)
    entries = [f"entry {compound['name']!r} ({compound['stp_file']})" for compound in compounds]
    lines = []
    table_path = selection_dir / "selection_decisions.tsv"
    _, table_rows = _read_binding_table(table_path)
    if len(table_rows) != len(expected):
        lines.append(
            f"{label}: selection_decisions.tsv: rows: expected {len(expected)} "
            f"from the compound table, found {len(table_rows)}"
        )
    lines += _selection_cell_problems(
        label,
        "selection_decisions.tsv",
        entries,
        SELECTION_COLUMNS,
        expected,
        table_rows,
        "the inputs",
    )
    chosen = [
        (index, row)
        for index, row in enumerate(expected)
        if row["selection_status"] == "selected"
    ]
    chosen_path = selection_dir / "selected_compounds.tsv"
    _, chosen_rows = _read_binding_table(chosen_path)
    if len(chosen_rows) != len(chosen):
        lines.append(
            f"{label}: selected_compounds.tsv: rows: expected {len(chosen)} selected, "
            f"found {len(chosen_rows)}"
        )
    lines += _selection_cell_problems(
        label,
        "selected_compounds.tsv",
        [entries[index] for index, _ in chosen],
        SELECTION_COLUMNS,
        [row for _, row in chosen],
        chosen_rows,
        "the inputs",
    )
    counts = Counter(row["selection_status"] for row in expected)
    audit = json.loads((selection_dir / "selection_audit.json").read_text(encoding="utf-8"))
    table_sha256 = sha256(table_path)
    chosen_sha256 = sha256(chosen_path)
    checks = (
        ("stage_status", "complete", "the case policy"),
        ("identity_mode", "structure", "the case policy"),
        ("inputs.selection.sha256", sha256(decisions), "the inputs"),
        ("inputs.selection.rows", len(decision_rows), "the inputs"),
        (
            "inputs.compounds_stage.audit_sha256",
            sha256(stage_dir / "compounds_audit.json"),
            "the compounds stage",
        ),
        (
            "inputs.compounds_stage.table_sha256",
            sha256(stage_dir / "compound_structures.tsv"),
            "the compounds stage",
        ),
        ("summary.candidates", len(compounds), "the inputs"),
        ("summary.selected", counts.get("selected", 0), "the inputs"),
        ("summary.excluded", counts.get("excluded", 0), "the inputs"),
        ("summary.needs_review", counts.get("needs_review", 0), "the inputs"),
        ("summary.quarantined", 0, "the case policy"),
        ("summary.decisions_recorded", len(decision_rows), "the inputs"),
        ("summary.decisions_not_recorded", 0, "the case policy"),
        ("summary.decisions_without_compound", 0, "the case policy"),
        ("summary.warnings", 0, "the case policy"),
        ("issues", [], "the case policy"),
        ("selection_decisions_sha256", table_sha256, "selection_decisions.tsv"),
        ("selected_compounds_sha256", chosen_sha256, "selected_compounds.tsv"),
    )
    for field, value, source in checks:
        actual = _binding_value(audit, field)
        if actual != value:
            lines.append(
                f"{label}: selection_audit.json: {field}: expected {value!r} "
                f"from {source}, found {actual!r}"
            )
    header, registered_rows = _read_binding_table(run_dir / "compounds_registered.tsv")
    if "selection_status" not in header:
        lines.append(f"{label}: compounds_registered.tsv: selection_status: the column is missing")
    else:
        if len(registered_rows) != len(expected):
            lines.append(
                f"{label}: compounds_registered.tsv: rows: expected {len(expected)} "
                f"from the compound table, found {len(registered_rows)}"
            )
        for index in range(min(len(expected), len(registered_rows))):
            for column in ("compound_id", "selection_status"):
                actual = registered_rows[index].get(column)
                if actual != expected[index][column]:
                    lines.append(
                        f"{label}: compounds_registered.tsv: {entries[index]} {column}: "
                        f"expected {expected[index][column]!r} from the selection, found {actual!r}"
                    )
    ingest = json.loads((run_dir / "stp_audit.json").read_text(encoding="utf-8"))
    ingest_checks = (
        ("schema_version", "1.2", "the selection"),
        ("summary.files_not_selected", counts.get("excluded", 0), "the inputs"),
        ("summary.files_quarantined", 0, "the case policy"),
    )
    for field, value, source in ingest_checks:
        actual = _binding_value(ingest, field)
        if actual != value:
            lines.append(
                f"{label}: stp_audit.json: {field}: expected {value!r} from {source}, "
                f"found {actual!r}"
            )
    notes = ingest.get("notes") if isinstance(ingest, dict) else None
    codes = [
        note.get("code") for note in notes if isinstance(note, dict)
    ] if isinstance(notes, list) else []
    if "selection_stage_applied" not in codes:
        lines.append(f"{label}: stp_audit.json: notes: no selection_stage_applied note")
    _, target_rows = _read_binding_table(run_dir / "targets.tsv")
    selected_ids = {row["compound_id"] for row in expected if row["selection_status"] == "selected"}
    selected_files = {row["stp_file"] for row in expected if row["selection_status"] == "selected"}
    for number, row in enumerate(target_rows, start=1):
        value = row.get("compound_id")
        if value not in selected_ids:
            lines.append(
                f"{label}: targets.tsv: row {number} compound_id: {value!r} "
                "is not a selected compound"
            )
        value = row.get("source_file")
        if value not in selected_files:
            lines.append(
                f"{label}: targets.tsv: row {number} source_file: {value!r} "
                "is not the export of a selected compound"
            )
    intersect_path = run_dir / "intersect" / "intersect_audit.json"
    intersect = json.loads(intersect_path.read_text(encoding="utf-8"))
    groups = intersect.get("groups") if isinstance(intersect, dict) else None
    groups = groups if isinstance(groups, dict) else {}
    wanted = sorted({row["group"] for row in expected if row["selection_status"] == "selected"})
    found = sorted(groups)
    if wanted != found:
        lines.append(
            f"{label}: intersect_audit.json: groups: expected {wanted} "
            f"from the selected compounds, found {found}"
        )
    for group in wanted:
        count = sum(
            1
            for row in expected
            if row["selection_status"] == "selected" and row["group"] == group
        )
        entry = groups.get(group)
        actual = entry.get("compounds") if isinstance(entry, dict) else None
        if actual != count:
            lines.append(
                f"{label}: intersect_audit.json: groups.{group}.compounds: "
                f"expected {count} from the selected compounds, found {actual!r}"
            )
    return lines, {
        "selection_decisions.tsv": table_sha256,
        "selected_compounds.tsv": chosen_sha256,
    }


def check_selection(
    compounds: Path,
    decisions: Path,
    stages: dict[str, Path],
    selection_stages: dict[str, Path],
    runs: dict[str, Path],
) -> dict[str, object]:
    """Re-derive the selection from the decision table and compare every stage that used it."""
    compound_rows = _compound_binding_rows(compounds)
    decision_rows = _read_decisions(decisions)
    problems, paired = _selection_pairs(decisions.name, compound_rows, decision_rows)
    readable: dict[str, dict[str, str]] = {}
    for label in sorted(selection_stages):
        lines, hashes = _threshold_selection_problems(
            label,
            compound_rows,
            decisions,
            decision_rows,
            paired,
            stages[label],
            selection_stages[label],
            runs[label],
        )
        problems.extend(lines)
        if hashes is not None:
            readable[label] = hashes
    ordered = sorted(readable)
    if ordered:
        first = ordered[0]
        for label in ordered[1:]:
            for filename in ("selection_decisions.tsv", "selected_compounds.tsv"):
                if readable[label][filename] != readable[first][filename]:
                    problems.append(
                        f"{label}: {filename}: sha256: expected "
                        f"{readable[first][filename]!r} from the selection stage of "
                        f"threshold {first}, found {readable[label][filename]!r}"
                    )
    if problems:
        raise AssertionError("\n".join(problems))
    counts: dict[str, int] = {}
    for index in range(len(compound_rows)):
        decision = decision_rows[paired[index]]["decision"] if index in paired else ""
        status = SELECTION_DECISIONS.get(decision, "needs_review")
        counts[status] = counts.get(status, 0) + 1
    return {
        "rule": SELECTION_RULE,
        "decisions_sha256": sha256(decisions),
        "rows": len(decision_rows),
        "status_counts": {status: counts[status] for status in sorted(counts)},
        "thresholds": {
            label: {
                "selection_table_sha256": readable[label]["selection_decisions.tsv"],
                "selected_list_sha256": readable[label]["selected_compounds.tsv"],
            }
            for label in sorted(readable)
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="LABEL=DIR",
        help="threshold label and run dir",
    )
    parser.add_argument("--background-dir", type=Path, required=True)
    parser.add_argument("--disease-genes", type=Path, required=True)
    parser.add_argument("--hgnc-map", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--compound-table", type=Path, default=None)
    parser.add_argument("--stp-dir", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--species", default=None)
    parser.add_argument("--stage", action="append", metavar="LABEL=DIR", default=None)
    parser.add_argument("--selection", type=Path, default=None)
    parser.add_argument("--selection-stage", action="append", metavar="LABEL=DIR", default=None)
    args = parser.parse_args(argv)

    options = {
        "--compound-table": args.compound_table,
        "--stp-dir": args.stp_dir,
        "--log": args.log,
        "--species": args.species,
        "--stage": args.stage,
    }
    missing = [name for name, value in options.items() if value is None]
    if missing and len(missing) < len(options):
        raise SystemExit(
            "the binding recheck needs --compound-table, --stp-dir, --log, --species and "
            f"--stage together; missing: {', '.join(missing)}"
        )
    if not missing:
        if args.selection_stage is not None and args.selection is None:
            raise SystemExit("--selection-stage needs --selection")
    elif args.selection is not None or args.selection_stage is not None:
        raise SystemExit(
            "the selection recheck needs the binding recheck: give --compound-table, --stp-dir, "
            "--log, --species and --stage together with --selection and --selection-stage"
        )

    mapper = GeneMapper(args.hgnc_map)
    disease = {
        line.strip()
        for line in args.disease_genes.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    disease = {
        mapped.gene_symbol
        for symbol in disease
        if (mapped := mapper.map(symbol)).gene_symbol
    }
    if not disease:
        raise SystemExit("disease gene list produced no mapped symbols")
    result: dict[str, object] = {
        "disease_sha256": sha256(args.disease_genes),
        "hgnc_sha256": sha256(args.hgnc_map),
        "runs": {},
    }
    for spec in args.run:
        label, raw_path = spec.split("=", 1)
        result["runs"][label] = check_run(
            label, Path(raw_path).resolve(), args.background_dir.resolve(), disease, mapper
        )
    if args.compound_table is not None:
        runs: dict[str, Path] = {}
        for spec in args.run:
            label, raw_path = spec.split("=", 1)
            runs[label] = Path(raw_path).resolve()
        stages: dict[str, Path] = {}
        for spec in args.stage:
            label, raw_path = spec.split("=", 1)
            stages[label] = Path(raw_path).resolve()
        if sorted(stages) != sorted(runs):
            raise SystemExit(
                f"--run labels {sorted(runs)} and --stage labels {sorted(stages)} "
                "must be the same"
            )
        result["bindings"] = check_bindings(
            args.compound_table.resolve(),
            args.stp_dir.resolve(),
            args.log.resolve(),
            args.species,
            stages,
            runs,
        )
        if args.selection is not None:
            selection_stages: dict[str, Path] = {}
            for spec in args.selection_stage or []:
                label, raw_path = spec.split("=", 1)
                selection_stages[label] = Path(raw_path).resolve()
            if sorted(selection_stages) != sorted(runs):
                raise SystemExit(
                    f"--run labels {sorted(runs)} and --selection-stage labels "
                    f"{sorted(selection_stages)} must be the same"
                )
            result["selection"] = check_selection(
                args.compound_table.resolve(),
                args.selection.resolve(),
                stages,
                selection_stages,
                runs,
            )
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
