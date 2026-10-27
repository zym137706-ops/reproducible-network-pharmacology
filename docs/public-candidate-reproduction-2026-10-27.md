# Public case candidate reproduction — 2026-10-27

This run used the complete local candidate, not a new STP/CTD download. Fixed commit:
`90f317869e97aef96904b872af9f8eefde5a2927` (`90f3178`); clean clone; `git status` empty.
Candidate: `C:/DSH/rnp-public-case-candidate-2026-10-21/`.

## Environment and commands

- Image: `bioconductor/bioconductor_docker:RELEASE_3_22`
- R 4.5.2; clusterProfiler 4.18.4; DOSE 4.4.0; org.Hs.eg.db 3.22.0
- Source hash (`case-source-hash-v2` combined): `67e57b00517df811bfc00d8f007d8b81ec966a5b0993518021a8cea664c641d1`
- Manifest: commit `90f3178`, `dirty=false`
- Entry: `scripts/case_run.py` with candidate compounds, STP exports, de-identified log, CTD genes and
  HGNC; it ran both thresholds, both manifest checks and `scripts/case_check.py`.

## Result

| Item | 0.10 | 0.05 |
|---|---:|---:|
| `T_r` | 239 | 267 |
| Foreground / intersection | 15 / 15 | 17 / 17 |
| Network nodes/edges | 23/67 | 26/74 |
| Effective foreground/background | 15/234 | 17/262 |
| GO terms tested | 704 | 747 |
| Significant | 0 | 2 |
| Report SHA-256 | `fea3a98e…` | `997ed7bf…` |

- Generated universes match the supplied candidate universe hashes exactly.
- `manifest --check-inputs`: 10 inputs, no drift for each threshold.
- Independent checker passed; all stage statuses complete.
- Report hashes vary with paths/time and are not cross-run equality tests.

Candidate local output: `C:/DSH/rnp-public-candidate-run-2026-10-27/` (not committed).

## Boundaries

- Results are predicted associations/annotation overlap, not experimental validation.
- STP tables CC BY 4.0; CTD public non-profit research permission (ticket #8545) with citation and
  date-stamp; PubChem structure terms remain pending; no MIT/CC relicense.
- The candidate is review-only and not published. No tag/release/visibility change was made.
