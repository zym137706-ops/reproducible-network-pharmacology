#!/usr/bin/env python3
"""Offline synthetic demo for the v0.1 chain.

One command runs validate → ingest → intersect → network → manifest check against
**synthetic, hand-computed** inputs and asserts the expected tables. Every expected
value below was derived from the input files in this script, not copied from a run.

This is an engineering demo. It is not a scientific case and makes no biological
claim: compound names, probabilities and disease genes are fabricated to exercise
the contracts.

Usage:
    python scripts/synthetic_demo.py --out demo_out
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HEADER = (
    "Target,Common name,Uniprot ID,ChEMBL ID,Target Class,Probability*,"
    "Known actives (3D/2D)\n"
)
HGNC_HEADER = (
    "hgnc_id\tsymbol\tstatus\tprev_symbol\talias_symbol\tuniprot_ids\tentrez_id\tlocus_group\n"
)
HGNC_ROWS = [
    "HGNC:11892\tTNF\tApproved\t\tTNFA\tP01375\t7124\tprotein-coding gene",
    "HGNC:9604\tPTGS2\tApproved\t\tCOX2\tP35354\t5743\tprotein-coding gene",
    "HGNC:1383\tCA2\tApproved\t\t\tP00918\t760\tprotein-coding gene",
    "HGNC:6018\tIL6\tApproved\t\t\tP05231\t3569\tprotein-coding gene",
    "HGNC:5344\tICAM1\tApproved\t\t\tP05362\t3383\tprotein-coding gene",
    "HGNC:6871\tMAPK1\tApproved\t\tERK|ERK2\tP28482\t5594\tprotein-coding gene",
    "HGNC:6877\tMAPK3\tApproved\t\tERK|ERK1\tP27361\t5595\tprotein-coding gene",
]

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def read_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "rnp.cli", *args],
        capture_output=True,
        text=True,
        timeout=300,
    )


def write_case(root: Path, name: str, *, compounds: str, files: dict[str, str],
               disease: list[str], allow_filename_match: bool = False) -> Path:
    case = root / name
    inputs = case / "inputs"
    inputs.mkdir(parents=True)
    (inputs / "compounds.tsv").write_text(compounds, encoding="utf-8")
    stp = inputs / "stp"
    stp.mkdir()
    for filename, rows in files.items():
        (stp / filename).write_text(HEADER + rows, encoding="utf-8")
    (inputs / "disease.txt").write_text("\n".join(disease) + "\n", encoding="utf-8")
    (inputs / "hgnc.tsv").write_text(HGNC_HEADER + "\n".join(HGNC_ROWS) + "\n", encoding="utf-8")
    config = {
        "project": f"demo-{name}",
        "species": "Homo_sapiens",
        "inputs": {
            "compounds": str(inputs / "compounds.tsv"),
            "stp_dir": str(stp),
            "disease_genes": str(inputs / "disease.txt"),
            "hgnc_map": str(inputs / "hgnc.tsv"),
        },
        "thresholds": {"stp_probability": 0.10},
        "enrichment": {"engine": "r", "gene_sets": "GO_BP"},
        "network": {"disease_label": "Synthetic disease"},
        "outputs": {"dir": str(case / "results")},
    }
    if allow_filename_match:
        config["inputs"]["allow_filename_match"] = True
    (case / "run.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    return case


def case_normal(root: Path) -> None:
    case = write_case(
        root,
        "normal",
        compounds="name\tstp_file\nAlpha\ta.csv\nBeta\tb.csv\n",
        files={
            "a.csv": "A1,TNF,P01375,,X,0.50,No\nA2,CA2,P00918,,X,0.40,No\n",
            "b.csv": "B1,PTGS2,P35354,,X,0.30,No\n",
        },
        disease=["TNF", "PTGS2", "IL6"],
    )
    config = str(case / "run.yaml")
    run_dir = case / "results" / "normal"

    check(run_cli("validate", "--config", config).returncode == 0, "validate should pass")
    ingest = run_cli("ingest", "stp", "--config", config, "--run-id", "normal")
    check(ingest.returncode == 0, f"ingest should be complete: {ingest.stderr}")
    intersect = run_cli(
        "intersect", "--config", config, "--targets", str(run_dir / "targets.tsv")
    )
    check(intersect.returncode == 0, f"intersect failed: {intersect.stderr}")
    network = run_cli(
        "network", "--config", config, "--intersect", str(run_dir / "intersect")
    )
    check(network.returncode == 0, f"network failed: {network.stderr}")
    manifest = run_cli(
        "manifest", "--run-dir", str(run_dir), "--check-inputs"
    )
    check(manifest.returncode == 0, f"manifest check failed: {manifest.stdout}{manifest.stderr}")

    edges = read_tsv(run_dir / "intersect" / "edges.tsv")
    expected_edges = [
        ("CMP0001", "Alpha", "CA2"),
        ("CMP0001", "Alpha", "TNF"),
        ("CMP0002", "Beta", "PTGS2"),
    ]
    check(
        [(row["compound_id"], row["compound"], row["gene"]) for row in edges]
        == expected_edges,
        f"normal edges differ: {edges}",
    )
    intersection = read_tsv(run_dir / "intersect" / "intersection_genes.tsv")
    check(
        [row["gene"] for row in intersection] == ["PTGS2", "TNF"],
        f"normal intersection differs: {intersection}",
    )
    audit = json.loads((run_dir / "intersect" / "intersect_audit.json").read_text(encoding="utf-8"))
    stats = audit["groups"]["all"]
    check(
        (stats["targets"], stats["intersection"], stats["target_only"], stats["disease_only"])
        == (3, 2, 1, 1),
        f"normal set counts differ: {stats}",
    )
    nodes = read_tsv(run_dir / "network" / "all" / "nodes.tsv")
    check(
        {row["Node"]: row["Type"] for row in nodes}
        == {
            "Alpha": "Compound",
            "Beta": "Compound",
            "TNF": "Target",
            "PTGS2": "Target",
            "Synthetic disease": "Disease",
        },
        f"normal nodes differ: {nodes}",
    )
    network_edges = read_tsv(run_dir / "network" / "all" / "edges.tsv")
    # Only intersection genes enter the network: 2 compound-target + 2 target-disease.
    check(len(network_edges) == 4, f"normal network edges should be 4: {network_edges}")


def case_extra_export(root: Path) -> None:
    case = write_case(
        root,
        "extra_export",
        compounds="name\tstp_file\nAlpha\ta.csv\n",
        files={
            "a.csv": "A1,TNF,P01375,,X,0.50,No\n",
            "unlisted.csv": "U1,ICAM1,P05362,,X,0.90,No\n",
        },
        disease=["TNF", "ICAM1"],
    )
    config = str(case / "run.yaml")
    run_dir = case / "results" / "extra"
    ingest = run_cli("ingest", "stp", "--config", config, "--run-id", "extra")
    check(ingest.returncode == 0, f"extra-export ingest should be complete: {ingest.stderr}")
    payload = json.loads(ingest.stdout) if ingest.stdout.strip() else {}
    check(
        payload.get("summary", {}).get("files_quarantined") == 1,
        f"expected one quarantined export: {payload}",
    )
    check(
        payload.get("quarantine", [{}])[0].get("reason") == "not_bound_to_compound",
        f"unexpected quarantine reason: {payload}",
    )
    targets = (run_dir / "targets.tsv").read_text(encoding="utf-8")
    check("ICAM1" not in targets, "quarantined export must not reach targets.tsv")
    intersect = run_cli(
        "intersect", "--config", config, "--targets", str(run_dir / "targets.tsv")
    )
    check(intersect.returncode == 0, f"extra-export intersect failed: {intersect.stderr}")
    edges = read_tsv(run_dir / "intersect" / "edges.tsv")
    check(
        [(row["compound_id"], row["gene"]) for row in edges] == [("CMP0001", "TNF")],
        f"extra-export edges differ: {edges}",
    )


def case_zero(root: Path) -> None:
    case = write_case(
        root,
        "zero",
        compounds="name\tstp_file\nAlpha\ta.csv\n",
        files={"a.csv": "A1,CA2,P00918,,X,0.50,No\n"},
        disease=["TNF"],
    )
    config = str(case / "run.yaml")
    run_dir = case / "results" / "zero"
    check(
        run_cli("ingest", "stp", "--config", config, "--run-id", "zero").returncode == 0,
        "zero-case ingest should be complete",
    )
    intersect = run_cli(
        "intersect", "--config", config, "--targets", str(run_dir / "targets.tsv")
    )
    check(intersect.returncode == 0, f"zero-case intersect failed: {intersect.stderr}")
    payload = json.loads(intersect.stdout)
    check(
        payload["groups"]["all"]["intersection"] == 0,
        f"zero case should have no hits: {payload}",
    )
    network = run_cli(
        "network", "--config", config, "--intersect", str(run_dir / "intersect")
    )
    check(network.returncode == 0, f"zero-case network failed: {network.stderr}")
    network_payload = json.loads(network.stdout)
    check(network_payload["stage_status"] == "empty", f"expected empty network: {network_payload}")
    check(
        not (run_dir / "network" / "all").exists(),
        "empty result must not create a group network",
    )
    audit = json.loads((run_dir / "network" / "network_audit.json").read_text(encoding="utf-8"))
    check(audit["groups"] == {}, f"empty-network audit should have no groups: {audit}")


def case_ambiguous(root: Path) -> None:
    case = write_case(
        root,
        "ambiguous",
        compounds="name\tstp_file\nAlpha\ta.csv\n",
        files={
            "a.csv": "A1,TNF,P01375,,X,0.50,No\nA2,ERK,,,X,0.40,No\n",
        },
        disease=["TNF"],
    )
    config = str(case / "run.yaml")
    run_dir = case / "results" / "ambiguous"
    check(
        run_cli("ingest", "stp", "--config", config, "--run-id", "ambiguous").returncode == 0,
        "ambiguous-case ingest should be complete",
    )
    intersect = run_cli(
        "intersect", "--config", config, "--targets", str(run_dir / "targets.tsv")
    )
    check(intersect.returncode == 0, f"ambiguous-case intersect failed: {intersect.stderr}")
    exclusions = read_tsv(run_dir / "intersect" / "target_exclusions.tsv")
    check(
        any(
            row["reason"] == "unmapped_or_conflicting_gene" and row["common_name"] == "ERK"
            for row in exclusions
        ),
        f"ERK should be excluded as ambiguous: {exclusions}",
    )
    conflicts = read_tsv(run_dir / "intersect" / "gene_mapping_conflicts.tsv")
    check(len(conflicts) == 1 and "MAPK1;MAPK3" == conflicts[0]["ambiguous_symbols"],
          f"ambiguous symbols should be recorded: {conflicts}")
    edges = read_tsv(run_dir / "intersect" / "edges.tsv")
    check([row["gene"] for row in edges] == ["TNF"], f"ambiguous-case edges differ: {edges}")


def case_partial(root: Path) -> None:
    case = write_case(
        root,
        "partial",
        compounds="name\tstp_file\nAlpha\ta.csv\nBeta\tb.csv\n",
        files={"a.csv": "A1,TNF,P01375,,X,0.50,No\n"},
        disease=["TNF"],
    )
    config = str(case / "run.yaml")
    run_dir = case / "results" / "partial"
    ingest = run_cli("ingest", "stp", "--config", config, "--run-id", "partial")
    check(ingest.returncode == 3, f"partial ingest should exit 3, got {ingest.returncode}")
    refused = run_cli(
        "intersect", "--config", config, "--targets", str(run_dir / "targets.tsv")
    )
    check(refused.returncode == 2, f"partial upstream should be refused, got {refused.returncode}")
    check("not 'complete'" in refused.stderr, f"unexpected refusal message: {refused.stderr}")
    allowed = run_cli(
        "intersect",
        "--config",
        config,
        "--targets",
        str(run_dir / "targets.tsv"),
        "--allow-partial",
    )
    check(allowed.returncode == 0, f"explicit partial override should run: {allowed.stderr}")
    payload = json.loads(allowed.stdout)
    check(payload["stage_status"] == "partial_override", f"override not recorded: {payload}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline synthetic demo for rnp v0.1")
    parser.add_argument("--out", required=True, help="output directory (removed if present)")
    parser.add_argument("--keep", action="store_true", help="keep outputs for inspection")
    args = parser.parse_args()

    root = Path(args.out).resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    case_normal(root)
    case_extra_export(root)
    case_zero(root)
    case_ambiguous(root)
    case_partial(root)

    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print("PASS: 5 synthetic scenarios match their hand-computed expectations")
    if args.keep:
        print(f"outputs kept in {root}")
    else:
        shutil.rmtree(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
