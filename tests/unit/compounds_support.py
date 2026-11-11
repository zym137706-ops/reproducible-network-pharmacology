"""Builders for the compounds-stage tests: run config, compound table, exports and submission log.

Nothing here needs RDKit or the network. The structure-mode tests replace the RDKit adapter by the
fake `Describer` of structures_support; only the tests of the command with real molecules use RDKit.
Only `run` needs the stage module, so the other builders work before it exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from structures_support import (
    NOW,
    TOOLKIT_VERSION,
    Describer,
    log_row,
    write_export,
    write_log,
    write_tsv,
)

from rnp.config import load_config

FIXTURES = Path(__file__).parents[1] / "fixtures"
STRUCTURE_COLUMNS = ["name", "group", "stp_file", "smiles", "pubchem_cid"]
NAME_COLUMNS = ["name", "group", "stp_file"]
OVERRIDES = {"CCCC": {"stereo_status": "undefined", "stereo_elements_total": 1}}
TABLE_COLUMNS = [
    "compound_id",
    "group",
    "name",
    "stp_file",
    "row_status",
    "structure_status",
    "structure_id",
    "smiles",
    "inchikey",
    "stereo_status",
    "submission_status",
    "export_kind",
    "export_sha256",
    "issue_codes",
]


def compound_row(number: int, smiles: str = "", group: str = "all", **fields) -> dict[str, str]:
    """A compound-table row `Compound <number>` bound to `c<number>.xlsx`."""
    row = {
        "name": f"Compound {number}",
        "group": group,
        "stp_file": f"c{number}.xlsx",
        "smiles": smiles,
        "pubchem_cid": "",
    }
    row.update(fields)
    return row


def write_exports(tmp_path: Path, numbers=range(1, 8)) -> dict[int, str]:
    """Create `c<number>.xlsx` in the STP directory; return their SHA-256 digests."""
    stp = tmp_path / "inputs" / "stp"
    return {number: write_export(stp, f"c{number}.xlsx") for number in numbers}


def write_config(
    tmp_path: Path,
    rows: list[dict[str, str]],
    *,
    columns: list[str] | None = None,
    log_rows: list[dict[str, str]] | None = None,
    inputs: dict[str, str] | None = None,
    species: str = "Homo_sapiens",
) -> Path:
    """Write the compound table, the log (if any) and a valid run config; return the config path."""
    columns = columns or STRUCTURE_COLUMNS
    inputs_dir = tmp_path / "inputs"
    (inputs_dir / "stp").mkdir(parents=True, exist_ok=True)
    write_tsv(
        inputs_dir / "compounds.tsv",
        columns,
        [{column: row.get(column, "") for column in columns} for row in rows],
    )
    data = {
        "project": "compounds-fixture",
        "species": species,
        "inputs": {
            "compounds": str(inputs_dir / "compounds.tsv"),
            "stp_dir": str(inputs_dir / "stp"),
            "disease_genes": str(FIXTURES / "run" / "inputs" / "disease_genes.txt"),
            "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
        },
        "thresholds": {"stp_probability": 0.10},
        "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
        "network": {"disease_label": "Fixture disease"},
        "outputs": {"dir": str(tmp_path / "results")},
    }
    if log_rows is not None:
        write_log(inputs_dir / "log.tsv", log_rows)
        data["inputs"]["submission_log"] = str(inputs_dir / "log.tsv")
    data["inputs"].update(inputs or {})
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def six_compounds() -> list[dict[str, str]]:
    """One compound of every kind (see the comments): the table of the structure-mode scenario."""
    return [
        compound_row(1, "CCO", group="g1"),  # verified
        compound_row(2, "CCN", group="g1"),  # no log row: not recorded
        compound_row(3, "CCC", group="g2"),  # the declared hash is wrong: rejected
        compound_row(4, "", group="g2"),  # no structure
        compound_row(5, "!bad", group="g2"),  # not a structure
        compound_row(6, "CCCC", group="g1"),  # reconstructed, stereo undefined
    ]


def six_log(digests: dict[int, str]) -> list[dict[str, str]]:
    """The log of the six compounds: four rows, one of them without a compound (a stray)."""
    return [
        log_row(1, digests[1]),
        log_row(3, "0" * 64, submitted_structure="CCC"),
        log_row(
            6,
            digests[6],
            submitted_structure="CCCC",
            export_kind="reconstructed_from_result_page",
            job_id="job-1",
            result_rows="30",
        ),
        log_row(9, "f" * 64, stp_file="stray.xlsx"),
    ]


def run(config_path: Path, **kwargs):
    """Run the stage with fakes: a fixed clock, the fake describer and a fixed toolkit version."""
    # Imported here, not at the top: the builders of this module are used by test_validate_entry_a
    # before the stage module exists.
    from rnp.analysis.compounds import run_compounds

    options = {
        "run_id": "r1",
        "now": lambda: NOW,
        "describe": Describer(OVERRIDES),
        "toolkit_version": lambda: TOOLKIT_VERSION,
    }
    options.update(kwargs)
    return run_compounds(load_config(config_path), **options)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
