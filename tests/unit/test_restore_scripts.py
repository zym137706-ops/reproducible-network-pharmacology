"""Restore entry points: failure propagation and exact library resolution."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
PS = ROOT / "scripts" / "restore_r.ps1"
SH = ROOT / "scripts" / "restore_r.sh"


def test_scripts_have_no_unchecked_r_call() -> None:
    ps = PS.read_text(encoding="utf-8")
    sh = SH.read_text(encoding="utf-8")
    assert ps.count("$LASTEXITCODE") >= 2
    assert "renv bootstrap failed" in ps and "renv restore failed" in ps
    assert "R_LIBRARY=" in ps and "R_LIBRARY=" in sh
    assert "set -euo pipefail" in sh
    assert "renv/library" not in ps  # do not guess the platform/version subdirectory
    assert "R_LIBS=$LIBRARY" in sh


@pytest.mark.skipif(os.name != "nt", reason="PowerShell integration test is Windows-only")
def test_powershell_restore_propagates_failure(tmp_path: Path) -> None:
    fake = tmp_path / "fake-fail.cmd"
    fake.write_text("@echo off\r\nexit /b 7\r\n", encoding="ascii")
    env = dict(os.environ, RNP_RSCRIPT=str(fake))
    completed = subprocess.run(
        [
            shutil.which("powershell.exe") or "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS),
            "-Library",
            str(tmp_path / "lib"),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert "R_LIBS=" not in completed.stdout
    assert "bootstrap failed" in (completed.stdout + completed.stderr)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell integration test is Windows-only")
def test_powershell_restore_propagates_restore_failure(tmp_path: Path) -> None:
    fake = tmp_path / "fake-restore-fail.cmd"
    fake.write_text(
        "@echo off\r\n"
        "if not exist \"%COUNTER%\" (echo 1> \"%COUNTER%\" & exit /b 0)\r\n"
        "exit /b 9\r\n",
        encoding="ascii",
    )
    env = dict(
        os.environ, RNP_RSCRIPT=str(fake), COUNTER=str(tmp_path / "counter")
    )
    completed = subprocess.run(
        [
            shutil.which("powershell.exe") or "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS),
            "-Library",
            str(tmp_path / "lib"),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert completed.returncode != 0
    assert "R_LIBS=" not in completed.stdout
    assert "restore failed" in (completed.stdout + completed.stderr)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell integration test is Windows-only")
def test_powershell_restore_reports_explicit_absolute_library(tmp_path: Path) -> None:
    fake = tmp_path / "fake-ok.cmd"
    fake.write_text(
        "@echo off\r\n"
        "if not exist \"%COUNTER%\" (echo 1> \"%COUNTER%\" & exit /b 0)\r\n"
        "echo R_LIBRARY=%FAKE_LIB%\r\n"
        "exit /b 0\r\n",
        encoding="ascii",
    )
    counter = tmp_path / "counter"
    lib = tmp_path / "explicit-lib"
    env = dict(
        os.environ,
        RNP_RSCRIPT=str(fake),
        COUNTER=str(counter),
        FAKE_LIB=str(lib),
    )
    completed = subprocess.run(
        [
            shutil.which("powershell.exe") or "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS),
            "-Library",
            str(lib),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert f"R_LIBS={lib}" in completed.stdout
    assert f'$env:R_LIBS = "{lib}"' in completed.stdout


@pytest.mark.skipif(os.name != "nt", reason="PowerShell integration test is Windows-only")
def test_powershell_restore_reports_default_library(tmp_path: Path) -> None:
    fake = tmp_path / "fake-default.cmd"
    fake.write_text(
        "@echo off\r\n"
        "if not exist \"%COUNTER%\" (echo 1> \"%COUNTER%\" & exit /b 0)\r\n"
        "echo R_LIBRARY=%FAKE_LIB%\r\n"
        "exit /b 0\r\n",
        encoding="ascii",
    )
    library = tmp_path / "default-resolved-lib"
    env = dict(
        os.environ,
        RNP_RSCRIPT=str(fake),
        COUNTER=str(tmp_path / "counter"),
        FAKE_LIB=str(library),
    )
    completed = subprocess.run(
        [
            shutil.which("powershell.exe") or "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert f"R_LIBS={library}" in completed.stdout
    assert "R_LIBS=\n" not in completed.stdout


def test_shell_restore_propagates_failure(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("POSIX shell integration test")
    fake = tmp_path / "fake-fail.sh"
    fake.write_text("#!/bin/sh\nexit 7\n", encoding="ascii")
    fake.chmod(0o755)
    completed = subprocess.run(
        ["bash", str(SH), str(tmp_path / "lib")],
        capture_output=True,
        text=True,
        env=dict(os.environ, RSCRIPT=str(fake)),
        cwd=ROOT,
        timeout=120,
    )
    assert completed.returncode != 0
    assert "R_LIBS=" not in completed.stdout


def test_shell_restore_propagates_restore_failure(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("POSIX shell integration test")
    fake = tmp_path / "fake-restore-fail.sh"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ ! -f "$COUNTER" ]; then echo 1 > "$COUNTER"; exit 0; fi\n'
        "exit 9\n",
        encoding="ascii",
    )
    fake.chmod(0o755)
    completed = subprocess.run(
        ["bash", str(SH), str(tmp_path / "lib")],
        capture_output=True,
        text=True,
        env=dict(os.environ, RSCRIPT=str(fake), COUNTER=str(tmp_path / "counter")),
        cwd=ROOT,
        timeout=120,
    )
    assert completed.returncode != 0
    assert "R_LIBS=" not in completed.stdout


def test_shell_restore_reports_absolute_default_library(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("POSIX shell integration test")
    fake = tmp_path / "fake-ok.sh"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ ! -f "$COUNTER" ]; then echo 1 > "$COUNTER"; exit 0; fi\n'
        'echo "R_LIBRARY=$FAKE_LIB"\n'
        "exit 0\n",
        encoding="ascii",
    )
    fake.chmod(0o755)
    library = "/tmp/rnp-restore-test-lib"
    completed = subprocess.run(
        ["bash", str(SH)],
        capture_output=True,
        text=True,
        env=dict(
            os.environ,
            RSCRIPT=str(fake),
            COUNTER=str(tmp_path / "counter"),
            FAKE_LIB=library,
        ),
        cwd=ROOT,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert f"R_LIBS={library}" in completed.stdout
    assert f'export R_LIBS="{library}"' in completed.stdout


def test_shell_restore_reports_absolute_explicit_library(tmp_path: Path) -> None:
    if os.name == "nt" or shutil.which("bash") is None:
        pytest.skip("POSIX shell integration test")
    fake = tmp_path / "fake-ok.sh"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ ! -f "$COUNTER" ]; then echo 1 > "$COUNTER"; exit 0; fi\n'
        'echo "R_LIBRARY=$RENV_LIBRARY"\n'
        "exit 0\n",
        encoding="ascii",
    )
    fake.chmod(0o755)
    library = tmp_path / "explicit-lib"
    completed = subprocess.run(
        ["bash", str(SH), str(library)],
        capture_output=True,
        text=True,
        env=dict(os.environ, RSCRIPT=str(fake), COUNTER=str(tmp_path / "counter")),
        cwd=ROOT,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert f"R_LIBS={library}" in completed.stdout


def test_shell_script_is_executable_in_git_index() -> None:
    if shutil.which("git") is None:
        pytest.skip("git not available")
    completed = subprocess.run(
        ["git", "ls-files", "-s", "scripts/restore_r.sh"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        pytest.skip("git index unavailable")
    assert completed.stdout.split()[0] == "100755"
