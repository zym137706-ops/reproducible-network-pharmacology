# Portable case entry clean-clone run — 2026-10-22

Fixed implementation commit: `2dc39471c1b7913d09c9ea9514b29352fafe268e` (`2dc3947`).
Clean clone: local git clone of that commit; `git status --porcelain` empty.
The same local restricted inputs were mounted read-only; no restricted file entered the clone, image,
CI or repository.

## Fixes exercised

- Submission log is bound by `stp_file`; duplicate/missing/unbound rows are rejected.
- `submitted_structure` is compared with the compound's exact stripped `smiles` before any analysis;
  the real handoff passes this check.
- Source hash uses the versioned `case-source-hash-v2` scope; core/entrypoint/lock/combined hashes are
  recorded separately and caches are excluded.
- The formal `scripts/case_run.py` entry calls `scripts/case_check.py` after both manifest checks;
  `complete` is only set after the independent check succeeds.

## Environment / provenance

| Item | Value |
|---|---|
| Image | `bioconductor/bioconductor_docker:RELEASE_3_22` |
| Image ID / digest | `sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a` |
| Python / R | 3.12.3 / 4.5.2 |
| `renv.lock` / `uv.lock` SHA-256 | `3cf4de10…` / `ce95aeb3…` |
| Source hash (`case-source-hash-v2`, combined) | `67e57b00517df811bfc00d8f007d8b81ec966a5b0993518021a8cea664c641d1` |
| Manifest commit / dirty | `2dc3947` / `false` |
| `case_provenance.json` | status `complete`; checker command recorded; source scope explicit |

## Results

| Item | 0.10 | 0.05 |
|---|---:|---:|
| `T_r` | 239 | 267 |
| Foreground / intersection | 15 / 15 | 17 / 17 |
| Network nodes/edges | 23/67 | 26/74 |
| Effective foreground/background | 15/234 | 17/262 |
| Terms tested | 704 | 747 |
| Significant | 0 | 2 |
| Report SHA-256 | `3629cc1a…` | `a54954e8…` |

All stages `complete`; `manifest --check-inputs` 10 inputs with no drift; independent checker passed
for both thresholds. Report hashes differ from earlier runs because paths/metadata changed; the sets
and counts match the frozen expectations. The earlier 2026-10-21 clean-clone evidence remains
historical and was not rewritten.

## Commands

```bash
uv sync --locked --extra dev
export R_LIBS=<restored-library>
uv run python scripts/case_run.py \
  --compounds <local>/compounds.tsv --stp-dir <local>/stp \
  --disease-genes <local>/disease_genes.txt \
  --hgnc-map examples/demo/inputs/hgnc_map.tsv \
  --log <local>/STP-SUBMISSION-LOG.tsv \
  --out <new-output>
```

The entry runs validate, ingest, backgrounds, intersect, network, enrich, report, manifest and the
independent checker. Local outputs are at `EVID-CLEAN-RUN-2026-10-22/` and are not committed.

## Boundaries

- CTD/STP redistribution permission remains pending; this is a local technical result only.
- No tag/release, visibility change or restricted upload was made.
