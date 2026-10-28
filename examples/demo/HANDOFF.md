# Case inputs, permissions and release handoff

The local RA case is **computed, independently checked, and reproduced from a clean clone**. STP's
2026-10-23 reply confirms **CC BY 4.0** for the eight native XLSX tables with attribution and no
modification. CTD ticket **#8545** (2026-10-26) confirms **public non-profit research including
GitHub** for the requested 179-gene RA subset and derived outputs, with CTD citation and a data
date-stamp; commercial use is separate. A complete review candidate is prepared outside Git, but
nothing is published, and **PubChem source/terms review is complete with a residual third-party
caveat; structure publication remains a researcher decision**.

| # | Item | Local evidence | Status |
|---|---|---|---|
| 1 | CTD disease extract | `data/local/case/disease_genes.txt`; 179 genes; query/rules in `inputs/CTD-QUERY.md` | **permission confirmed; candidate local; not committed** |
| 2 | Eight manual STP XLSX exports | external local `stp/`; explicit `.xlsx` bindings; 800 rows; 676/740 at 0.10/0.05 | **CC BY 4.0 confirmed 2026-10-23; candidate prepared; not published** |
| 3 | Completed submission log | external local `STP-SUBMISSION-LOG.tsv`; 8 rows; per-file SHA-256; date-only / LastWriteTime proxy; URL/job ID `not_saved` | **de-identified review copy; not yet cleared for public release** |
| 4 | HGNC snapshot | `examples/demo/inputs/hgnc_map.tsv` (2026-10-16, 45,277 Approved, CC0) | **frozen + committed** |
| 5 | Conditional backgrounds | `data/local/case/run-2026-10-21/backgrounds/`; T_r 239/267; foreground 15/17 | **generated + verified locally; candidate copy prepared** |
| 6 | Licence/source evidence | `docs/stp-permission-2026-10-23.md`; `docs/ctd-permission-2026-10-26.md`; `examples/demo/CASE-FREEZE.yaml` | **STP and CTD confirmed for requested scope; private EMLs local; publication pending** |

## Complete public case candidate

Local, review-only, outside Git:

`C:/DSH/rnp-public-case-candidate-2026-10-21/`

It contains relative-path `run-0.10.yaml`/`run-0.05.yaml`, STP XLSX, compounds with actual submitted
structures, de-identified submission log, CTD genes/evidence/query metadata, HGNC, both universes and
foregrounds, PubChem per-CID provenance/source note, permissions, citations, expected counts and
`SHA256SUMS.tsv`. It has **35 payload files + 1 checksum manifest = 36 total** and was reproduced
from clean commit `49c86ee`; see `docs/public-candidate-reproduction-2026-10-28.md`. The versioned
zip is `C:/DSH/rnp-case-v0.1.0-2026-10-21.zip` (SHA-256 `5fe85b4e…`). Private EMLs, screenshots,
full headers, school email and IP/session data are excluded.

## Local run already completed (not public)

Linux Docker (`bioconductor/bioconductor_docker:RELEASE_3_22`, R 4.5.2, clusterProfiler 4.18.4,
DOSE 4.4.0, org.Hs.eg.db 3.22.0) completed both thresholds. Current entry point and independent
checker are documented in `docs/case-run.md`; results are under `data/local/case/run-2026-10-21/` and
are not committed.

## Remaining publication actions

1. Researcher reviews the complete candidate and explicitly decides data inclusion, repository
   visibility and versioned release.
2. Review the completed PubChem source/terms/citation record and decide whether the structure table
   is published; the review is complete, with a residual third-party-rights caveat.
3. If published, cite CTD with a data date-stamp and notify CTD of the public link.
4. Do not relabel CTD data as MIT/CC0/CC BY or claim commercial rights; keep code and data licenses
   separate.
5. Preserve the STP original tables unmodified and include attribution/citation.
6. Do not publish private EMLs/screenshots/headers, school/private correspondence or IP/session data.
