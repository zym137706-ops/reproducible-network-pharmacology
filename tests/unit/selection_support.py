"""Builders for the selection tests: decision tables, run configs with `inputs.selection`, stages.

A scenario is the list of `(smiles, log)` pairs of ingest_link_support: compound `Compound <n>`
is bound to the export `c<n>.csv`. With the scenario MIXED the compounds are, in order: verified
and accepted, quarantined (wrong declared hash), quarantined (no structure) and accepted (no log
row). Nothing here needs RDKit or the network: the compounds stage runs with the fakes of
structures_support, and the selection stage takes a fixed clock.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from compounds_support import NAME_COLUMNS, compound_row, write_config
from ingest_link_support import KIND_FIELDS, MIXED, export_text
from structures_support import NOW, TOOLKIT_VERSION, Describer, log_row, write_export

from rnp.analysis.compounds import run_compounds
from rnp.config import load_config

COLUMNS = [
    "compound",
    "group",
    "decision",
    "reason_codes",
    "rules_version",
    "reviewer",
    "evidence_refs",
]
LATER = "2026-11-12T08:00:00Z"


def decision(
    compound: str,
    value: str,
    *,
    group: str = "all",
    reason: str = "",
    rules: str = "RA-v1",
    reviewer: str = "Researcher",
    refs: str = "",
    **extra: str,
) -> dict[str, str]:
    """A row of the decision table."""
    return {
        "compound": compound,
        "group": group,
        "decision": value,
        "reason_codes": reason,
        "rules_version": rules,
        "reviewer": reviewer,
        "evidence_refs": refs,
        **extra,
    }


def write_decisions(
    path: Path,
    rows: list[dict[str, str]],
    columns: list[str] | None = None,
    *,
    delimiter: str = "\t",
    newline: str = "\n",
    encoding: str = "utf-8",
) -> Path:
    """Write a decision table (the columns default to the seven known ones)."""
    columns = columns or COLUMNS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter, lineterminator=newline)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(column, "") for column in columns])
    return path


def decisions_path(tmp_path: Path) -> Path:
    return tmp_path / "inputs" / "decisions.tsv"


def build(
    tmp_path: Path,
    rows: list[dict[str, str]] | None,
    scenario: list[tuple[str, str | None]] = MIXED,
    *,
    mode: str = "structure",
    columns: list[str] | None = None,
    names: int = 3,
) -> Path:
    """Write exports, compound table, log, decision table and run config; return the config path.

    In name mode the compound table has no smiles column and `names` compounds are written. When
    `rows` is None no decision table is written and `inputs.selection` is left out of the config.
    """
    inputs = {} if rows is None else {"selection": str(decisions_path(tmp_path))}
    if rows is not None:
        write_decisions(decisions_path(tmp_path), rows, columns)
    stp = tmp_path / "inputs" / "stp"
    if mode == "name":
        for number in range(1, names + 1):
            write_export(stp, f"c{number}.csv", export_text(number))
        table = [compound_row(number, stp_file=f"c{number}.csv") for number in range(1, names + 1)]
        return write_config(tmp_path, table, columns=NAME_COLUMNS, inputs=inputs)
    digests = {
        number: write_export(stp, f"c{number}.csv", export_text(number))
        for number in range(1, len(scenario) + 1)
    }
    table = [
        compound_row(number, smiles, stp_file=f"c{number}.csv")
        for number, (smiles, _) in enumerate(scenario, start=1)
    ]
    log = [
        log_row(
            number,
            "0" * 64 if kind == "bad_hash" else digests[number],
            stp_file=f"c{number}.csv",
            submitted_structure=smiles,
            **KIND_FIELDS.get(kind, {}),
        )
        for number, (smiles, kind) in enumerate(scenario, start=1)
        if kind
    ]
    return write_config(tmp_path, table, log_rows=log or None, inputs=inputs)


def stage(config: Path, run_id: str = "s") -> Path:
    """Run the compounds stage with fakes and return its directory."""
    summary = run_compounds(
        load_config(config),
        run_id=run_id,
        now=lambda: NOW,
        describe=Describer(),
        toolkit_version=lambda: TOOLKIT_VERSION,
    )
    return Path(summary["run_dir"])


def select(config: Path, compounds: Path, run_id: str = "sel", **kwargs):
    """Run the selection stage with a fixed clock."""
    from rnp.analysis.selection import run_selection

    options = {"run_id": run_id, "now": lambda: NOW}
    options.update(kwargs)
    return run_selection(load_config(config), compounds=compounds, **options)


def setup(tmp_path: Path, rows, scenario=MIXED, **kwargs) -> tuple[Path, Path]:
    """Build the case and run the compounds stage: the config path and the stage directory."""
    config = build(tmp_path, rows, scenario, **kwargs)
    return config, stage(config)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file under `root` as {relative path: bytes}."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


# The four candidates of MIXED with a decision for each: the table every status test starts from.
ALL_FOUR = [
    decision("Compound 1", "include"),
    decision("Compound 2", "include"),
    decision("Compound 3", "exclude", reason="no_structure;bad_data", refs="notes.pdf"),
    decision("Compound 4", "needs_review", reason="check_identity"),
]
EVERYTHING_DECIDED = [
    decision("Compound 1", "include"),
    decision("Compound 2", "exclude", reason="bad_hash"),
    decision("Compound 3", "exclude", reason="no_structure"),
    decision("Compound 4", "include", reason="ok_by_hand"),
]
