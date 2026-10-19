"""Compound identity registry and export binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from rnp.errors import InputError
from rnp.io.tables import write_table
from rnp.normalize.identities import (
    REGISTRY_COLUMNS,
    match_exports,
    register_compounds,
)


def _compounds(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "compounds.tsv"
    path.write_text(text, encoding="utf-8")
    return path


def test_new_compounds_get_stable_ids(tmp_path: Path) -> None:
    path = _compounds(tmp_path, "name\tstp_file\nBeta\tb.csv\nAlpha\ta.csv\n")
    records, registry_rows, notes = register_compounds(path, tmp_path / "registry.tsv")
    assert [record.compound_id for record in records] == ["CMP0001", "CMP0002"]
    assert any(note["code"] == "registry_created" for note in notes)
    assert len(registry_rows) == 2


def test_registry_is_reused_across_runs(tmp_path: Path) -> None:
    registry = tmp_path / "registry.tsv"
    write_table(
        registry,
        [
            {
                "compound_id": "CMP0042",
                "group": "all",
                "name": "Alpha",
                "stp_file": "a.csv",
                "submission_id": "S",
                "identity_basis": "new",
                "rule_version": "v0.1.0-name-registry",
                "first_seen_utc": "2026-01-01T00:00:00Z",
                "last_seen_utc": "2026-01-01T00:00:00Z",
                "status": "active",
            }
        ],
        REGISTRY_COLUMNS,
    )
    records, _, _ = register_compounds(
        _compounds(tmp_path, "name\tstp_file\nAlpha\ta.csv\n"), registry
    )
    assert records[0].compound_id == "CMP0042"
    assert records[0].identity_basis == "registry_name"


def test_explicit_compound_id_wins(tmp_path: Path) -> None:
    records, _, _ = register_compounds(
        _compounds(tmp_path, "compound_id\tname\tstp_file\nCMP0099\tAlpha\ta.csv\n"),
        tmp_path / "registry.tsv",
    )
    assert records[0].compound_id == "CMP0099"
    assert records[0].identity_basis == "explicit"


def test_rename_keeps_identity_via_stp_file(tmp_path: Path) -> None:
    registry = tmp_path / "registry.tsv"
    write_table(
        registry,
        [
            {
                "compound_id": "CMP0001",
                "group": "all",
                "name": "Old name",
                "stp_file": "x.csv",
                "submission_id": "S",
                "identity_basis": "new",
                "rule_version": "v0.1.0-name-registry",
                "first_seen_utc": "2026-01-01T00:00:00Z",
                "last_seen_utc": "2026-01-01T00:00:00Z",
                "status": "active",
            }
        ],
        REGISTRY_COLUMNS,
    )
    records, _, notes = register_compounds(
        _compounds(tmp_path, "name\tstp_file\nNew name\tx.csv\n"), registry
    )
    assert records[0].compound_id == "CMP0001"
    assert records[0].identity_basis == "registry_stp_file"
    assert any(note["code"] == "identity_matched_by_stp_file" for note in notes)


def test_missing_stp_file_requires_explicit_compatibility_mode(tmp_path: Path) -> None:
    path = _compounds(tmp_path, "name\nAlpha\n")
    with pytest.raises(InputError) as excinfo:
        register_compounds(path, tmp_path / "registry.tsv")
    assert "explicit stp_file" in excinfo.value.render()
    records, _, _ = register_compounds(
        path, tmp_path / "registry.tsv", allow_filename_match=True
    )
    assert records[0].stp_file == ""


def test_duplicate_name_and_file_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(InputError):
        register_compounds(
            _compounds(tmp_path, "name\tstp_file\nA\ta.csv\nA\tb.csv\n"),
            tmp_path / "registry.tsv",
        )
    with pytest.raises(InputError):
        register_compounds(
            _compounds(tmp_path, "name\tstp_file\nA\tx.csv\nB\tx.csv\n"),
            tmp_path / "registry.tsv",
        )


def test_match_exports_quarantines_unbound_files(tmp_path: Path) -> None:
    records, _, _ = register_compounds(
        _compounds(tmp_path, "name\tstp_file\nAlpha\ta.csv\n"),
        tmp_path / "registry.tsv",
    )
    files = [tmp_path / "a.csv", tmp_path / "extra.csv"]
    bindings, unbound, notes = match_exports(records, files, allow_filename_match=False)
    assert set(bindings) == {"a.csv"}
    assert unbound == [{"path": "extra.csv", "reason": "not_bound_to_compound"}]
    assert notes == []


def test_filename_compatibility_mode_is_recorded(tmp_path: Path) -> None:
    records, _, _ = register_compounds(
        _compounds(tmp_path, "name\nAlpha\n"),
        tmp_path / "registry.tsv",
        allow_filename_match=True,
    )
    bindings, unbound, notes = match_exports(
        records, [tmp_path / "Alpha.csv"], allow_filename_match=True
    )
    assert set(bindings) == {"Alpha.csv"}
    assert unbound == []
    assert any(note["code"] == "filename_compatibility_match" for note in notes)
