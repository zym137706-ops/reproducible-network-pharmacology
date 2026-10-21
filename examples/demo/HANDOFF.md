# Case inputs and public-release handoff

The local RA case is **computed and independently checked**. No local scientific input is missing.
The only remaining gate is **public redistribution permission** for CTD and STP data/derived tables.
HGNC is CC0 and committed; disease/STP/results stay outside git until permission is clarified.

| # | Item | Local evidence | Status |
|---|---|---|---|
| 1 | CTD disease extract | `data/local/case/disease_genes.txt`; 179 genes; SHA-256 `321e5441…`; query/rules in `inputs/CTD-QUERY.md` | **provided + verified locally**; public commit pending permission |
| 2 | Eight manual STP XLSX exports | external local `stp/` directory; explicit `.xlsx` bindings; 800 rows; 676/740 at 0.10/0.05 | **provided + verified locally**; public redistribution pending |
| 3 | Completed submission log | external local `STP-SUBMISSION-LOG.tsv`; 8 rows; per-file SHA-256; date-only submitted date; LastWriteTime download proxy; URL/job ID `not_saved` | **provided + verified locally**; public commit pending |
| 4 | HGNC snapshot | `examples/demo/inputs/hgnc_map.tsv` (2026-10-16, 45,277 Approved, CC0) | **frozen + committed** |
| 5 | Conditional backgrounds | `data/local/case/run-2026-10-21/backgrounds/`; T_r 239/267; foreground 15/17 | **generated + verified locally**; public commit pending |
| 6 | Licence/source evidence | `examples/demo/CASE-FREEZE.yaml`; CTD legal page; STP Terms of Use | **public-release gate pending** |

## Local run already completed (not public)

Linux Docker (`bioconductor/bioconductor_docker:RELEASE_3_22`, R 4.5.2, clusterProfiler 4.18.4,
DOSE 4.4.0, org.Hs.eg.db 3.22.0) completed both thresholds. Results are under
`data/local/case/run-2026-10-21/` and are not committed. Independent check recomputed
hypergeometric p-values/BH for 704 (0.10) and 747 (0.05) rows and verified all stage audits and
`manifest --check-inputs` (10 inputs, no drift).

The repository's `inputs/STP-SUBMISSION-LOG.tsv` is an intentionally blank **template**; the
completed log is the local handoff file. Do not commit the completed log or XLSX files without
permission. The pending list `inputs/STP-PENDING-SUBMISSIONS.tsv` is public metadata only (CID,
species, expected filename, log row) and contains no structures or predictions.

## After permission clarification

1. Record the official reply; do not treat this handoff or the project record as permission.
2. If permitted, add the covered subset with attribution/licence, then rerun from a clean clone.
3. If not permitted, keep the local case and publish only code, synthetic examples, the query/filter
   recipe and checksums; keep the public-case gate **not passed**.
4. Do not automate STP submission, and do not change the local-completed status into a public-case
   pass without the permission gate.
