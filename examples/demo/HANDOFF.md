# Case handoff: what the researcher must provide

The case is **locally computed but not public-releaseable**. HGNC, the RA disease query, the
background rule, the 8 received STP XLSX files and both threshold runs are prepared locally; CTD/STP
redistribution permission is still missing, so the disease/STP/results remain outside git.

| # | What | Where | Format | Acceptance check | Blocked step |
|---|---|---|---|---|---|
| 1 | CTD disease extract (query/term/inclusion recorded; permission missing) | local: `data/local/case/disease_genes.txt`; repo path `examples/demo/inputs/disease_genes.txt` | one HGNC symbol per line, UTF-8; 179 rows, SHA-256 `321e5441…` | local `validate` passed; public commit requires permission under CTD terms | **public release only** |
| 2 | Eight manual SwissTargetPrediction exports (received) | local `C:\DSH\rnp-case-inputs\stp\<Compound>.xlsx`; pending metadata `inputs/STP-PENDING-SUBMISSIONS.tsv` | native XLSX; explicit `stp_file` bindings | locally verified: 8/8 hash match, 800 rows, 676/740 rows at 0.10/0.05; public redistribution blocked | **public commit/upload only** |
| 3 | Per-compound submission record (received) | local `C:\DSH\rnp-case-inputs\handoff-2026-10-21\STP-SUBMISSION-LOG.tsv`; repo template `inputs/STP-SUBMISSION-LOG.tsv` | TSV; dates/structures/species/hashes | local log verified; submitted date is date-only, retrieval time is file-LastWriteTime proxy; URL/job ID `not_saved` | **public commit only** |
| 4 | HGNC complete-set snapshot | `examples/demo/inputs/hgnc_map.tsv` (provided) | frozen HGNC-derived table, CC0 | release/date/hash/attribution in `HGNC-SOURCE.md` | **provided/frozen** |
| 5 | Conditional enrichment backgrounds (generated) | local `data/local/case/run-2026-10-21/backgrounds/`; repo paths currently absent | `universe-0.10.txt` 239, `universe-0.05.txt` 267 | generated/frozen from T_r; GO effective backgrounds 234/262; mapping loss recorded | **public commit only** |
| 6 | Case licence/source evidence | `examples/demo/CASE-FREEZE.yaml` | fields present | CTD/STP public redistribution not confirmed | **public release only** |

## Local run already completed (not public)

Linux Docker (`bioconductor/bioconductor_docker:RELEASE_3_22`, R 4.5.2, clusterProfiler 4.18.4,
DOSE 4.4.0, org.Hs.eg.db 3.22.0) completed both thresholds. Results are under
`data/local/case/run-2026-10-21/` and are not committed. Independent check recomputed
hypergeometric p-values/BH for 704 (0.10) and 747 (0.05) rows and verified all stage audits and
`manifest --check-inputs` (10 inputs, no drift).

Use [`inputs/STP-SUBMISSION-LOG.tsv`](inputs/STP-SUBMISSION-LOG.tsv) and the pending list
[`inputs/STP-PENDING-SUBMISSIONS.tsv`](inputs/STP-PENDING-SUBMISSIONS.tsv). The eight rows and
`stp_file` names are prefilled; fill the blank columns:

```text
compound  pubchem_cid  stp_file  submitted_structure  structure_source  species
submitted_date  result_file  retrieved_date  operator  result_sha256  notes
```

`submitted_structure` must be the structure actually submitted (SMILES/InChI), not a guessed one.
`species` must be the actual selection (Homo sapiens is expected by the config). `result_sha256` is
the file hash, not a placeholder.

## After inputs arrive

1. Complete `CASE-FREEZE.yaml`: disease fields, data source licences/hashes, STP log, universe.
2. Run `rnp validate --config examples/demo/run.yaml` and fix only real format/binding errors.
3. Run the full chain **in the verified Linux CI environment**:
   `validate → ingest → intersect → network → enrich → report → manifest --check-inputs`.
4. Create independently checked expected counts/tables and only then mark the case frozen/computed.

Do not automate STP submission and do not commit disease/structure data whose terms are unverified.
