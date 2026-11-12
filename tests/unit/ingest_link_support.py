"""Builders for the tests of `rnp ingest stp --compounds`: exports, compound tables, both stages.

A scenario is a list of `(smiles, log)` pairs, one per compound `Compound <n>` (n from 1) that is
bound to the export `c<n>.csv`. `log` is "ok" (a submission log row with the right hash, a native
export), "unstated" or "reconstructed" (the same with another export kind), "bad_hash" (a wrong
declared hash: the submission is rejected and the compound is quarantined) or None (no log row: not
recorded). A compound without a SMILES string has no structure and is quarantined too. The
structure describer is the fake of structures_support, so none of this needs RDKit or the network.
"""

from __future__ import annotations

import csv
from pathlib import Path

from compounds_support import compound_row, write_config
from structures_support import NOW, TOOLKIT_VERSION, Describer, log_row, write_export

from rnp.analysis.compounds import run_compounds
from rnp.analysis.ingest import run_ingest
from rnp.config import load_config

HEADER = "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,Known actives (3D/2D)\n"
BODIES = {
    1: "A1,CA2,P00918,,X,0.40,No\nA2,TNF,P01375,,X,0.30,No\n",
    2: "B1,IL6,P05231,,X,0.20,No\n",
    3: "C1,ESR1,P03372,,X,0.90,No\nC2,PTGS2,P35354,,X,0.60,No\n",
    4: "D1,EGFR,P00533,,X,0.50,No\n",
}
KIND_FIELDS = {
    "unstated": {"export_kind": ""},
    "reconstructed": {
        "export_kind": "reconstructed_from_result_page",
        "job_id": "job-1",
        "result_rows": "12",
    },
}
MIXED = [("CCO", "ok"), ("CCN", "bad_hash"), ("", None), ("CCC", None)]
CLEAN = [("CCO", "ok"), ("CCN", None)]


def export_text(number: int) -> str:
    return HEADER + BODIES[number]


def build(tmp_path: Path, scenario: list[tuple[str, str | None]], columns=None) -> Path:
    """Write the exports, the compound table, the log (if any row has one) and the run config."""
    stp = tmp_path / "inputs" / "stp"
    digests = {
        number: write_export(stp, f"c{number}.csv", export_text(number))
        for number in range(1, len(scenario) + 1)
    }
    rows = [
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
    return write_config(tmp_path, rows, columns=columns, log_rows=log or None)


def compounds_stage(config: Path) -> Path:
    """Run the compounds stage with fakes (fixed clock, fake describer); return its directory."""
    summary = run_compounds(
        load_config(config),
        run_id="s",
        now=lambda: NOW,
        describe=Describer(),
        toolkit_version=lambda: TOOLKIT_VERSION,
    )
    return Path(summary["run_dir"])


def ingest(config: Path, compounds=None, run_id: str = "i1", **kwargs):
    return run_ingest(load_config(config), run_id=run_id, compounds=compounds, **kwargs)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))
