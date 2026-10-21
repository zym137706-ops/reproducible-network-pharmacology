# Public demo inputs: freeze status

This directory contains the recorded compound list and the frozen HGNC normalization table. The
other scientific inputs are missing and must not be substituted:

| Input | Status | Required evidence |
|---|---|---|
| `compounds.tsv` | present (8 PubChem CIDs) | CIDs are public; SMILES local-only from PubChem |
| `disease_genes.txt` | **missing** | exact CTD term/query, release, retrieval date, license evidence, SHA-256 |
| `hgnc_map.tsv` | present, frozen (CC0) | release/last-modified, hash and attribution in [`HGNC-SOURCE.md`](HGNC-SOURCE.md) |
| `stp/` exports | **missing** | eight manual SwissTargetPrediction exports + submission/retrieval log; no automation |
| `expected/` | **missing** | only after inputs are frozen and the full chain runs |

See [`CASE-FREEZE.yaml`](../CASE-FREEZE.yaml) for the blocker list and
[`docs/public-case-checklist.md`](../../docs/public-case-checklist.md) for acceptance.
