"""`rnp ingest stp` without `--compounds` is what it was before the compounds stage existed.

Two small scenarios are run. Their three deterministic artifacts are compared with fingerprints
taken from the code before the `--compounds` option was added: `compounds_registered.tsv` and
`targets.tsv` byte for byte, `stp_audit.json` after the machine-dependent fields (the paths with
their separators, and the hash of the run config that contains them) are normalised. The input
files are written with LF on every platform, so the hashes of the exports in the audit are the
same everywhere. A compound table that has the structure columns of the compounds stage (smiles,
pubchem_cid, ...) must give the same artifacts as the plain table: only the explicit option makes
`ingest stp` look at them.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from rnp.analysis.ingest import run_ingest
from rnp.config import load_config, load_schema

FIXTURES = Path(__file__).parents[1] / "fixtures"
HEADER = "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,Known actives (3D/2D)\n"
EXPORTS = {
    "a.csv": "A1,CA2,P00918,,X,0.40,No\nA2,TNF,P01375,,X,0.30,No\nA3,IL6,P05231,,X,0.05,No\n",
    "b.csv": "B1,ESR1,P03372,,X,0.90,No\nB2,PTGS2,P35354,,X,0.60,No\n",
    "c.csv": "",
    "extra.csv": "X1,EGFR,P00533,,X,0.50,No\n",
}
PARTIAL_TABLE = (
    "name\tgroup\tstp_file\nAlpha\tg1\ta.csv\nBeta\tg1\tb.csv\nGamma\tg2\tc.csv\nDelta\tg2\td.csv\n"
)
CLEAN_TABLE = "name\tstp_file\nAlpha\ta.csv\nBeta\tb.csv\n"
EXTRA_COLUMNS_TABLE = (
    "name\tgroup\tstp_file\tsmiles\tpubchem_cid\tsource\n"
    "Alpha\tg1\ta.csv\tCCO\t702\tPubChem\n"
    "Beta\tg1\tb.csv\tCCN\t6329\tPubChem\n"
    "Gamma\tg2\tc.csv\tCCC\t\tPubChem\n"
    "Delta\tg2\td.csv\t\t\tlocal\n"
)
# fingerprints taken from the code before `--compounds` existed
GOLDEN = {
    "partial": {
        "registered": "2c8ef8cf80b398cb240c4392723ce13e8a6f9c9c2c3b3fdf214261c2c5090857",
        "targets": "674be399d6d99fef383b67f154effeb2e0bae64e983c27eeaeb62382561a342f",
        "audit": "cc56d622370ff4a89cb26c490c8c2f5ddde2f04c3e3f9aa63e9c9ffcad98a4cc",
    },
    "clean": {
        "registered": "8777b5aaa0f757839dd7399849820c5bdaeee4bdecaac0f401e6711cbe738ad6",
        "targets": "c1083bd1220bc9967971253a72025a2406a2ecab880be25ff6bd1e1cad93314a",
        "audit": "175ac994142c675957a799d8d6ff06c6873f442c5a75a9c0570b1167bee0a004",
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(tmp_path: Path, table: str, names: list[str]) -> tuple[Path, str]:
    """Run `ingest stp`; return the run directory and the (resolved) directory of the run config."""
    inputs = tmp_path / "inputs"
    stp = inputs / "stp"
    stp.mkdir(parents=True)
    # LF on every platform: the exports are hashed into the audit, and `write_text` would turn
    # "\n" into the line ending of the platform (CRLF on Windows) and change those hashes.
    (inputs / "compounds.tsv").write_text(table, encoding="utf-8", newline="\n")
    for name in names:
        (stp / name).write_text(HEADER + EXPORTS[name], encoding="utf-8", newline="\n")
    data = {
        "project": "unchanged-fixture",
        "species": "Homo_sapiens",
        "inputs": {
            "compounds": str(inputs / "compounds.tsv"),
            "stp_dir": str(stp),
            "disease_genes": str(FIXTURES / "run" / "inputs" / "disease_genes.txt"),
            "hgnc_map": str(FIXTURES / "hgnc" / "hgnc_map.tsv"),
        },
        "thresholds": {"stp_probability": 0.10},
        "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
        "network": {"disease_label": "Fixture disease"},
        "outputs": {"dir": str(tmp_path / "results")},
    }
    config = tmp_path / "run.yaml"
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    loaded = load_config(config)
    summary = run_ingest(loaded, run_id="r1")
    return Path(summary["run_dir"]), str(loaded.path.parent)


def normalised_audit(run_dir: Path, root: str) -> str:
    """The audit as JSON text without what depends on the machine: the paths, the config hash."""
    audit = json.loads((run_dir / "stp_audit.json").read_text(encoding="utf-8"))
    audit["config"]["sha256"] = "<config sha256>"
    text = json.dumps(audit, sort_keys=True, ensure_ascii=False)
    text = text.replace(root, "<root>").replace(root.replace("\\", "\\\\"), "<root>")
    # what is left of a path after the root is a relative path: write its separators as "/"
    return text.replace("\\\\", "/")


def fingerprints(run_dir: Path, root: str) -> dict[str, str]:
    return {
        "registered": sha256((run_dir / "compounds_registered.tsv").read_bytes()),
        "targets": sha256((run_dir / "targets.tsv").read_bytes()),
        "audit": sha256(normalised_audit(run_dir, root).encode("utf-8")),
    }


SCENARIOS = {
    "partial": (PARTIAL_TABLE, ["a.csv", "b.csv", "c.csv", "extra.csv"]),
    "clean": (CLEAN_TABLE, ["a.csv", "b.csv"]),
}


@pytest.mark.parametrize("name", ["partial", "clean"])
def test_the_artifacts_are_the_ones_of_the_code_before_the_option_existed(tmp_path, name):
    table, names = SCENARIOS[name]
    run_dir, root = run(tmp_path, table, names)
    assert fingerprints(run_dir, root) == GOLDEN[name]


def test_the_two_scenarios_cover_partial_and_complete_stages(tmp_path):
    partial, _ = run(tmp_path / "p", PARTIAL_TABLE, SCENARIOS["partial"][1])
    audit = json.loads((partial / "stp_audit.json").read_text(encoding="utf-8"))
    assert audit["stage_status"] == "partial"
    assert [item["reason"] for item in audit["quarantine"]] == ["not_bound_to_compound"]
    assert audit["missing_exports"][0]["stp_file"] == "d.csv"
    clean, _ = run(tmp_path / "c", CLEAN_TABLE, SCENARIOS["clean"][1])
    assert json.loads((clean / "stp_audit.json").read_text(encoding="utf-8"))["stage_status"] == (
        "complete"
    )


def test_a_table_with_structure_columns_gives_the_same_artifacts_without_the_option(tmp_path):
    plain, plain_root = run(tmp_path / "plain", PARTIAL_TABLE, SCENARIOS["partial"][1])
    rich, rich_root = run(tmp_path / "rich", EXTRA_COLUMNS_TABLE, SCENARIOS["partial"][1])
    for name in ("compounds_registered.tsv", "targets.tsv"):
        assert (plain / name).read_bytes() == (rich / name).read_bytes(), name
    assert normalised_audit(plain, plain_root) == normalised_audit(rich, rich_root)


def test_without_the_option_nothing_of_the_compounds_stage_is_recorded(tmp_path):
    run_dir, _ = run(tmp_path, EXTRA_COLUMNS_TABLE, SCENARIOS["partial"][1])
    header = (run_dir / "compounds_registered.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "compound_id\tgroup\tname\tstp_file\tsubmission_id\tidentity_basis"
    audit = json.loads((run_dir / "stp_audit.json").read_text(encoding="utf-8"))
    jsonschema.validate(audit, load_schema("stp_audit"))
    assert audit["schema_version"] == "1.1"
    assert "compounds_stage_applied" not in {note["code"] for note in audit["notes"]}
    assert "parents" not in audit
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "ingest stp"
    assert manifest["parents"] == []
    assert sorted(manifest["args"]) == [
        "allow_filename_match",
        "config",
        "stp_dir",
        "stp_probability",
    ]
    names = [Path(item["path"]).name for item in manifest["inputs"]]
    assert names == ["run.yaml", "compounds.tsv", "a.csv", "b.csv", "c.csv", "extra.csv"]
