# Public case: candidate data sources and license checklist

Status: **candidate sources only — no dataset has been downloaded or committed, and no scientific
result exists yet.** This page prepares the data/source/license work only. It does not turn
`examples/demo/` into a completed case, and it must not be cited as one.

For the acceptance conditions see [public-case-checklist.md](public-case-checklist.md).

## Candidate public sources

Verify the current terms at the exact release/retrieval date before committing anything. A public
URL is not by itself permission to redistribute.

| Layer | Candidate source | Access / identifiers | License / redistribution check | Status |
|---|---|---|---|---|
| Compound structures | PubChem | CID, canonical SMILES, `https://pubchem.ncbi.nlm.nih.gov/` | Check PubChem data terms for the release; do not redistribute vendor-only fields | candidate |
| Compound structures | ChEMBL | ChEMBL ID, canonical SMILES, release number | CC BY-SA 4.0 (attribution + share-alike obligations); record release | candidate |
| Compound names / natural products | NPASS / COCONUT | compound ID, source organism, SMILES | Check each database's academic-use terms; do not assume redistribution rights | candidate |
| Disease genes | Open Targets Platform | Ensembl gene IDs, disease ID, score, release | CC BY 4.0 typically; record release and attribution | candidate |
| Disease genes | CTD | exact MeSH `D001172` (Arthritis, Rheumatoid), no child expansion; direct marker/mechanism or therapeutic evidence | Research/education use; redistribution not confirmed; local extract only, query/rules in `examples/demo/inputs/CTD-QUERY.md` | **local prepared, not committed** |
| Disease genes (excluded) | GeneCards / OMIM | — | Repository policy excludes vendored GeneCards/OMIM content | excluded |
| Gene identifiers | HGNC | complete set, HGNC ID, symbol, alias, UniProt | CC0; attribution recommended; frozen derived table with source record | **frozen** |
| PPI (optional) | STRING | v12.0, confidence cutoff, `protein.links` | CC BY 4.0; record attribution | optional |
| Enrichment sets | GO | GO release, `org.Hs.eg.db` version | GO CC BY 4.0; record versions in the audited meta | candidate |
| Enrichment sets | Reactome | Reactome release, pathway IDs | Check Reactome terms for the release | candidate |
| Enrichment sets (excluded) | KEGG | — | KEGG is not redistributable in this repository; keep it user-provided | excluded |
| Target prediction | SwissTargetPrediction export | one export per compound, submission log, species | Produced manually by the researcher; no automatic submission; check site terms before committing exports | manual gate |

## Local data preparation (not committed)

The recorded eight PubChem CIDs can be fetched reproducibly into the ignored local data directory:

```bash
uv run python scripts/fetch_pubchem_structures.py --out data/local/case
```

This writes `data/local/case/pubchem_structures.tsv` plus raw per-CID responses and a metadata
file with the retrieval timestamp, field meanings and SHA-256. Current local retrieval:
`2026-10-20T12:40:37Z`, 8 rows, SHA-256
`c43811542fe1ef1856c8e9aefd2c1805e400d0c87d6093117565c04e9ebc6d02`. The current endpoint
returns `SMILES` (stereochemistry included where defined) and `ConnectivitySMILES` (connectivity
only), not the old `CanonicalSMILES`/`IsomericSMILES` names; the script validates both non-empty and
checks the returned CID. It is **not committed**: PubChem terms must be checked for the intended
redistribution use. STP submission still requires the researcher's manual exports and submission log.

## Evidence that must be recorded for every input

1. Landing-page URL and exact release/version.
2. Retrieval date (UTC) and query string/filters.
3. SHA-256 of the downloaded file and the row/column counts.
4. License shown at retrieval and the attribution text.
5. Whether the file is committed, or only a retrieval script + checksum is committed.
6. What the case does **not** verify (predictions ≠ experimental validation).

## Open decisions (researcher)

- Which disease and compound series may be public without disclosing an unpublished thesis direction.
- Whether SwissTargetPrediction exports can be redistributed, or only a submission log plus checksums.
- Whether the case uses only public compounds or a published compound list.
- Whether the target journal/advisor permits reuse of any wording from an unpublished report.

## Next step after core verification

Only after the R environment lock and the CLI tests are green: retrieve the chosen inputs, record the
table above with hashes, run `validate → ingest → intersect → network → enrich → report`, and write
the case README with source/license/retrieval evidence. Until then, no public-case claim is allowed.
