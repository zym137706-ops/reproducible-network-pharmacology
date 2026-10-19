# Public-data demo (week 2)

This directory will hold the end-to-end public demo:

```
inputs/
  compounds.tsv        # 8 public compounds (PubChem CIDs), SMILES filled from PubChem
  disease_genes.txt    # CTD export, source and date recorded in run.yaml
  stp/                 # SwissTargetPrediction exports, produced manually (see below)
expected/              # golden outputs, committed so CI can detect drift
run.yaml
```

## Why the STP exports are not automated

SwissTargetPrediction is a public web service. Scraping it, replaying hidden form fields or
rotating clients to dodge rate limits violates the spirit of the service and would make the
pipeline fragile. Instead:

1. submit the 8 compounds manually (one at a time) with `Homo sapiens` selected;
2. download the native CSV/Excel export for each job;
3. save it as `stp/<compound>.csv`, and record the retrieval date in the README table below.

The pipeline starts *after* the download. This is a deliberate boundary, documented in
`docs/review-gates.md` (gate G1) and `docs/limitations.md`.

## Retrieval log

| Compound | PubChem CID | Job / retrieval date | File |
|---|---|---|---|
| _(to be filled in week 2)_ | | | |

## Licensing

Compounds and CIDs are public. The cached STP exports are derived from a public service; the
repository ships them only as demo inputs with a retrieval date, and the README tells users how to
regenerate them. Disease genes come from CTD (cite CTD); STRING and GO results keep their
CC BY 4.0 attribution. See `docs/data-licenses.md`.
