# Case handoff: what the researcher must provide

The case is **blocked**. These are the only remaining human inputs; do not fabricate them.

| # | What | Where | Format | Acceptance check | Blocked step |
|---|---|---|---|---|---|
| 1 | Exact CTD disease term, query, release, retrieval date, inclusion/exclusion rules and licence evidence | `examples/demo/CASE-FREEZE.yaml` → `disease:`; save genes as `examples/demo/inputs/disease_genes.txt` | one HGNC symbol per line, UTF-8; metadata in freeze fields | `rnp validate` accepts the file; row count and SHA-256 match the freeze; licence is recorded for this release | `validate` (disease input), so everything downstream |
| 2 | Eight manual SwissTargetPrediction exports | `examples/demo/inputs/stp/quercetin.csv` … `chlorogenic-acid.csv` (names fixed in `compounds.tsv`) | native CSV/XLSX export per compound; one file per `stp_file` | `rnp ingest stp` binds all 8 to the explicit `stp_file`; no quarantine/missing; log `SUBMISSION-LOG.tsv` completed with structure/species/date/hash | `ingest stp` → `targets.tsv` |
| 3 | Per-compound submission record | `examples/demo/inputs/stp/SUBMISSION-LOG.tsv` | TSV template; fill every column, including submitted SMILES/InChI, species, date, result file, SHA-256 | no blank required fields; structure/species/date consistent with the actual STP job | `ingest` cannot be called a traceable STP submission |
| 4 | HGNC complete-set snapshot | `examples/demo/inputs/hgnc_map.tsv` | TSV compatible with the existing `hgnc_map` format (symbol/alias/UniProt columns) | `rnp validate` accepts it; release/date/hash/licence recorded in freeze | `intersect` |
| 5 | Explicit enrichment background | `examples/demo/inputs/universe.txt` | one gene symbol/Entrez per line, UTF-8 | `rnp enrich` accepts it; source/selection basis/hash recorded; never the annotated genome | `enrich` |
| 6 | Case licence/source evidence | `examples/demo/CASE-FREEZE.yaml` → `data_sources:` | fields already present; replace nulls with actual URL/release/date/hash/licence | no fabricated values; restricted sources not committed | acceptance as a public case |

## Submission log template

Use [`inputs/stp/SUBMISSION-LOG.tsv`](inputs/stp/SUBMISSION-LOG.tsv). The eight rows and
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
