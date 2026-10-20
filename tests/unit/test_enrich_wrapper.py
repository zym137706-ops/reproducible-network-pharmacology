"""Wrapper-layer exit codes: a non-zero R process is authoritative."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from rnp.analysis.enrich import run_enrich
from rnp.config import load_config
from rnp.errors import ExternalToolError, InputError


def _fake_process(monkeypatch: pytest.MonkeyPatch, *, returncode: int, write_meta: bool):
    def fake_run(command, **_kwargs):  # noqa: ANN001 - mirrors subprocess.run
        group_dir = Path(command[3])
        group_dir.mkdir(parents=True, exist_ok=True)
        if write_meta:
            (group_dir / "enrichment_meta.json").write_text(
                json.dumps({"status": "ok", "counts": {"mapped": 2, "unmapped": 0}}),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(
            command, returncode, stdout="", stderr="simulated native crash"
        )

    monkeypatch.setattr("rnp.analysis.enrich.subprocess.run", fake_run)


def test_nonzero_process_with_normal_meta_is_rejected(
    intersect_run: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, intersect_dir = intersect_run
    _fake_process(monkeypatch, returncode=1, write_meta=True)
    with pytest.raises(ExternalToolError) as excinfo:
        run_enrich(
            load_config(config_path),
            intersect_dir,
            tmp_path / "enrichment",
            rscript=sys.executable,
        )
    rendered = excinfo.value.render()
    assert "R enrichment process failed" in rendered
    assert "R exit code: 1" in rendered
    assert "R meta status: ok" in rendered
    assert excinfo.value.exit_code == 3
    assert not (tmp_path / "enrichment").exists()


def test_signal_like_exit_with_normal_meta_is_rejected(
    intersect_run: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, intersect_dir = intersect_run
    _fake_process(monkeypatch, returncode=137, write_meta=True)
    with pytest.raises(ExternalToolError) as excinfo:
        run_enrich(
            load_config(config_path),
            intersect_dir,
            tmp_path / "enrichment",
            rscript=sys.executable,
        )
    assert "R exit code: 137" in excinfo.value.render()


def test_zero_exit_without_meta_is_rejected(
    intersect_run: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, intersect_dir = intersect_run
    _fake_process(monkeypatch, returncode=0, write_meta=False)
    with pytest.raises(ExternalToolError) as excinfo:
        run_enrich(
            load_config(config_path),
            intersect_dir,
            tmp_path / "enrichment",
            rscript=sys.executable,
        )
    assert "wrote no enrichment_meta.json" in excinfo.value.render()


def test_exit_two_remains_an_input_error(
    intersect_run: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, intersect_dir = intersect_run
    _fake_process(monkeypatch, returncode=2, write_meta=True)
    with pytest.raises(InputError) as excinfo:
        run_enrich(
            load_config(config_path),
            intersect_dir,
            tmp_path / "enrichment",
            rscript=sys.executable,
        )
    assert excinfo.value.exit_code == 2
