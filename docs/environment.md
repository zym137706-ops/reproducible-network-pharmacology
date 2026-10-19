# Verified environment

Recorded 2026-10-19 from the development machine and the GitHub Actions run. Versions are
observations, not a lock for the R side; Python dependencies are locked by `uv.lock`.

## Windows development environment

| Component | Version / note |
|---|---|
| OS | Windows 11 (x86_64) |
| Python | 3.12.5 (`C:\Users\MECHREVO\AppData\Local\Programs\Python\Python312`) |
| uv | 0.12.5 |
| R | 4.5.2 (`C:\Program Files\R\R-4.5.2\bin\Rscript.exe`) |
| clusterProfiler | 4.18.2 |
| DOSE | 4.4.0 |
| org.Hs.eg.db | 3.22.0 |
| VennDiagram | 1.8.2 |
| jsonlite | 2.0.0 |
| openpyxl / jsonschema / PyYAML | 3.1.5 / 4.26.0 / 6.0.3 |

Reproduce the Python side:

```bash
uv sync --locked --extra dev
uv run pytest -q
```

If `Rscript` is not on `PATH`, set `RNP_RSCRIPT` to its absolute path (the test suite and the
enrichment bridge read it).

## Windows R/DOSE exit-status note

`clusterProfiler::bitr` (via DOSE/AnnotationDbi) prints lines such as
`'select()' returned 1:1 mapping between keys and columns` to **stderr**. This is informational:

- `Rscript R/ora.R ...` exits with status **0** in this environment;
- Python `subprocess` sees return code 0 and captures the stderr text;
- Windows PowerShell may still render native-command stderr as a red `NativeCommandError` record,
  which is a shell display issue, not an R failure.

Regression tests: `tests/unit/test_r_environment.py` asserts that a warning keeps exit status 0 and
that the ORA bridge exits 0 while writing the expected meta file. Do not key failure detection on
stderr contents; use the process exit status and the written status/meta fields.

## GitHub Actions

- `lint-test`: Ubuntu, Python 3.10/3.11/3.12, `uv sync --locked --extra dev` (lock file enforced).
- `r-contract`: Ubuntu, R 4.5 + Bioconductor `clusterProfiler`/`org.Hs.eg.db`, system packages
  `libglpk-dev`/`libcurl4-openssl-dev`/`libxml2-dev`/`libssl-dev` (igraph needs GLPK), Python from
  the same lock file.

The R package set is installed by `BiocManager` at CI time and is **not pinned**; the run records
the observed versions in `enrichment_meta.json`. A future release should add an R lock
(`renv.lock` or a dated container) if byte-level reproducibility of enrichment results is required.
