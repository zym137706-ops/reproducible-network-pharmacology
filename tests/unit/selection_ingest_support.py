"""Builders for the tests of `rnp ingest stp --selection` and of the stages that come after it.

A case is a run config with its inputs, the compounds stage and the selection stage, built with the
fakes of selection_support (no RDKit, no network). The scenarios are those of ingest_link_support:
`MIXED` has four compounds (verified and accepted, quarantined by a wrong declared hash, quarantined
for lack of a structure, accepted without a log row); `FOUR_OK` has four accepted ones. Compound
`Compound <n>` is bound to the export `c<n>.csv`, whose targets are those of
ingest_link_support.BODIES: CA2 and TNF (1), IL6 (2), ESR1 and PTGS2 (3), EGFR (4). Of these TNF,
IL6 and PTGS2 are genes of the disease list of the fixtures, and EGFR is not in the HGNC fixture
(its row is excluded as unmapped), so Compound 4 never has an edge.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from ingest_link_support import MIXED
from selection_support import (
    ALL_FOUR,
    EVERYTHING_DECIDED,
    build,
    decision,
    read_tsv,
    select,
    snapshot,
    stage,
)

from rnp.analysis.ingest import run_ingest
from rnp.analysis.intersect import run_intersect
from rnp.analysis.network import run_network
from rnp.analysis.report import run_report
from rnp.config import load_config

__all__ = [
    "ALL_FOUR",
    "EVERYTHING_DECIDED",
    "FOUR_OK",
    "MIXED",
    "Case",
    "decision",
    "downstream",
    "ingest",
    "make",
    "read_json",
    "read_tsv",
    "snapshot",
]

FOUR_OK = [("CCO", "ok"), ("CCN", "ok"), ("CCC", "ok"), ("CCCC", "ok")]


@dataclass
class Case:
    """The config, the compounds stage and the selection stage of one scenario."""

    config: Path
    compounds: Path
    selection: Path

    @property
    def root(self) -> Path:
        return self.config.parent

    @property
    def decisions(self) -> Path:
        return self.root / "inputs" / "decisions.tsv"

    @property
    def registry(self) -> Path:
        return self.root / "results" / "registry" / "compound_registry.tsv"


def regroup(config: Path, groups: list[str]) -> None:
    """Rewrite the group column of the compound table (one group per compound, in order)."""
    path = config.parent / "inputs" / "compounds.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        columns = list(reader.fieldnames)
        rows = list(reader)
    assert len(rows) == len(groups)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row, group in zip(rows, groups, strict=True):
            writer.writerow({**row, "group": group})


def rename(case_root: Path, old: str, new: str) -> None:
    """Rename a compound in the compound table and in the decision table (LF, UTF-8)."""
    for name in ("compounds.tsv", "decisions.tsv"):
        path = case_root / "inputs" / name
        text = path.read_bytes().decode("utf-8")
        path.write_bytes(text.replace(old, new).encode("utf-8"))


def make(
    tmp_path: Path,
    rows: list[dict[str, str]],
    scenario: list[tuple[str, str | None]] = MIXED,
    *,
    groups: list[str] | None = None,
    renames: dict[str, str] | None = None,
    select_stage: bool = True,
    **kwargs,
) -> Case:
    """Build the inputs, run the compounds stage and (by default) the selection stage.

    `groups` gives every compound its group; `renames` renames compounds (`{"Compound 3": "TNF"}`;
    only for name mode, where no submission log refers to the names). With `select_stage=False`
    the selection directory of the case is the directory that the stage would have.
    """
    config = build(tmp_path, rows, scenario, **kwargs)
    if groups is not None:
        regroup(config, groups)
    for old, new in (renames or {}).items():
        rename(tmp_path, old, new)
    compounds = stage(config)
    if not select_stage:
        return Case(config, compounds, tmp_path / "results" / "sel_selection")
    return Case(config, compounds, Path(select(config, compounds)["run_dir"]))


def ingest(case: Case, *, run_id: str = "i1", selection="case", **kwargs):
    """`run_ingest` with the compounds stage and (unless `selection=None`) the selection stage."""
    chosen = case.selection if selection == "case" else selection
    return run_ingest(
        load_config(case.config),
        run_id=run_id,
        compounds=case.compounds,
        selection=chosen,
        **kwargs,
    )


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def downstream(case: Case, run_dir: Path, *, allow_partial: bool = False) -> dict:
    """Run `intersect`, `network` and `report` on an ingest run directory (library calls).

    Returns the intersect audit, the network summary and the text of the report.
    """
    config = load_config(case.config)
    run_intersect(
        config, run_dir / "targets.tsv", run_dir / "intersect", allow_partial=allow_partial
    )
    network = run_network(
        config, run_dir / "intersect", run_dir / "network", allow_partial=allow_partial
    )
    run_report(config, run_dir, run_dir / "report", allow_partial=True)
    reports = sorted((run_dir / "report").glob("*.md"))
    assert len(reports) == 1
    return {
        "intersect": read_json(run_dir / "intersect" / "intersect_audit.json"),
        "network": network,
        "report": reports[0].read_text(encoding="utf-8"),
    }
