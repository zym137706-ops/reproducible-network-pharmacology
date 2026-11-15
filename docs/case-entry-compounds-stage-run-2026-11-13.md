# Case entry with the compounds stage, clean-clone run — 2026-11-13

Fixed implementation commit: `2b6fb52ea8b55ae9b639917f4e5ad8335fc11354` (`2b6fb52`), the last of the five
commits that make `scripts/case_run.py` call `rnp ingest compounds` (unreleased code on local `main`, after
v0.1.0; not yet pushed when the run was made).
Clean clone: a local `git clone --no-hardlinks` of the repository checked out at that commit;
`git status --porcelain` was empty before and after the runs.
Inputs: the `rnp-case-v0.1.0-2026-10-21` case package, extracted outside the clone. Its 35 payload files match
`SHA256SUMS.tsv` (size and SHA-256) and no unlisted file is present. The entry only reads the package; no
restricted file entered the clone or the repository.

This is a local technical record of unreleased code. The final reproduction of the published v0.1.0 remains
`docs/public-candidate-reproduction-2026-10-28.md`.

## What this run exercises

- With `--log`, the preflight runs `rnp ingest compounds` on the real inputs in a temporary directory and
  applies the case policy `case-log-policy-v2` before anything is written to the output directory.
- Each threshold gets a compounds stage (`<out>/<threshold>/run_compounds/`) before
  `rnp ingest stp --compounds`; the stage directory has its own `manifest --check-inputs`.
- `case_provenance.json` records `inputs.log.policy`, `inputs.structures` and `inputs.compounds_stage`.

## Environment / provenance

| Item | Value |
|---|---|
| Host | Windows 11 Home China 10.0.26200, local workstation; **not** the container of the v0.1.0 reproduction (the image fields of the provenance are empty) |
| Python | 3.11.16, the clone's own virtual environment from `uv sync --locked --offline --extra dev --extra chem` (uv 0.12.5, local cache, no network) |
| RDKit | 2026.09.1 (extra `chem`; the version the compounds stage recorded) |
| R | 4.5.2 (2025-10-31, ucrt), default user library (`R_LIBS` unset); **not** the renv-restored library |
| R packages | `clusterProfiler` **4.18.2** installed against 4.18.4 in `renv.lock`; `org.Hs.eg.db` 3.22.0, `AnnotationDbi` 1.72.0, `DOSE` 4.4.0 and `GO.db` 3.22.0 equal to the lock |
| `renv.lock` / `uv.lock` SHA-256 | `08976bc2…` / `a3a94c8c…`, passed to the entry as `RNP_RENV_LOCK_SHA256` / `RNP_UV_LOCK_SHA256` together with `RNP_R_VERSION=4.5.2` |
| Source hash (`case-source-hash-v2`, combined, 56 files) | `b5c04c8d2e59a0937834bc3942411b8e68d5b11f6afc1b13822bd4dfe61cc9d0` |
| Manifest commit / dirty | `2b6fb52` / `false` |
| `case_provenance.json` | status `complete`; 20 commands recorded, the last one is `case_check.py`; `inputs.log.policy` is `case-log-policy-v2` |

## Results

| Item | 0.10 | 0.05 |
|---|---:|---:|
| `T_r` | 239 | 267 |
| Foreground / intersection | 15 / 15 | 17 / 17 |
| Network nodes/edges | 23/67 | 26/74 |
| Effective foreground/background | 15/234 | 17/262 |
| GO terms tested | 704 | 747 |
| Significant | 0 | 2 |
| Report SHA-256 | `9585f327…` | `506aeda9…` |

- Both thresholds `complete`; all stage audits `complete`.
- `manifest --check-inputs`: no drift on any directory (12 inputs for each `run/`, 11 for each `run_compounds/`).
- Independent `case_check.py` passed for both thresholds; the counts equal the frozen `expected/EXPECTED.json`.
- Report hashes depend on paths; the counts are the invariant, as in the 2026-10-28 record.

## Structures and submissions (new in this run)

| Item | 0.10 | 0.05 |
|---|---:|---:|
| Compounds / log rows / STP exports hashed | 8 / 8 / 8 | 8 / 8 / 8 |
| Rows `accepted` / `quarantined` | 8 / 0 | 8 / 0 |
| Submission status | `verified_kind_unstated` × 8 | `verified_kind_unstated` × 8 |
| Warnings | 1 (`stereo_undefined`, Naringenin) | 1 (the same) |
| Stereo status | 5 `none_present`, 2 `defined`, 1 `undefined` | the same |
| `compound_structures.tsv` SHA-256 | `1cd702e2…` | `1cd702e2…` (byte-identical) |
| `compounds_audit.json` SHA-256 | `ac4db10c…` | `a9cef480…` |

Every STP export traces `compound_id → structure_id → submitted SMILES (log) → InChIKey → export SHA-256`. The
InChIKeys were recomputed with RDKit and the export hashes were recomputed from the files; they equal the
log's declared values. The log does not state `export_kind`, hence `verified_kind_unstated` and not
`verified`. The undefined stereocentre of Naringenin is recorded as submitted, not corrected.

## Comparison with the previous entry

The entry at `e359b9d` (no compounds stage) was run on the same inputs and arguments in a separate tree
(a local comparison script, not part of the repository):

- Both entries end `complete`, and the counts of both equal `expected/EXPECTED.json`.
- For each threshold, 15 of the 17 non-JSON result files under `run/` are byte-identical, and so are the files
  under `backgrounds/`. The other two differ as expected: `report.md` is equal apart from path and hash lines;
  `compounds_registered.tsv` has the same columns plus `structure_id` and `structure_status`, and its
  `identity_basis` is `registry_name` instead of `new` because the compounds stage registered the identities
  first.

## CI step

The inline script of the new step "Portable case entry end-to-end with a submission log on synthetic inputs"
was run locally in the same clone and passed. The hosted workflow has not run these commits.

## Commands

```bash
git clone --no-hardlinks <repository> <clone> && git -C <clone> checkout 2b6fb52
cd <clone>
uv sync --locked --offline --extra dev --extra chem
export RNP_R_VERSION=4.5.2 RNP_UV_LOCK_SHA256=<observed> RNP_RENV_LOCK_SHA256=<observed>
uv run --no-sync python scripts/case_run.py \
  --compounds <case>/inputs/compounds.tsv --stp-dir <case>/inputs/stp \
  --disease-genes <case>/inputs/disease_genes.txt --hgnc-map <case>/inputs/hgnc_map.tsv \
  --log <case>/inputs/STP-SUBMISSION-LOG.tsv --config-template <case>/run-0.10.yaml \
  --rscript <R>/bin/Rscript.exe --out <new-output>
```

The recorded run started the same entry with the clone's interpreter (`.venv\Scripts\python.exe
scripts/case_run.py …`) from the comparison script. The outputs (clone, both entries' output directories and
the comparison log) are kept outside the repository and are not committed.

## Not covered

- A container run of this commit. The v0.1.0 reproduction used the Bioconductor image and the renv-restored
  library; this run used the local R with `clusterProfiler` 4.18.2 against the pinned 4.18.4. The counts equal
  the frozen expectations and `case_check.py` recomputed every hypergeometric p-value and BH adjustment on its own,
  but a run with the pinned library was not made.
- The hosted CI workflow, and a Linux run.
- An independent recheck of the submission bindings. `case_check.py` still re-derives the sets and the statistics
  only; the structure layer is judged by `rnp ingest compounds`, in the preflight and in the chain. A recheck by
  the checker is planned, not implemented.

## Boundaries

- Results are predicted associations and annotation overlap, not experimental validation. The structure binding
  records which structure string was submitted for which export; it does not validate a prediction.
- Data terms are unchanged from `docs/public-candidate-reproduction-2026-10-28.md`; real data remain outside Git.
- No tag, release, push, visibility change or restricted upload was made.
