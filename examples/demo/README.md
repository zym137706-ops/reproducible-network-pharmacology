# RA public-data case: local calculation state

Status: **locally computed; STP CC BY 4.0 and CTD public non-profit research permission confirmed;
complete candidate prepared; publication decision pending.** The machine-readable freeze is
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

## Publication status

STP confirmed on **2026-10-23** that the eight native XLSX tables are **CC BY 4.0**, with attribution,
the actual prediction date and no modification of the originals. CTD confirmed on **2026-10-26**
(ticket **#8545**) that the requested 179-gene RA subset and derived outputs may be used for public
non-profit research including GitHub, with CTD citation and a data date-stamp; commercial use is
separate. The complete review candidate is at
`C:/DSH/rnp-public-case-candidate-2026-10-21/` and is outside Git.

The candidate has been reproduced from a clean clone; its expected counts are recorded there.
Publication remains pending the researcher's explicit decision on data inclusion, repository
visibility and release. PubChem structure/source terms are still separately pending and are not
cleared by the STP/CTD replies. HGNC is CC0 and committed; private EMLs, screenshots, submission
correspondence and full logs remain uncommitted.

Reproduction uses the complete candidate or the local materials
(`C:\DSH\rnp-case-inputs\handoff-2026-10-21` and `C:\DSH\rnp-case-inputs\stp`) with the commands
recorded in `CASE-FREEZE.yaml` / `docs/environment.md`; do not upload private material to CI.
