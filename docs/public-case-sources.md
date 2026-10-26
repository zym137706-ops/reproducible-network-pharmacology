# Public case: candidate data sources and license checklist

Status: **STP tables CC BY 4.0-confirmed; overall public release still pending CTD.** The disease
extract, eight STP XLSX exports, submission log and detailed results are local-only and were used for
the completed local calculation. HGNC is frozen/committed (CC0). STP's 2026-10-23 reply covers the
eight native tables only; a review-only candidate is local and not committed. No restricted dataset
is committed and the local result is not a public case. This page records the source/license checks.
For acceptance conditions see [public-case-checklist.md](public-case-checklist.md).

## Candidate public sources

Verify the current terms at the exact release/retrieval date before committing anything. A public
URL is not by itself permission to redistribute.

| Layer | Candidate source | Access / identifiers | License / redistribution check | Status |
|---|---|---|---|---|
| Compound structures | PubChem | CID, SMILES/ConnectivitySMILES | Terms for redistribution not confirmed; 8 rows fetched locally, not committed | **local fetched, not committed** |
| Compound structures | ChEMBL | ChEMBL ID, canonical SMILES, release number | CC BY-SA 4.0 (attribution + share-alike obligations); record release | candidate |
| Compound names / natural products | NPASS / COCONUT | compound ID, source organism, SMILES | Check each database's academic-use terms; do not assume redistribution rights | candidate |
| Disease genes | Open Targets Platform | Ensembl gene IDs, disease ID, score, release | CC BY 4.0 typically; record release and attribution | candidate |
| Disease genes | CTD | exact MeSH `D001172` (Arthritis, Rheumatoid), no child expansion; direct marker/mechanism or therapeutic evidence | Research/education use; redistribution not confirmed; local extract only, query/rules in `examples/demo/inputs/CTD-QUERY.md` | **local prepared, not committed** |
| Disease genes (excluded) | GeneCards / OMIM | — | Repository policy excludes vendored GeneCards/OMIM content | excluded |
| Gene identifiers | HGNC | complete set, HGNC ID, symbol, alias, UniProt | CC0; attribution recommended; frozen derived table with source record | **frozen** |
| PPI (optional) | STRING | v12.0, confidence cutoff, `protein.links` | CC BY 4.0; record attribution | optional |
| Enrichment sets | GO | GO release, `org.Hs.eg.db` version | GO CC BY 4.0; local GO.db 3.22.0 used through the locked R library | **local used** |
| Enrichment sets | Reactome | Reactome release, pathway IDs | Check Reactome terms for the release | candidate |
| Enrichment sets (excluded) | KEGG | — | KEGG is not redistributable in this repository; keep it user-provided | excluded |
| Target prediction | SwissTargetPrediction export | 8 XLSX, 800 rows, submission log, Homo sapiens | SwissDrugDesign reply 2026-10-23 confirms **CC BY 4.0** for the eight native tables; cite website/prediction date/Daina & Zoete 2024; originals unmodified. Derived analyses allowed; mixed-source outputs need per-source review. Local candidate: `C:/DSH/rnp-stp-release-candidate-2026-10-21/` | **confirmed; candidate local; not published** |

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

## Open decisions (researcher / upstream)

- Whether CTD permits public redistribution of the 179-gene subset and derived outputs.
- Review the local STP candidate package and decide whether to publish the cleared native tables
  and/or selected STP-only derived outputs.
- If CTD permission is not granted, whether to publish only the query/filter recipe and checksums, or
  choose a case with clear redistribution terms.

## Next step after local verification

The R lock is restored and the local dual-threshold chain plus independent checks are complete. STP's
table scope is confirmed; the remaining public gate is CTD permission in
`examples/demo/CASE-FREEZE.yaml`. Record the official CTD reply, then either publish the covered
subset/results with attribution or keep them local and publish only the reproducible
recipe/checksums. Until then, no public-case claim is allowed.
