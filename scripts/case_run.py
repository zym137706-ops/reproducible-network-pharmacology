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
CASE_CHECK = ROOT / "scripts" / "case_check.py"

SOURCE_HASH_RULE = "case-source-hash-v2"
SOURCE_HASH_EXCLUDES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    ".git",
    "build",
    "dist",
    "results",
    "data",
    "node_modules",
}
SOURCE_HASH_SUFFIXES = {".pyc", ".pyo", ".pyd", ".tmp", ".log", ".swp"}
SOURCE_HASH_FILES = (
    "scripts/case_run.py",
    "scripts/case_check.py",
    "scripts/build_case_background.py",
)
LOCK_FILES = ("uv.lock", "renv.lock")


class CommandFailure(RuntimeError):
    """A child command failed; carry its real exit code for the provenance record."""

    def __init__(self, command: list[str], returncode: int) -> None:
        super().__init__(f"command failed with exit {returncode}: {' '.join(command)}")
        self.command = command
        self.returncode = returncode


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


def _iter_hash_files(root: Path, relative: str) -> list[Path]:
    base = root / relative
    if not base.is_dir():
        return []
    files = []
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        if any(part in SOURCE_HASH_EXCLUDES for part in rel.parts):
            continue
        if path.suffix.lower() in SOURCE_HASH_SUFFIXES:
            continue
        files.append(path)
    return files


def _hash_files(root: Path, files: list[Path]) -> dict[str, Any]:
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {"files": len(files), "sha256": digest.hexdigest()}


def source_hashes(root: Path) -> dict[str, Any]:
    """Hash only the documented case-relevant source scope.

    The scope is deliberately not the whole repository/package: generated caches, results and local
    data are excluded. Each group and the combined controlled set are recorded separately.
    """
    core_files: list[Path] = []
    for relative in ("src/rnp", "R", "schemas"):
        core_files.extend(_iter_hash_files(root, relative))
    entrypoint_files = [
        root / relative for relative in SOURCE_HASH_FILES if (root / relative).is_file()
    ]
    lock_files = [root / relative for relative in LOCK_FILES if (root / relative).is_file()]
    groups = {
        "core": _hash_files(root, core_files),
        "entrypoints": _hash_files(root, entrypoint_files),
        "locks": _hash_files(root, lock_files),
    }
    combined = _hash_files(root, core_files + entrypoint_files + lock_files)
    return {
        "version": SOURCE_HASH_RULE,
        "algorithm": "sha256 over sorted repo-relative POSIX path + NUL + raw bytes + NUL",
        "path_format": "repo-relative POSIX paths, lexicographically sorted",
        "content": "raw bytes",
        "scope": (
            "case-relevant source, R, schemas, entrypoint scripts and lock files; "
            "not the full repository/package"
        ),
        "excludes": sorted(SOURCE_HASH_EXCLUDES),
        "groups": groups,
        "combined": combined,
    }


def source_hash(root: Path) -> str:
    """Backward-compatible combined hash for the controlled source scope."""
    return source_hashes(root)["combined"]["sha256"]


def _one_per_line(path: Path) -> list[str]:
    values = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if values and values[0].lower() == "gene_symbol":
        values = values[1:]
    return values


def _required(row: dict[str, str], field: str, source: Path, entry: str) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"{source}: entry {entry!r} has empty required field {field!r}")
    return value


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def verify_inputs(args: argparse.Namespace) -> dict[str, Any]:
    """Fail before writing anything when bindings, hashes or structures are inconsistent."""
    compounds = _read(args.compounds)
    if not compounds:
        raise ValueError(f"{args.compounds}: compounds table is empty")
    fields = set(compounds[0])
    required = {"name", "pubchem_cid", "stp_file"}
    if not required <= fields:
        raise ValueError(f"{args.compounds}: missing columns {sorted(required - fields)}")

    for index, row in enumerate(compounds, start=2):
        entry = (row.get("name") or row.get("stp_file") or f"row {index}").strip()
        for field in required:
            _required(row, field, args.compounds, entry)
    names = [(row["name"] or "").strip() for row in compounds]
    stp_names = [(row["stp_file"] or "").strip() for row in compounds]
    if duplicates := _duplicates(names):
        raise ValueError(f"{args.compounds}: duplicate compound name(s): {duplicates}")
    if duplicates := _duplicates(stp_names):
        raise ValueError(f"{args.compounds}: duplicate stp_file binding(s): {duplicates}")

    if not args.stp_dir.is_dir():
        raise ValueError(f"STP export directory not found: {args.stp_dir}")
    expected = set(stp_names)
    actual = {
        path.name
        for path in args.stp_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".csv", ".xlsx", ".xls"}
    }
    if actual != expected:
        raise ValueError(
            f"{args.stp_dir}: STP binding mismatch: missing={sorted(expected - actual)}, "
            f"unbound={sorted(actual - expected)}"
        )
    by_stp = {row["stp_file"].strip(): row for row in compounds}
    files = {name: args.stp_dir / name for name in by_stp}
    if any(not path.is_file() for path in files.values()):
        raise ValueError(f"{args.stp_dir}: a declared STP export is not a file")

    disease = _one_per_line(args.disease_genes)
    if not disease:
        raise ValueError(f"{args.disease_genes}: disease gene list is empty")
    if len(set(disease)) != len(disease):
        raise ValueError(f"{args.disease_genes}: disease gene list contains duplicate symbols")
    if not args.hgnc_map.is_file():
        raise ValueError(f"HGNC map not found: {args.hgnc_map}")

    log_check: dict[str, Any] = {"provided": False}
    if args.log is not None:
        log = _read(args.log)
        required_log = {
            "stp_file",
            "pubchem_cid",
            "submitted_structure",
            "species",
            "result_sha256",
        }
        if log and not required_log <= set(log[0]):
            raise ValueError(
                f"{args.log}: missing columns {sorted(required_log - set(log[0]))}"
            )
        by_file: dict[str, dict[str, str]] = {}
        for index, row in enumerate(log, start=2):
            entry = (row.get("stp_file") or row.get("compound") or f"row {index}").strip()
            stp = _required(row, "stp_file", args.log, entry)
            if stp in by_file:
                raise ValueError(f"{args.log}: duplicate stp_file binding {stp!r}")
            by_file[stp] = row
        if len(log) != len(compounds):
            raise ValueError(
                f"{args.log}: has {len(log)} rows, expected {len(compounds)} "
                f"from {args.compounds}"
            )
        if set(by_file) != expected:
            raise ValueError(
                f"{args.log}: binding mismatch with {args.compounds}: "
                f"missing={sorted(expected - set(by_file))}, "
                f"unexpected={sorted(set(by_file) - expected)}"
            )
        for stp in sorted(expected):
            compound = by_stp[stp]
            entry = (compound.get("name") or stp).strip()
            row = by_file[stp]
            log_entry = (row.get("compound") or stp).strip()
            if (row.get("compound") or "").strip() and row["compound"].strip() != entry:
                raise ValueError(
                    f"{args.log}: entry {log_entry!r} stp_file {stp!r} names "
                    f"{row['compound']!r}, but {args.compounds} names {entry!r}"
                )

            compound_cid = _required(compound, "pubchem_cid", args.compounds, entry)
            log_cid = _required(row, "pubchem_cid", args.log, log_entry)
            if compound_cid != log_cid:
                raise ValueError(
                    f"{args.log}: entry {log_entry!r} pubchem_cid {log_cid!r} != "
                    f"{compound_cid!r} in {args.compounds}"
                )

            compound_smiles = (compound.get("smiles") or "").strip()
            if not compound_smiles:
                raise ValueError(
                    f"{args.compounds}: entry {entry!r} has empty smiles; cannot verify "
                    f"submitted_structure in {args.log}"
                )
            submitted = _required(row, "submitted_structure", args.log, log_entry)
            if submitted != compound_smiles:
                raise ValueError(
                    f"{args.log}: entry {log_entry!r} submitted_structure does not match "
                    f"the exact stripped smiles for {entry!r} in {args.compounds}"
                )

            if "submission_id" in row and row.get("submission_id", "").strip():
                compound_submission = (compound.get("submission_id") or "").strip()
                if compound_submission and row["submission_id"].strip() != compound_submission:
                    raise ValueError(
                        f"{args.log}: entry {log_entry!r} submission_id "
                        f"{row['submission_id']!r} != {compound_submission!r} in {args.compounds}"
                    )

            species = _required(row, "species", args.log, log_entry)
            if species != "Homo sapiens":
                raise ValueError(
                    f"{args.log}: entry {log_entry!r} species is {species!r}, "
                    "expected 'Homo sapiens'"
                )
            actual_hash = sha256(files[stp])
            if row.get("result_sha256", "").strip() != actual_hash:
                raise ValueError(
                    f"{args.log}: entry {log_entry!r} result_sha256 does not match {files[stp]}"
                )
        log_check = {
            "provided": True,
            "path": str(args.log.resolve()),
            "sha256": sha256(args.log),
            "rows": len(log),
            "bindings_verified": True,
            "structures_verified": True,
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
        raise CommandFailure(command, result.returncode)


def _stage_name(command: list[str]) -> str:
    if any(str(part).endswith("case_check.py") for part in command):
        return "independent_check"
    if any(str(part).endswith("build_case_background.py") for part in command):
        return "backgrounds"
    for part in command:
        if part in {"validate", "ingest", "intersect", "network", "enrich", "report", "manifest"}:
            return part
    return "unknown"


def _write_provenance(out: Path, provenance: dict[str, Any]) -> None:
    validate_document(provenance, "case_provenance", "case provenance")
    target = out / "case_provenance.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, target)


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
    inputs = verify_inputs(args)
    out.mkdir(parents=True, exist_ok=True)
    configs = write_configs(args, out)
    source = source_hashes(ROOT)
    provenance = {
        "schema": "rnp-case-provenance/1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {
            "root": str(ROOT),
            "git": _git(ROOT),
            "source_sha256": source["combined"]["sha256"],
            "hash_rule": {
                "version": source["version"],
                "algorithm": source["algorithm"],
                "path_format": source["path_format"],
                "content": source["content"],
                "scope": source["scope"],
                "excludes": source["excludes"],
            },
            "groups": source["groups"],
            "combined": source["combined"],
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
    _write_provenance(out, provenance)
    if args.preflight_only:
        print(json.dumps(provenance, indent=2, sort_keys=True))
        return 0

    os.environ["RNP_CODE_SOURCE_SHA256"] = provenance["source"]["source_sha256"]
    os.environ["RNP_CODE_SOURCE_SCOPE"] = provenance["source"]["hash_rule"]["scope"]
    declared_commit = provenance["source"]["git"]["commit"]
    declared_dirty = provenance["source"]["git"]["dirty"]
    if declared_commit:
        os.environ["RNP_CODE_DECLARED_COMMIT"] = declared_commit
    if declared_dirty is not None:
        os.environ["RNP_CODE_DECLARED_DIRTY"] = str(declared_dirty).lower()

    base = [sys.executable, "-m", "rnp.cli"]
    labels = sorted(configs, key=float)
    try:
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
                [
                    "intersect",
                    "--config",
                    str(configs[label]),
                    "--targets",
                    str(run / "targets.tsv"),
                ],
                ["network", "--config", str(configs[label]), "--intersect", str(run / "intersect")],
                ["enrich", "--config", str(configs[label]), "--intersect", str(run / "intersect")],
                ["report", "--config", str(configs[label]), "--run-dir", str(run)],
            ]
            for command in commands:
                extra = (
                    ["--rscript", args.rscript]
                    if command[0] == "enrich" and args.rscript
                    else []
                )
                run_command(base + command + extra, ROOT, provenance["commands"])
            run_command(
                base + ["manifest", "--run-dir", str(run), "--check-inputs"],
                ROOT,
                provenance["commands"],
            )
        check_command = [sys.executable, str(CASE_CHECK)]
        for label in labels:
            check_command += ["--run", f"{label}={out / label / 'run'}"]
        check_command += [
            "--background-dir",
            str(out / "backgrounds"),
            "--disease-genes",
            str(args.disease_genes.resolve()),
            "--hgnc-map",
            str(args.hgnc_map.resolve()),
            "--out",
            str(out / "independent-check.json"),
        ]
        run_command(check_command, ROOT, provenance["commands"])
    except CommandFailure as exc:
        provenance["status"] = "failed"
        provenance["failed_stage"] = _stage_name(exc.command)
        provenance["failed_command"] = " ".join(exc.command)
        provenance["child_exit_code"] = exc.returncode
        _write_provenance(out, provenance)
        raise SystemExit(exc.returncode) from exc
    provenance["status"] = "complete"
    _write_provenance(out, provenance)
    print(f"case run complete: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
