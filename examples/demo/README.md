# RA public-data case: local calculation state

Status: **locally computed, NOT public-releaseable (blocked).** The machine-readable freeze is
[`CASE-FREEZE.yaml`](CASE-FREEZE.yaml); acceptance checklist:
[`docs/public-case-checklist.md`](../../docs/public-case-checklist.md), sources:
[`docs/public-case-sources.md`](../../docs/public-case-sources.md).

## Recorded decisions

- Disease: **Arthritis, Rheumatoid**, exact MeSH **D001172**; no child expansion. CTD
  `genes_curated`, direct `marker/mechanism` or `therapeutic` evidence only; 179 genes. Query and
  rules: [`inputs/CTD-QUERY.md`](inputs/CTD-QUERY.md).
- Eight compounds by PubChem CID; manual STP submission, Homo sapiens; 0.10 main + 0.05 sensitivity.
- HGNC 2026-10-16 snapshot (CC0) with source/hash record; GO BP, BH, explicit conditional background.
- Background rule: `T_r` = HGNC-normalised unique targets before disease; background `T_r`,
  foreground `T_r ∩ D`; see [`inputs/BACKGROUND-RULE.md`](inputs/BACKGROUND-RULE.md).

## Local Linux result (not committed)

Environment: `bioconductor/bioconductor_docker:RELEASE_3_22`, R 4.5.2, clusterProfiler 4.18.4,
DOSE 4.4.0, org.Hs.eg.db 3.22.0. Results: `data/local/case/run-2026-10-21/` (ignored).

| Threshold | Target rows | T_r | Foreground | Intersection | Network | Effective background | Terms | Significant |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | 676 | 239 | 15 | 15 | 23 nodes / 67 edges | 234 | 704 | 0 |
| 0.05 | 740 | 267 | 17 | 17 | 26 nodes / 74 edges | 262 | 747 | 2 |

- 0.10: `completed_no_significant_terms`.
- 0.05: 2 GO BP terms, p.adjust `0.0481978889184172` (conditional enrichment within predicted
  targets; not evidence of mechanism/efficacy).
- Both: `manifest --check-inputs` 10 inputs, no drift; all stage audits complete.
- Independent check: hypergeometric p and BH recomputed for all 704/747 result rows; T_r/foreground
  rederived from targets + HGNC + CTD genes. Passed.

## Why it is not public

The CTD disease extract, STP XLSX files, submission log and result tables are **local only**:
CTD/STP redistribution permission is not confirmed. HGNC is CC0 and committed; provenance/rule
records are committed. Local computation does not equal public-release clearance.

Reproduction requires the local materials (`C:\DSH\rnp-case-inputs\handoff-2026-10-21` and
`C:\DSH\rnp-case-inputs\stp`) and the commands recorded in `CASE-FREEZE.yaml` /
`docs/environment.md`; do not upload them to CI without permission.
