"""Provenance fields must be explicit and schema-valid, never invented."""

from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest

from rnp.config import load_schema
from rnp.provenance import build_manifest, code_identity, container_identity


class _Config:
    path = Path("run.yaml")
    sha256 = "a" * 64
    base_dir = Path(".")
    data = {"references": {}}


def test_host_attestation_is_labelled_and_not_a_git_claim(monkeypatch) -> None:
    monkeypatch.setenv("RNP_CODE_SOURCE_SHA256", "b" * 64)
    monkeypatch.setenv("RNP_CODE_DECLARED_COMMIT", "deadbeef")
    monkeypatch.setenv("RNP_CODE_DECLARED_DIRTY", "true")
    identity = code_identity()
    attestation = identity["source_attestation"]
    assert attestation["origin"] == "host_declared"
    assert attestation["declared_commit"] == "deadbeef"
    assert attestation["declared_dirty"] is True
    assert identity["commit"] != "deadbeef" or identity["commit"] is None


def test_container_identity_is_only_what_the_host_supplied(monkeypatch) -> None:
    monkeypatch.setenv("RNP_CONTAINER_IMAGE", "bioconductor/test:1")
    monkeypatch.setenv("RNP_CONTAINER_IMAGE_DIGEST", "sha256:" + "c" * 64)
    monkeypatch.setenv("RNP_R_VERSION", "4.5.2")
    identity = container_identity()
    assert identity["image"].endswith(":1")
    assert identity["r_version"] == "4.5.2"
    assert "r_lib" not in identity


def test_manifest_schema_accepts_attestation_and_container(monkeypatch) -> None:
    monkeypatch.setenv("RNP_CODE_SOURCE_SHA256", "b" * 64)
    monkeypatch.setenv("RNP_CONTAINER_IMAGE_DIGEST", "sha256:" + "c" * 64)
    manifest = build_manifest(
        run_id="test",
        command="validate",
        args={},
        config=_Config(),
        inputs=[],
        started_at="2026-10-21T00:00:00Z",
        finished_at="2026-10-21T00:00:01Z",
        exit_code=0,
        stage_status="complete",
    )
    jsonschema.validate(manifest, load_schema("run_manifest"))
    assert manifest["code"]["source_attestation"]["origin"] == "host_declared"
    assert manifest["container"]["image_digest"].startswith("sha256:")


def test_manifest_schema_rejects_bad_digest() -> None:
    manifest = build_manifest(
        run_id="test",
        command="validate",
        args={},
        config=_Config(),
        inputs=[],
        started_at="2026-10-21T00:00:00Z",
        finished_at="2026-10-21T00:00:01Z",
        exit_code=0,
        stage_status="complete",
    )
    manifest["container"] = {"renv_lock_sha256": "not-a-hash"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, load_schema("run_manifest"))
