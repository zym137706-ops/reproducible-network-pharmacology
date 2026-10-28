# Clean-clone case run — 2026-10-21

Fixed commit: `e81f5bf1e584b98355229df2b31f21297a560f54` (`e81f5bf`)
Clone: local git clone of that commit; `git status --porcelain` empty before the run.
Local restricted inputs were mounted read-only from outside the clone; no restricted file was added
to the clone, image layer, CI or repository.

## Environment

| Item | Value |
|---|---|
| Linux image | `bioconductor/bioconductor_docker:RELEASE_3_22` |
| Image ID / digest | `sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a` / `bioconductor/bioconductor_docker@sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a` |
| Python | 3.12.3 |
| R | 4.5.2; clusterProfiler 4.18.4; DOSE 4.4.0; org.Hs.eg.db 3.22.0 |
| Restored R library | `/rlib` from the project `renv.lock` |
| `renv.lock` SHA-256 | `3cf4de1000b298f79257b7d3ac264a0e0919f5dcd77da8a50b729f6388e8ad9d` |
| `uv.lock` SHA-256 | `ce95aeb3a29342264afbddb145266e7676681fc788e65fb58b11c3d7d0177b11` |
| Source-content SHA-256 | `f271a2f792b595aebc6bcba1689867d018262b78abe41dc59bc517cab5b2cafa` |
| Git state in manifest | commit `e81f5bf`, dirty `false` |

`case_provenance.json` records the image/digest, restored library, lock hashes, source hash and input
hashes; each stage `run_manifest.json` carries the same `container` and `code.source_attestation`
fields. The source hash was supplied by the runner and is labelled `host_declared`; the commit/dirty
fields were read from the mounted `.git`.

## Commands

The reusable orchestrator was used from the clean clone:

```text
uv run python scripts/case_run.py \
  --compounds <local>/compounds.tsv --stp-dir <local>/stp \
  --disease-genes <local>/disease_genes.txt \
  --hgnc-map examples/demo/inputs/hgnc_map.tsv \
  --log <local>/STP-SUBMISSION-LOG.tsv --out <new output>
```

It ran, per threshold: `validate → ingest → build_case_background.py → intersect → network →
enrich → report → manifest --check-inputs`, then the independent checker. Configs were written before
ingest and not changed afterwards.

## Results

| Item | 0.10 | 0.05 |
|---|---:|---:|
| Thresholded prediction rows | 676 | 740 |
| Unique normalized targets `T_r` | 239 | 267 |
| Disease foreground | 15 | 17 |
| Intersection | 15 | 17 |
| Network nodes/edges | 23/67 | 26/74 |
| Effective foreground/background | 15/234 | 17/262 |
| GO terms tested | 704 | 747 |
| Significant terms | 0 | 2 |
| Enrichment status | `completed_no_significant_terms` | `ok` |
| Report SHA-256 | `d16209e8…` | `2f8021c1…` |

All stages were `complete`; `manifest --check-inputs` checked **10 inputs with no drift** for each
threshold. The independent checker re-derived `T_r`/foreground from targets + HGNC + disease and
recomputed all 704/747 hypergeometric p-values and BH adjustments; it passed. Report hashes differ
from the earlier 2026-10-21 run because the report embeds run path/time context; sets/counts match.
The 0.05 significant terms remain conditional enrichment within predicted targets, not mechanism or
efficacy evidence.

Local outputs: `EVID-CLEAN-RUN-2026-10-21/` (not committed). Provenance:
`case_provenance.json`; independent check: `independent-check.json`.

## Clean-clone synthetic quickstart

The same clean clone also ran the full synthetic quickstart in Linux:

- `validate → ingest → intersect → network → enrich → report → manifest --check-inputs` all complete;
- 4 inputs checked, no drift; enrichment effective foreground/background **2/30**, 558 terms,
  0 significant; report SHA-256 `fcde6cd3…`;
- selected Skill tests (`tests/unit/test_skill.py`, `tests/skill/test_skill_scenarios.py`) passed
  (11 tests).

## Boundaries

- The local case is not public-releaseable: CTD/STP permission is pending.
- The Windows native R `0xC0000005` remains unverified; this run used Linux.
- No source tag/release, visibility change or restricted-data upload was made.
