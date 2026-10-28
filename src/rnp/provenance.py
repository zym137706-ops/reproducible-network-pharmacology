"""Provenance helpers: hashing, environment capture, run manifests."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from . import __version__

DIST_NAME = "reproducible-network-pharmacology"
_TRACKED_DISTRIBUTIONS = ("openpyxl", "jsonschema", "PyYAML")


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now_iso() -> str:
    """Second-resolution UTC timestamp, e.g. ``2026-10-18T05:00:00Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def package_version(distribution: str = DIST_NAME) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return __version__


def dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in _TRACKED_DISTRIBUTIONS:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "missing"
    return versions


def git_state(cwd: str | Path | None = None) -> dict[str, Any]:
    """Return ``{commit, dirty}`` if the working tree is a git repository."""
    working_dir = str(cwd or Path.cwd())
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return {"commit": commit or None, "dirty": bool(status)}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def environment() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "dependencies": dependency_versions(),
    }


def input_records(paths: list[Path]) -> list[dict[str, Any]]:
    records = []
    for path in paths:
        if path.is_file():
            records.append(
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    return records


def code_root() -> Path:
    """Repository root of the installed package source (not the config location)."""
    return Path(__file__).resolve().parents[2]


def code_identity() -> dict[str, Any]:
    root = code_root()
    state = git_state(root)
    identity: dict[str, Any] = {
        "version": package_version(),
        "commit": state["commit"],
        "dirty": state["dirty"],
        "root": str(root),
    }
    source_sha = os.environ.get("RNP_CODE_SOURCE_SHA256")
    if source_sha:
        identity["source_attestation"] = {
            "origin": "host_declared",
            "source_sha256": source_sha,
            "scope": os.environ.get("RNP_CODE_SOURCE_SCOPE") or None,
            "declared_commit": os.environ.get("RNP_CODE_DECLARED_COMMIT") or None,
            "declared_dirty": (
                os.environ.get("RNP_CODE_DECLARED_DIRTY", "").lower() in {"true", "1", "yes"}
                if os.environ.get("RNP_CODE_DECLARED_DIRTY")
                else None
            ),
            "note": (
                "supplied by the host/runner; git fields above are read from the checkout "
                "if available"
            ),
        }
    return identity


def container_identity() -> dict[str, Any]:
    """Container/environment declarations supplied by the host runner.

    These values are not inferred from the container. A runner that cannot establish a value leaves
    it out; it must not fabricate a digest or a restored-library version.
    """
    keys = {
        "image": "RNP_CONTAINER_IMAGE",
        "image_id": "RNP_CONTAINER_IMAGE_ID",
        "image_digest": "RNP_CONTAINER_IMAGE_DIGEST",
        "image_platform": "RNP_CONTAINER_IMAGE_PLATFORM",
        "image_manifest_digest": "RNP_CONTAINER_IMAGE_MANIFEST_DIGEST",
        "image_config_digest": "RNP_CONTAINER_IMAGE_CONFIG_DIGEST",
        "python": "RNP_CONTAINER_PYTHON",
        "r_version": "RNP_R_VERSION",
        "r_lib": "RNP_R_LIB",
        "renv_lock_sha256": "RNP_RENV_LOCK_SHA256",
        "uv_lock_sha256": "RNP_UV_LOCK_SHA256",
    }
    identity = {key: os.environ.get(env) for key, env in keys.items() if os.environ.get(env)}
    return identity


def config_identity(config) -> dict[str, Any]:
    state = git_state(config.base_dir)
    return {
        "path": str(config.path),
        "sha256": config.sha256,
        "repository": {"commit": state["commit"], "dirty": state["dirty"]},
    }


def build_manifest(
    *,
    run_id: str,
    command: str,
    args: dict[str, Any],
    config,
    inputs: list[Path],
    parents: list[dict[str, Any]] | None = None,
    references: dict[str, str] | None = None,
    started_at: str,
    finished_at: str,
    exit_code: int,
    stage_status: str,
    r_version: str | None = None,
    overwritten: bool = False,
) -> dict[str, Any]:
    """Build a manifest that satisfies ``schemas/run_manifest.schema.json``.

    Code identity (this package's repository) and config identity (where the run
    configuration lives) are recorded separately: a config stored outside the code
    repository must not borrow the code commit as its own identity.
    """
    env = environment()
    manifest = {
        "schema_version": "2.0",
        "run_id": run_id,
        "tool": {"name": DIST_NAME, "version": package_version()},
        "code": code_identity(),
        "config": config_identity(config),
        "python": env["python"],
        "dependencies": env["dependencies"],
        "command": command,
        "args": args,
        "parents": parents or [],
        "inputs": input_records(inputs),
        "references": references or config.data.get("references", {}),
        "r_version": r_version,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "exit_code": exit_code,
        "stage_status": stage_status,
        "overwritten": overwritten,
        # platform strings are informative only; keep them out of tables.
        "platform": env["platform"],
    }
    container = container_identity()
    if container:
        manifest["container"] = container
    return manifest


def write_json(path: str | Path, payload: Any) -> None:
    """Write UTF-8 JSON atomically (no partial files on failure)."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)
