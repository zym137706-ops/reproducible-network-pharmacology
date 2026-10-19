"""Command-line interface.

The CLI is the single source of truth for every analysis step. The agent skill in
``skills/`` only orchestrates these commands; it does not contain business logic.

Exit codes: 0 success, 2 validation/input error (nothing written), 3 partial run
(outputs written and marked partial), 1 unexpected internal error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .analysis.enrich import run_enrich
from .analysis.ingest import run_ingest
from .analysis.intersect import run_intersect
from .analysis.network import run_network
from .config import RunConfig, load_config, validate_document
from .errors import InputError, RnpError, exit_code_for
from .provenance import sha256_file


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _require_inputs(config: RunConfig) -> dict[str, str]:
    checks: dict[str, Path] = {
        "compounds": config.input_path("compounds"),
        "stp_dir": config.input_path("stp_dir"),
        "disease_genes": config.input_path("disease_genes"),
    }
    if "hgnc_map" in config.data["inputs"]:
        checks["hgnc_map"] = config.input_path("hgnc_map")
    problems = []
    for name, path in checks.items():
        expected = "dir" if name == "stp_dir" else "file"
        if expected == "dir" and not path.is_dir():
            problems.append(f"inputs.{name}: not a directory: {path}")
        elif expected == "file" and not path.is_file():
            problems.append(f"inputs.{name}: not a file: {path}")
    if problems:
        raise InputError("declared inputs are missing", details=problems)
    exports = sorted(
        path.name
        for path in checks["stp_dir"].iterdir()
        if path.suffix.lower() in {".csv", ".tsv", ".txt", ".xlsx"}
    )
    if not exports:
        raise InputError(f"inputs.stp_dir contains no export files: {checks['stp_dir']}")
    return {name: str(path) for name, path in checks.items()} | {
        "export_files": str(len(exports))
    }


def cmd_validate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    summary = _require_inputs(config)
    _emit(
        {
            "status": "ok",
            "config": str(config.path),
            "config_sha256": config.sha256,
            "project": config.project,
            "species": config.species,
            "outputs": str(config.output_dir),
            **summary,
        }
    )
    return 0


def cmd_ingest_stp(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    summary = run_ingest(config, run_id=args.run_id, force=args.force)
    _emit(summary)
    return 0 if summary["stage_status"] == "complete" else 3


def cmd_intersect(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    targets = Path(args.targets).resolve()
    if not targets.is_file():
        raise InputError(f"target table not found: {targets}")
    out_dir = Path(args.out).resolve() if args.out else targets.parent / "intersect"
    summary = run_intersect(
        config,
        targets,
        out_dir,
        venn_plot=args.venn_plot,
        allow_partial=args.allow_partial,
        force=args.force,
    )
    _emit(summary)
    return 0


def cmd_network(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    intersect_dir = Path(args.intersect).resolve()
    if not (intersect_dir / "intersect_audit.json").is_file():
        raise InputError(
            f"no intersection outputs in {intersect_dir}",
            details=["run 'rnp intersect' first"],
        )
    out_dir = Path(args.out).resolve() if args.out else intersect_dir.parent / "network"
    summary = run_network(
        config,
        intersect_dir,
        out_dir,
        disease_label=args.disease_label,
        allow_partial=args.allow_partial,
        force=args.force,
    )
    _emit(summary)
    return 0


def cmd_enrich(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    intersect_dir = Path(args.intersect).resolve()
    if not (intersect_dir / "intersect_audit.json").is_file():
        raise InputError(
            f"no intersection outputs in {intersect_dir}",
            details=["run 'rnp intersect' first"],
        )
    out_dir = Path(args.out).resolve() if args.out else intersect_dir.parent / "enrichment"
    summary = run_enrich(
        config,
        intersect_dir,
        out_dir,
        allow_partial=args.allow_partial,
        force=args.force,
        rscript=args.rscript,
    )
    _emit(summary)
    return 0 if summary["stage_status"] in {"complete", "empty", "partial_override"} else 3


def cmd_manifest(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise InputError(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_document(manifest, "run_manifest", "run manifest")

    drift: list[dict[str, str]] = []
    if args.check_inputs:
        for record in manifest.get("inputs", []):
            path = Path(record["path"])
            if not path.is_file():
                drift.append({"path": str(path), "problem": "missing"})
                continue
            current = sha256_file(path)
            if current != record["sha256"]:
                drift.append({"path": str(path), "problem": "sha256 changed"})
    _emit(
        {
            "status": "ok" if not drift else "drift",
            "run_id": manifest["run_id"],
            "command": manifest["command"],
            "stage_status": manifest.get("stage_status"),
            "tool": manifest["tool"],
            "inputs_checked": len(manifest.get("inputs", [])) if args.check_inputs else 0,
            "drift": drift,
        }
    )
    return 0 if not drift else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rnp",
        description="Reproducible network-pharmacology workflows.",
    )
    parser.add_argument("--version", action="version", version=f"rnp {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a run config and its inputs")
    validate.add_argument("--config", required=True, help="path to run.yaml")

    ingest = sub.add_parser("ingest", help="parse raw exports into audited tables")
    ingest_sub = ingest.add_subparsers(dest="ingest_command", required=True)
    ingest_stp = ingest_sub.add_parser("stp", help="parse SwissTargetPrediction exports")
    ingest_stp.add_argument("--config", required=True, help="path to run.yaml")
    ingest_stp.add_argument("--run-id", default=None, help=argparse.SUPPRESS)
    ingest_stp.add_argument(
        "--force", action="store_true", help="replace an existing run directory"
    )

    intersect = sub.add_parser(
        "intersect", help="map target genes and intersect them with the disease gene set"
    )
    intersect.add_argument("--config", required=True, help="path to run.yaml")
    intersect.add_argument("--targets", required=True, help="targets.tsv from 'rnp ingest stp'")
    intersect.add_argument("--out", default=None, help="output directory")
    intersect.add_argument(
        "--venn-plot",
        action="store_true",
        help="render a 2-set Venn diagram with R VennDiagram when available",
    )
    intersect.add_argument(
        "--allow-partial",
        action="store_true",
        help="explicitly continue when the ingest stage is partial (recorded in the audit)",
    )
    intersect.add_argument("--force", action="store_true", help="replace an existing output dir")

    network = sub.add_parser(
        "network", help="write Cytoscape node/edge tables from an intersection run"
    )
    network.add_argument("--config", required=True, help="path to run.yaml")
    network.add_argument("--intersect", required=True, help="output directory of 'rnp intersect'")
    network.add_argument("--out", default=None, help="output directory")
    network.add_argument("--disease-label", default=None, help="node label for the disease")
    network.add_argument(
        "--allow-partial",
        action="store_true",
        help="explicitly continue when the intersection stage is partial",
    )
    network.add_argument("--force", action="store_true", help="replace an existing output dir")

    manifest = sub.add_parser("manifest", help="validate a run manifest and check for drift")
    manifest.add_argument("--run-dir", required=True, help="path to results/<run_id>")
    manifest.add_argument(
        "--check-inputs",
        action="store_true",
        help="re-hash every recorded input and report drift",
    )

    enrich = sub.add_parser(
        "enrich", help="run ORA on each intersection group with an explicit background"
    )
    enrich.add_argument("--config", required=True, help="path to run.yaml")
    enrich.add_argument("--intersect", required=True, help="output directory of 'rnp intersect'")
    enrich.add_argument("--out", default=None, help="output directory")
    enrich.add_argument(
        "--allow-partial",
        action="store_true",
        help="explicitly continue when the intersection stage is partial",
    )
    enrich.add_argument("--force", action="store_true", help="replace an existing output dir")
    enrich.add_argument(
        "--rscript", default=None, help="path to Rscript (default: RNP_RSCRIPT or PATH)"
    )
    return parser


_DISPATCH = {
    ("validate", None): cmd_validate,
    ("ingest", "stp"): cmd_ingest_stp,
    ("intersect", None): cmd_intersect,
    ("network", None): cmd_network,
    ("enrich", None): cmd_enrich,
    ("manifest", None): cmd_manifest,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    key = (args.command, getattr(args, "ingest_command", None))
    handler = _DISPATCH.get(key)
    if handler is None:  # pragma: no cover - argparse prevents this
        parser.error(f"unknown command: {args.command}")
        return 2
    try:
        return handler(args)
    except RnpError as exc:
        print(f"error: {exc.render()}", file=sys.stderr)
        return exit_code_for(exc)
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - last-resort guard, see exit-code contract
        print(f"unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
