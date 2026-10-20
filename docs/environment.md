# Verified environment

Updated 2026-10-20 after a clean-library reproduction. Python is locked by `uv.lock`; R is locked
by `renv.lock` (generated from the verified clean library, not from an unverified/failed one).

## Windows development machine (host)

| Component | Version / note |
|---|---|
| OS | Windows 11 (x86_64) |
| Python | 3.12.5 |
| uv | 0.12.5 |
| R | 4.5.2 (`C:\Program Files\R\R-4.5.2\bin\Rscript.exe`) |
| clusterProfiler (host library) | 4.18.2 |
| DOSE | 4.4.0 |
| org.Hs.eg.db | 3.22.0 |
| VennDiagram | 1.8.2 |
| jsonlite | 2.0.0 |

## Clean R library (pak-installed, isolated)

A fresh `R_LIBS` directory was populated by `pak` from CRAN + Bioconductor 3.22, without reusing
the host user library, and the bridge tests were run against it:

| Component | Clean-library version |
|---|---|
| R | 4.5.2 |
| clusterProfiler | 4.18.4 |
| DOSE | 4.4.0 |
| org.Hs.eg.db | 3.22.0 |
| GO.db | 3.22.0 |
| AnnotationDbi | 1.72.0 |
| jsonlite | 2.0.0 |

The clean-library run passed 25 R-dependent tests (bridge, synthetic hypergeometric/BH benchmark,
enrichment, report) in 3 min 48 s. Some binaries warned that they were built under R 4.5.3; the
bridge ran successfully on 4.5.2. The lockfile records the clean-library versions.

## Locked environment

```bash
uv sync --locked --extra dev          # Python
Rscript -e 'renv::restore(lockfile="renv.lock", prompt=FALSE)'   # R
```

`renv.lock` records R 4.5.2 and 121 packages including `clusterProfiler`, `DOSE`, `GO.db`,
`org.Hs.eg.db` and their dependencies. The lock was generated **after** the clean-library tests
passed, so it does not enshrine a broken host library.

Note: a second local restore into a fresh Windows library failed while source-building `curl`
(its bundled download hit a GitHub SSL error under the local proxy). That is a network/build
limitation of this machine, not a test result; CI restores the same lock on a clean Ubuntu runner.
Do not treat a failed restore as a successful environment snapshot.

## "Native exit" and stderr: what was actually observed

The observed red output from Windows PowerShell was `'select()' returned 1:1 mapping...` on
**stderr**, not an R failure:

- `Rscript R/ora.R ...` exits **0**, and Python `subprocess` sees 0;
- PowerShell renders native-command stderr as `NativeCommandError`; that is shell presentation;
- a real R process can nevertheless die with a non-zero status (kill, native crash, wrapper
  failure) after writing a normal-looking `enrichment_meta.json`.

The previous wrapper only special-cased exit code 2 and otherwise trusted the meta file, so a
process with status 1/137 and a plausible meta could have been reported as success. The clean
library did not reproduce a genuine native non-zero exit, so the fix is guarded by simulated
regression tests in `tests/unit/test_enrich_wrapper.py`: any non-zero R exit is authoritative
(exit code 2 remains an input/background error; other statuses become a partial/external-tool
failure with the R status and stderr), and exit 0 without meta is also rejected.

## Reproduction commands

```powershell
uv sync --locked --extra dev
$env:RNP_RSCRIPT = "C:\Program Files\R\R-4.5.2\bin\Rscript.exe"
uv run pytest -q
uv run ruff check .
```

For the clean-library variant, set `R_LIBS` to that isolated library before running the R-dependent
tests; never point it at the host library while claiming a clean environment.

## GitHub Actions

- `lint-test`: Ubuntu, Python 3.10/3.11/3.12, `uv sync --locked --extra dev`.
- `r-contract`: Ubuntu, R 4.5, `renv::restore()` from `renv.lock`, system packages
  `libglpk-dev`/`libcurl4-openssl-dev`/`libxml2-dev`/`libssl-dev` (igraph needs GLPK). The restored
  library is exposed to Python subprocesses via `R_LIBS`.

The R bridge records the observed versions in `enrichment_meta.json` on every run; the lock is the
declared version set, and CI is the clean-environment restore check.
