#!/usr/bin/env python3
"""Portable entry point for a real rnp case run.

This is an orchestrator, not a second implementation: every analysis step is the installed
``rnp`` CLI. It accepts user-supplied compounds, STP exports, disease genes and HGNC map, verifies
explicit bindings/hashes and fixes the two threshold configs before ingest. It never downloads or
submits data, never touches ``data/local`` implicitly, and refuses to overwrite an existing output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from rnp.config import validate_document

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "examples" / "demo" / "run.yaml"
BUILD_BACKGROUND = ROOT / "scripts" / "build_case_background.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _git(root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def source_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in ("src/rnp", "R", "schemas"):
        base = root / relative
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _one_per_line(path: Path) -> list[str]:
    values = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if values and values[0].lower() == "gene_symbol":
        values = values[1:]
    return values


def verify_inputs(args: argparse.Namespace) -> dict[str, Any]:
    """Fail before writing anything when bindings, hashes or formats are inconsistent."""
    compounds = _read(args.compounds)
    if not compounds:
        raise ValueError("compounds table is empty")
    fields = set(compounds[0])
    required = {"name", "pubchem_cid", "smiles", "stp_file"}
    if not required <= fields:
        raise ValueError(f"compounds table missing columns: {sorted(required - fields)}")
    names = [row["name"] for row in compounds]
    if len(set(names)) != len(names):
        raise ValueError("duplicate compound names")
    if not args.stp_dir.is_dir():
        raise ValueError(f"STP export directory not found: {args.stp_dir}")
    expected = {row["stp_file"] for row in compounds}
    actual = {
        path.name
        for path in args.stp_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".csv", ".xlsx", ".xls"}
    }
    if actual != expected:
        raise ValueError(
            f"STP binding mismatch: missing={sorted(expected - actual)}, "
            f"unbound={sorted(actual - expected)}"
        )
    files = {row["stp_file"]: args.stp_dir / row["stp_file"] for row in compounds}
    if any(not path.is_file() for path in files.values()):
        raise ValueError("a declared STP export is not a file")

    disease = _one_per_line(args.disease_genes)
    if not disease:
        raise ValueError("disease gene list is empty")
    if len(set(disease)) != len(disease):
        raise ValueError("disease gene list contains duplicate symbols")
    if not args.hgnc_map.is_file():
        raise ValueError(f"HGNC map not found: {args.hgnc_map}")

    log_check: dict[str, Any] = {"provided": False}
    if args.log is not None:
        log = _read(args.log)
        if len(log) != len(compounds):
            raise ValueError(f"submission log has {len(log)} rows, expected {len(compounds)}")
        by_file = {row["stp_file"]: row for row in log}
        if set(by_file) != expected:
            raise ValueError("submission log binds files not present in compounds.tsv")
        for name, path in files.items():
            row = by_file[name]
            actual_hash = sha256(path)
            if row.get("result_sha256", "").strip() != actual_hash:
                raise ValueError(f"result hash mismatch for {name}")
            if not row.get("submitted_structure", "").strip():
                raise ValueError(f"submitted_structure is empty for {name}")
            if row.get("species", "").strip() != "Homo sapiens":
                raise ValueError(f"species is not Homo sapiens for {name}")
        log_check = {
            "provided": True,
            "path": str(args.log.resolve()),
            "sha256": sha256(args.log),
            "rows": len(log),
            "time_precision": "submitted_date is date-only; retrieved_date uses the user-approved "
            "file LastWriteTime proxy; result_url/job_id may be not_saved",
        }

    return {
        "compounds": str(args.compounds.resolve()),
        "compounds_sha256": sha256(args.compounds),
        "compound_rows": len(compounds),
        "stp_dir": str(args.stp_dir.resolve()),
        "stp_files": {
            name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for name, path in sorted(files.items())
        },
        "disease_genes": str(args.disease_genes.resolve()),
        "disease_sha256": sha256(args.disease_genes),
        "disease_rows": len(disease),
        "hgnc_map": str(args.hgnc_map.resolve()),
        "hgnc_sha256": sha256(args.hgnc_map),
        "log": log_check,
    }


def write_configs(args: argparse.Namespace, out: Path) -> dict[str, Path]:
    base = yaml.safe_load(args.config_template.read_text(encoding="utf-8"))
    configs: dict[str, Path] = {}
    for label in args.thresholds:
        label = f"{float(label):.2f}"
        data = yaml.safe_load(yaml.safe_dump(base, sort_keys=False))
        data["description"] = f"Local case, STP probability {label}"
        data["inputs"] = {
            "compounds": str(args.compounds.resolve()),
            "stp_dir": str(args.stp_dir.resolve()),
            "disease_genes": str(args.disease_genes.resolve()),
            "disease_source": data.get("inputs", {}).get("disease_source", "CTD"),
            "disease_retrieval_date": data.get("inputs", {}).get(
                "disease_retrieval_date", "2026-10-21"
            ),
            "hgnc_map": str(args.hgnc_map.resolve()),
        }
        data["thresholds"]["stp_probability"] = float(label)
        data["thresholds"]["note"] = f"case threshold {label}; sensitivity run independent"
        data["enrichment"]["universe_file"] = str(out / "backgrounds" / f"universe-{label}.txt")
        data["outputs"] = {"dir": str(out / label)}
        path = out / "configs" / f"run-{label}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        configs[label] = path
    return configs


def run_command(command: list[str], cwd: Path, recorded: list[str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    if recorded is not None:
        recorded.append(" ".join(command))
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(f"command failed with exit {result.returncode}: {' '.join(command)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compounds", type=Path, required=True)
    parser.add_argument("--stp-dir", type=Path, required=True)
    parser.add_argument("--disease-genes", type=Path, required=True)
    parser.add_argument("--hgnc-map", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config-template", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--thresholds", nargs="+", default=["0.10", "0.05"])
    parser.add_argument("--rscript", default=None)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="verify inputs and write fixed configs, but do not run the chain",
    )
    args = parser.parse_args(argv)

    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"refusing to write into a non-empty output directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    inputs = verify_inputs(args)
    configs = write_configs(args, out)
    provenance = {
        "schema": "rnp-case-provenance/1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {
            "root": str(ROOT),
            "git": _git(ROOT),
            "source_sha256": source_hash(ROOT),
            "attestation": "git state read from the checkout; container callers must mount .git",
        },
        "container": {
            "image": os.environ.get("RNP_CONTAINER_IMAGE"),
            "image_id": os.environ.get("RNP_CONTAINER_IMAGE_ID"),
            "image_digest": os.environ.get("RNP_CONTAINER_IMAGE_DIGEST"),
            "python": sys.version.split()[0],
            "r_version": os.environ.get("RNP_R_VERSION"),
            "r_lib": os.environ.get("R_LIBS"),
            "renv_lock_sha256": os.environ.get("RNP_RENV_LOCK_SHA256"),
            "uv_lock_sha256": os.environ.get("RNP_UV_LOCK_SHA256"),
        },
        "inputs": inputs,
        "configs": {
            label: {"path": str(path), "sha256": sha256(path)}
            for label, path in configs.items()
        },
        "commands": [],
        "status": "preflight_only" if args.preflight_only else "running",
    }
    validate_document(provenance, "case_provenance", "case provenance")
    (out / "case_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.preflight_only:
        print(json.dumps(provenance, indent=2, sort_keys=True))
        return 0

    os.environ["RNP_CODE_SOURCE_SHA256"] = provenance["source"]["source_sha256"]
    declared_commit = provenance["source"]["git"]["commit"]
    declared_dirty = provenance["source"]["git"]["dirty"]
    if declared_commit:
        os.environ["RNP_CODE_DECLARED_COMMIT"] = declared_commit
    if declared_dirty is not None:
        os.environ["RNP_CODE_DECLARED_DIRTY"] = str(declared_dirty).lower()

    base = [sys.executable, "-m", "rnp.cli"]
    labels = sorted(configs, key=float)
    for label in labels:
        run_command(
            base + ["validate", "--config", str(configs[label])],
            ROOT,
            provenance["commands"],
        )
    for label in labels:
        run_command(
            base
            + [
                "ingest",
                "stp",
                "--config",
                str(configs[label]),
                "--run-id",
                "run",
            ],
            ROOT,
            provenance["commands"],
        )
    background_args = [sys.executable, str(BUILD_BACKGROUND)]
    for label in labels:
        background_args += [
            "--targets",
            f"{label}={out / label / 'run' / 'targets.tsv'}",
        ]
    background_args += [
        "--disease-genes",
        str(args.disease_genes.resolve()),
        "--hgnc-map",
        str(args.hgnc_map.resolve()),
        "--out-dir",
        str(out / "backgrounds"),
    ]
    run_command(background_args, ROOT, provenance["commands"])
    for label in labels:
        run = out / label / "run"
        commands = [
            ["intersect", "--config", str(configs[label]), "--targets", str(run / "targets.tsv")],
            ["network", "--config", str(configs[label]), "--intersect", str(run / "intersect")],
            ["enrich", "--config", str(configs[label]), "--intersect", str(run / "intersect")],
            ["report", "--config", str(configs[label]), "--run-dir", str(run)],
        ]
        for command in commands:
            extra = ["--rscript", args.rscript] if command[0] == "enrich" and args.rscript else []
            run_command(base + command + extra, ROOT, provenance["commands"])
        run_command(
            base + ["manifest", "--run-dir", str(run), "--check-inputs"],
            ROOT,
            provenance["commands"],
        )
    provenance["status"] = "complete"
    (out / "case_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"case run complete: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
