# Verified environment

Updated 2026-11-02 for the published v0.1.0 release. **Linux CI is the verified case
environment. Windows is not verified** because of a native R exit (`0xC0000005`) that is still open;
the non-zero exit guard stays in place.

## Authoritative status

| Environment | Result | Status |
|---|---|---|
| Linux GitHub Actions (current `main` run; see README badge) | `renv::restore` from `renv.lock`; Python 3.10/3.11/3.12 tests and full synthetic enrich→report quickstart passed; current run linked in the release record | **verified for machinery** |
| Local Linux Docker (2026-10-28) | final candidate commit `49c86ee`; source hash `fc6784e6…`; image tag `bioconductor/bioconductor_docker:RELEASE_3_22`, index/`.Id` `sha256:e341…`, platform `linux/amd64`, manifest `sha256:67ab…`, config `sha256:7da6…`; both RA thresholds + independent checker complete; expected counts unchanged | **verified for the final case candidate** |
| Linux GitHub Actions (historical, run 39415883483) | `renv::restore`; 4/4 jobs success; synthetic quickstart | historical **verified for machinery** |
| Local Linux Docker (2026-10-22) | clean-clone `2dc3947`; `case-source-hash-v2` combined `67e57b00…`; both RA thresholds + checker complete | historical |
| Windows local working tree | 138 passed once (4 min 25 s) | one non-reproducible pass; not a stable Windows result |
| Windows host / isolated library (Codex, commit `0cf3584`) | 119 passed, 11 failed; R subprocess exit `3221225477` (`0xC0000005`) even when status/results looked normal | **unverified / blocked** |

The RA case was computed locally in Linux Docker. STP/CTD permission is confirmed for the requested
public non-profit scope, and the complete case package is published as the v0.1.0 release asset; local
computation is not a public release. See `examples/demo/CASE-FREEZE.yaml` and
`docs/public-candidate-reproduction-2026-10-28.md`.

## Install R 4.5.x, restore the lock, select the library

Python:

```bash
uv sync --locked --extra dev
```

R (Linux/macOS):

```bash
# system build dependencies for igraph/curl/xml/graphics packages
sudo apt-get install -y libglpk-dev libcurl4-openssl-dev libxml2-dev libssl-dev \
  libfontconfig1-dev libfreetype6-dev libharfbuzz-dev libfribidi-dev \
  libpng-dev libtiff5-dev libjpeg-dev libzstd-dev libbz2-dev liblzma-dev

# explicit bootstrap + restore; optional argument selects an isolated library
scripts/restore_r.sh
# or: scripts/restore_r.sh /abs/path/rlib
```

Windows PowerShell:

```powershell
.\scripts\restore_r.ps1
# or: .\scripts\restore_r.ps1 -Library C:\path\to\rlib
```

Library selection rules:

1. The restore target must be explicit. `renv::restore(library=...)` or a project `renv/library` is
   the only accepted R library.
2. For Python subprocesses, export the **same** library so `Rscript` sees it:
   `export R_LIBS=/abs/path/rlib` (Linux) or `$env:R_LIBS = "C:\path\to\rlib"` (Windows).
3. Never point `R_LIBS` at the host user library and call it a clean environment.
4. Verify before running:

```bash
Rscript -e '.libPaths(); packageVersion("clusterProfiler"); packageVersion("DOSE"); packageVersion("org.Hs.eg.db")'
```

The lock (`renv.lock`) records R 4.5.2 and 121 packages, including clusterProfiler 4.18.4,
DOSE 4.4.0, org.Hs.eg.db 3.22.0, GO.db 3.22.0, AnnotationDbi 1.72.0 and jsonlite 2.0.0. It was
generated **after** the clean-library tests, not from an unverified/failed library.

A local second restore into a fresh Windows library failed while source-building `curl` (its
bundled download hit a GitHub SSL error under the local proxy). That is a Windows network/build
limitation; the Linux CI restore of the same lock succeeded and is the recorded clean-restore
evidence.

## Windows native exit: observed, not suppressed

Codex reproduced the real process status on commit `0cf3584` with
`RNP_RSCRIPT=<R_HOME>\bin\Rscript.exe` and `R_LIBS=<rlib>`:

- R subprocess exit `3221225477` (`0xC0000005`) while `enrichment_meta.json` said `status=ok` and
  result files were written;
- also reproduced with `--vanilla`, `LC_ALL=C`, `LANG=C`, and nonexistent `R_LIBS_USER`/`R_LIBS_SITE`;
- all 121 locked package versions matched the library;
- 11 R-dependent tests failed, all because the process did not exit cleanly.

The earlier red `'select()' returned 1:1 mapping...` output is stderr display, not the cause. The
wrapper now treats every non-zero status as authoritative: `2` remains input/background error, other
statuses become an external-tool/partial failure (exit 3), and exit 0 without meta is rejected.
`tests/unit/test_enrich_wrapper.py` covers rc=1/137 with a normal-looking meta.

Windows root cause is **not fixed** in this round. Do not use Windows to claim a verified case; do
not relax the exit-code check. Use Linux CI for case computation.

## Reproduction commands

```powershell
cd <repo>
uv sync --locked --extra dev
.\scripts\restore_r.ps1 -Library <rlib>
$env:R_LIBS = "<rlib>"
$env:RNP_RSCRIPT = "<R_HOME>\bin\Rscript.exe"
uv run ruff check .
uv run pytest -q
```

On Linux CI the same steps are used with `scripts/restore_r.sh` and `R_LIBS` exported to the
restored library. The Windows run above is expected to remain blocked by the native exit until the
root cause is fixed; keep the failures visible.

## GitHub Actions

- `lint-test`: Ubuntu, Python 3.10/3.11/3.12, `uv sync --locked --extra dev`.
- `r-contract`: Ubuntu, R 4.5; **calls `bash scripts/restore_r.sh "$RUNNER_TEMP/rlib"`** from
  `renv.lock`, exports the exact absolute path it prints as `R_LIBS`, verifies a Python-launched
  `Rscript` sees that library, then runs live bridge/enrichment/report tests and the full quickstart.
  The CI path is the same script documented for users, not a separate inline restore.

CI records the observed R versions in `enrichment_meta.json` on every run; `renv.lock` is the
declared version set.
