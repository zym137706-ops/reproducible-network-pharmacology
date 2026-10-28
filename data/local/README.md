# Local reference data

Downloaded reference data lives here and is **never committed** (see `.gitignore`).
Record each snapshot in `../SOURCES.yaml` with its release, retrieval date and SHA-256.

Typical layout:

```text
data/local/
  hgnc/
    hgnc_complete_set_<date>.txt
  go/
    go-basic_<date>.obo
  ctd/
    CTD_genes_diseases.tsv
```

The complete RA case inputs are distributed separately as `rnp-case-v0.1.0-2026-10-21.zip`;
see `examples/demo/DATA-ACCESS.md`.
