# Public case: data and license checklist

Status: **not started / not a completed case.** The synthetic demo
(`scripts/synthetic_demo.py`) is an engineering test, not a public scientific case.
Do not describe a placeholder dataset as a public case.

## What the case must contain

| Item | Required detail | License / provenance check | Status |
|---|---|---|---|
| Compound list | stable `compound_id`, name, SMILES or a documented structure source; explicit `stp_file` binding; group if multiple products | compounds must be public; record source (PubChem CID, vendor, paper) and retrieval date | TODO |
| SwissTargetPrediction exports | one export per compound, species recorded, retrieval date, submission log (query structure) | produced manually by the researcher; no automatic submission; no bulk redistribution without terms check | TODO |
| Disease gene list | gene symbols + source (CTD / Open Targets / other), query string, retrieval date, inclusion criteria | confirm redistribution terms for the release used; restricted sources (GeneCards/OMIM) stay out of git | TODO |
| HGNC snapshot | complete-set TSV version/date; which release | acceptable to use locally; check attribution terms before committing even a subset | TODO |
| STRING/PPI (optional) | version (e.g. 12.0), confidence cutoff, retrieval date | CC BY 4.0; record attribution | TODO |
| Enrichment gene sets | GO/Reactome/KEGG release; background definition | GO CC BY 4.0; KEGG is not redistributable — user-provided | TODO |
| Demo commands + expected tables | exact command log, committed expected outputs derived independently | synthetic or public only | TODO |

## Acceptance for calling it a "public case"

1. Every input above is public, or a documented local derivative whose redistribution terms were
   checked for that specific release.
2. `rnp validate → ingest → intersect → network → manifest --check-inputs` runs from a clean clone.
3. Expected tables are reproducible from the committed inputs; numeric tolerances are declared.
4. The case README states source, retrieval date, license, and what was **not** verified.
5. No unpublished compound identity, disease hypothesis or report text is included.

## Open decisions for the researcher

- Which product and disease the case uses (must not disclose an unpublished thesis direction).
- Whether STP exports may be committed, or only a retrieval log plus checksums.
- Whether a public dataset (e.g. a published formula/compound list) is acceptable as the subject.
- Journal/advisor permission before any case-study text is reused from an unpublished report.

## Explicit non-goals

- No automatic STP submission.
- No bulk migration of historical docking tasks.
- No claim that a public case exists before the checklist is complete.
