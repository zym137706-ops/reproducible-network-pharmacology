# Public demo inputs: freeze status

This directory contains the recorded compound list only. The other inputs are missing and must not
be substituted:

| Input | Status | Required evidence |
|---|---|---|
| `compounds.tsv` | present (8 PubChem CIDs) | CIDs are public; SMILES are not filled for v0.1 |
| `disease_genes.txt` | **missing** | exact CTD term/query, release, retrieval date, license evidence, SHA-256 |
| `hgnc_map.tsv` | **missing** | HGNC release/date, hash, attribution/license evidence |
| `stp/` exports | **missing** | eight manual SwissTargetPrediction exports + submission/retrieval log; no automation |
| `expected/` | **missing** | only after inputs are frozen and the full chain runs |

See [`CASE-FREEZE.yaml`](../CASE-FREEZE.yaml) for the blocker list and
[`docs/public-case-checklist.md`](../../docs/public-case-checklist.md) for acceptance.
