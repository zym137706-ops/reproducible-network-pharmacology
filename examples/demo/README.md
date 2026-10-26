# RA public-data case: local calculation state

Status: **locally computed, STP tables CC BY 4.0-confirmed, overall public case still blocked by CTD.**
The machine-readable freeze is [`CASE-FREEZE.yaml`](CASE-FREEZE.yaml); acceptance checklist:
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

STP confirmed on **2026-10-23** that the eight native XLSX tables are **CC BY 4.0**, with attribution,
the actual prediction date and no modification of the originals. A local review candidate is at
`C:/DSH/rnp-stp-release-candidate-2026-10-21/`; it is not committed or published.

The CTD disease extract and the detailed results that depend on it remain **local and blocked**:
CTD redistribution/permission is not confirmed. HGNC is CC0 and committed; the private submission
log, compound structures and full permission correspondence are also not public. STP's reply does
not clear CTD, PubChem or mixed-source derived outputs.

Reproduction requires the local materials (`C:\DSH\rnp-case-inputs\handoff-2026-10-21` and
`C:\DSH\rnp-case-inputs\stp`) and the commands recorded in `CASE-FREEZE.yaml` /
`docs/environment.md`; do not upload them to CI without permission.
