"""Command-line interface.

The CLI is the single source of truth for every analysis step. The agent skill in
``skills/`` only orchestrates these commands; it does not contain business logic.

Exit codes: 0 success, 2 validation/input error (nothing written), 3 partial run
(outputs written and marked partial), 1 unexpected internal error.

``rnp acquire`` is the only command whose Python code uses the network (ADR-0005).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .acquire import DEFAULT_TIMEOUT, RECORD_FILENAME, urllib_fetcher, verify_acquisition
from .acquire import acquire as run_acquire
from .analysis.compounds import run_compounds
from .analysis.enrich import run_enrich
from .analysis.ingest import run_ingest
from .analysis.intersect import run_intersect
from .analysis.network import run_network
from .analysis.report import run_report
from .config import RunConfig, load_config, validate_document
from .errors import InputError, RnpError, exit_code_for
from .provenance import sha256_file, utc_now_iso


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _emit_ascii(payload: Any) -> None:
    """Print a summary that survives an old terminal code page.

    The summary quotes text from remote responses, so the record must not become unreadable when
    a non-ASCII character cannot be encoded after the record was already written.
    """
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def _require_inputs(config: RunConfig) -> dict[str, str]:
    checks: dict[str, Path] = {
        "compounds": config.input_path("compounds"),
        "stp_dir": config.input_path("stp_dir"),
        "disease_genes": config.input_path("disease_genes"),
    }
    if "hgnc_map" in config.data["inputs"]:
        checks["hgnc_map"] = config.input_path("hgnc_map")
    if "submission_log" in config.data["inputs"]:
        checks["submission_log"] = config.input_path("submission_log")
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
    summary = run_ingest(
        config, run_id=args.run_id, force=args.force, compounds=args.compounds
    )
    _emit(summary)
    return 0 if summary["stage_status"] == "complete" else 3


def cmd_ingest_compounds(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    summary = run_compounds(config, run_id=args.run_id, force=args.force)
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


def cmd_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    run_dir = Path(args.run_dir).resolve()
    if not (run_dir / "stp_audit.json").is_file():
        raise InputError(
            f"not an rnp run directory (missing stp_audit.json): {run_dir}",
            details=["pass the results/<run-id> directory produced by 'rnp ingest stp'"],
        )
    out_dir = Path(args.out).resolve() if args.out else run_dir / "report"
    summary = run_report(
        config,
        run_dir,
        out_dir,
        allow_partial=args.allow_partial,
        force=args.force,
    )
    _emit(summary)
    return 0


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


def _upper_ascii(text: str) -> str:
    """Upper-case ASCII identifiers only.

    A non-ASCII character must reach the library unchanged: str.upper() maps some of them
    (for example the German sharp s) onto other valid-looking letters, silently turning one
    identifier into a different one.
    """
    return text.upper() if text.isascii() else text


def _acquire_pairs(raw_items: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    pairs: list[tuple[str, str]] = []
    problems: list[str] = []
    for number, raw in enumerate(raw_items, 1):
        parts = [part.strip() for part in raw.split(":")]
        if len(parts) != 2 or not all(parts):
            problems.append(f"item {number}: {raw!r} is not PDB_ID:UNIPROT_ACCESSION")
            continue
        pairs.append((_upper_ascii(parts[0]), _upper_ascii(parts[1])))
    return pairs, problems


def _record_status(path: Path) -> str | None:
    """Return the record status, or None when the file is not a JSON object with one."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    status = record.get("status")
    return status if isinstance(status, str) else None


def _acquire_verify(args: argparse.Namespace) -> int:
    if args.out is not None or args.timeout is not None or args.items:
        raise InputError("--verify cannot be combined with --out, --timeout or items")
    directory = Path(args.verify).resolve()
    if not directory.is_dir():
        raise InputError(f"not a directory: {directory}")
    record_path = directory / RECORD_FILENAME
    if not record_path.is_file():
        raise InputError(
            f"not an acquisition directory (missing {RECORD_FILENAME}): {directory}",
            details=["a directory without the record is an interrupted run and cannot be used"],
        )
    problems = verify_acquisition(directory)
    _emit_ascii(
        {
            "status": "problems" if problems else "verified",
            "directory": str(directory),
            "record": str(record_path),
            "record_sha256": sha256_file(record_path),
            "acquisition_status": _record_status(record_path),
            "problems": problems,
        }
    )
    return 3 if problems else 0


def cmd_acquire(args: argparse.Namespace) -> int:
    if args.verify is not None:
        return _acquire_verify(args)
    timeout = DEFAULT_TIMEOUT if args.timeout is None else args.timeout
    problems: list[str] = []
    if not args.out:
        problems.append("--out is required unless --verify is given")
    if not args.items:
        problems.append("no items given; pass one or more PDB_ID:UNIPROT_ACCESSION pairs")
    if not math.isfinite(timeout) or timeout <= 0:
        problems.append("--timeout must be a positive, finite number of seconds")
    pairs, item_problems = _acquire_pairs(args.items)
    problems.extend(item_problems)
    if problems:
        raise InputError("invalid arguments for 'rnp acquire'", details=problems)
    result = run_acquire(
        pairs,
        Path(args.out).resolve(),
        fetcher=urllib_fetcher,
        now=utc_now_iso,
        timeout=timeout,
    )
    record = result.record
    outcomes: dict[str, int] = {}
    for entry in record["requests"]:
        outcomes[entry["outcome"]] = outcomes.get(entry["outcome"], 0) + 1
    _emit_ascii(
        {
            "status": result.status,
            "acquisition_id": record["acquisition_id"],
            "out_dir": str(result.out_dir),
            "record": str(result.record_path),
            "record_sha256": sha256_file(result.record_path),
            "items": [
                {
                    "item_id": entry["item_id"],
                    "pdb_id": entry["pdb_id"],
                    "uniprot_accession": entry["uniprot_accession"],
                    "status": entry["status"],
                }
                for entry in record["items"]
            ],
            "outcomes": {name: outcomes[name] for name in sorted(outcomes)},
            "warnings": record["warnings"],
        }
    )
    return 0 if result.status == "complete" else 3


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
    ingest_compounds = ingest_sub.add_parser(
        "compounds",
        help="register compound identities, structures and STP submissions (upstream entry A)",
    )
    ingest_compounds.add_argument("--config", required=True, help="path to run.yaml")
    ingest_compounds.add_argument("--run-id", default=None, help=argparse.SUPPRESS)
    ingest_compounds.add_argument(
        "--force", action="store_true", help="replace an existing run directory"
    )
    ingest_stp = ingest_sub.add_parser("stp", help="parse SwissTargetPrediction exports")
    ingest_stp.add_argument("--config", required=True, help="path to run.yaml")
    ingest_stp.add_argument("--run-id", default=None, help=argparse.SUPPRESS)
    ingest_stp.add_argument(
        "--force", action="store_true", help="replace an existing run directory"
    )
    ingest_stp.add_argument(
        "--compounds",
        default=None,
        metavar="DIR",
        help="apply the decisions of a compounds stage directory "
        "(output of 'rnp ingest compounds')",
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

    report = sub.add_parser(
        "report", help="render a Markdown report from audited stage artifacts"
    )
    report.add_argument("--config", required=True, help="path to run.yaml")
    report.add_argument("--run-dir", required=True, help="results/<run-id> directory")
    report.add_argument("--out", default=None, help="output directory")
    report.add_argument(
        "--allow-partial",
        action="store_true",
        help="render a report that includes explicitly partial stages",
    )
    report.add_argument("--force", action="store_true", help="replace an existing output dir")
    acquire = sub.add_parser(
        "acquire",
        help="freeze RCSB and UniProt records for chosen receptor IDs (uses the network)",
        description=(
            "Retrieve the RCSB PDB and UniProt records of each PDB_ID:UNIPROT_ACCESSION "
            "pair, freeze them in a new directory and write acquisition_record.json there. "
            "This is the only rnp command whose Python code uses the network: it contacts "
            "files.rcsb.org, data.rcsb.org and rest.uniprot.org and nothing else, and --verify "
            "contacts nothing. Identifiers are case-insensitive and recorded in upper case."
        ),
        epilog=(
            "Exit codes: 0 every item complete; 2 invalid arguments, nothing written; 3 at "
            "least one item failed (the record is written and lists every failure), or --verify "
            "found a problem; 1 internal error. An output directory without "
            "acquisition_record.json is an interrupted run: delete it and run again."
        ),
    )
    acquire.add_argument(
        "items",
        nargs="*",
        metavar="PDB_ID:UNIPROT_ACCESSION",
        help="a receptor structure and its target sequence, for example 1M17:P00533",
    )
    acquire.add_argument(
        "--out", default=None, help="new or empty directory for the frozen files and the record"
    )
    acquire.add_argument(
        "--timeout",
        type=float,
        default=None,
        help=f"seconds to wait for each response (default {DEFAULT_TIMEOUT:g})",
    )
    acquire.add_argument(
        "--verify",
        default=None,
        metavar="DIR",
        help="check a frozen directory against its record; offline, writes nothing",
    )
    return parser


_DISPATCH = {
    ("validate", None): cmd_validate,
    ("ingest", "stp"): cmd_ingest_stp,
    ("ingest", "compounds"): cmd_ingest_compounds,
    ("intersect", None): cmd_intersect,
    ("network", None): cmd_network,
    ("enrich", None): cmd_enrich,
    ("report", None): cmd_report,
    ("manifest", None): cmd_manifest,
    ("acquire", None): cmd_acquire,
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
