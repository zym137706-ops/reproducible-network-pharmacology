# Case inputs, permissions and release handoff

The local RA case is **computed and independently checked**. STP's written confirmation (2026-10-23)
covers the eight native XLSX tables under **CC BY 4.0** with attribution and no modification; a
review-only release candidate is prepared locally. The overall public case remains **blocked** because
CTD permission/redistribution is still pending.

| # | Item | Local evidence | Status |
|---|---|---|---|
| 1 | CTD disease extract | `data/local/case/disease_genes.txt`; 179 genes; query/rules in `inputs/CTD-QUERY.md` | **local prepared/used; public permission pending** |
| 2 | Eight manual STP XLSX exports | external local `stp/`; explicit `.xlsx` bindings; 800 rows; 676/740 at 0.10/0.05 | **CC BY 4.0 confirmed 2026-10-23; candidate prepared; not committed/published** |
| 3 | Completed submission log | external local `STP-SUBMISSION-LOG.tsv`; 8 rows; per-file SHA-256; date-only / LastWriteTime proxy; URL/job ID `not_saved` | **local only; not covered by the STP table clearance; do not publish without separate review** |
| 4 | HGNC snapshot | `examples/demo/inputs/hgnc_map.tsv` (2026-10-16, 45,277 Approved, CC0) | **frozen + committed** |
| 5 | Conditional backgrounds | `data/local/case/run-2026-10-21/backgrounds/`; T_r 239/267; foreground 15/17 | **generated + verified locally; public commit blocked with upstream data** |
| 6 | Licence/source evidence | `docs/stp-permission-2026-10-23.md`; `examples/demo/CASE-FREEZE.yaml` | **STP confirmed tables-only; original EML/screenshot archived locally; CTD pending** |

## STP release candidate

Local, review-only, outside Git:

`C:/DSH/rnp-stp-release-candidate-2026-10-21/`

It contains eight byte-identical XLSX files, `SHA256SUMS.tsv`, `FILES.tsv`, `README.md`,
`ATTRIBUTION.md` and `DATA-LICENSE.md`. The original tables are unmodified; normalization/filtering/
deduplication would be separate derived files. It excludes the private submission log, structures,
CTD data and detailed results. See `docs/stp-permission-2026-10-23.md`.

## Local run already completed (not public)

Linux Docker (`bioconductor/bioconductor_docker:RELEASE_3_22`, R 4.5.2, clusterProfiler 4.18.4,
DOSE 4.4.0, org.Hs.eg.db 3.22.0) completed both thresholds. Current entry point and independent
checker are documented in `docs/case-run.md`; results are under `data/local/case/run-2026-10-21/` and
are not committed. The later clean-clone run is in `docs/case-entry-clean-run-2026-10-22.md`.

## Remaining public-release actions

1. Record CTD's official reply; do not treat silence as permission.
2. Review the local STP candidate and its attribution/hash record; publish only the cleared tables
   and only after the researcher approves the release scope.
3. Keep CTD genes, evidence tables, intersections, networks, enrichment tables and detailed reports
   local until CTD permission is confirmed.
4. If CTD does not permit the subset, publish only code, synthetic examples, the query/filter recipe
   and checksums; keep the public case blocked.
5. Do not publish private submission logs, school/private correspondence or full permission screenshots.
