# Demo: public compounds (filled in week 2)

The end-to-end public demo is scheduled for week 2. `run.yaml` is the target contract; two inputs
are filled manually:

1. `inputs/stp/` — SwissTargetPrediction exports, submitted by hand (see `inputs/README.md`).
2. `inputs/disease_genes.txt` — a CTD gene list with source and retrieval date.

Until then, use the self-contained fixture:

```bash
rnp validate --config tests/fixtures/run/run.yaml
```

## Data provenance

| Input | Source | Retrieved | License |
|---|---|---|---|
| compounds | PubChem CIDs (to be filled) | | public |
| STP exports | SwissTargetPrediction (manual submission) | | service terms |
| disease genes | CTD | | academic use, cite CTD |
| STRING PPI | STRING v12.0 | | CC BY 4.0 |
| enrichment | GO (offline) / KEGG (opt-in) | | CC BY 4.0 / KEGG terms |

## What the demo is expected to prove

- a stranger can clone the repository, install it and reproduce every table from public inputs;
- the run manifest explains exactly which files, versions and parameters produced the tables;
- known failure modes are visible in the audit rather than hidden.
