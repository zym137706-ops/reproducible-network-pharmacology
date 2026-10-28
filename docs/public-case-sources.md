# Public case: candidate data sources and license checklist

Status: **STP tables CC BY 4.0-confirmed; CTD public non-profit research permission confirmed
(ticket #8545); complete candidate prepared; publication decision/candidate review pending.**
The disease extract, eight STP XLSX exports, submission log and detailed results are local-only and
were used for the completed local calculation. HGNC is frozen/committed (CC0). PubChem structure
terms remain separately pending. No restricted dataset is committed; the candidate is not published.
This page records the source/license checks. For acceptance conditions see
[public-case-checklist.md](public-case-checklist.md).

## Candidate public sources

Verify the current terms at the exact release/retrieval date before committing anything. A public
URL is not by itself permission to redistribute.

| Layer | Candidate source | Access / identifiers | License / redistribution check | Status |
|---|---|---|---|---|
| Compound structures | PubChem | CID, SMILES/ConnectivitySMILES | Source/terms review completed 2026-10-27: computed descriptors from PUG REST; NCBI no-restriction statement + submitter-rights caveat; no CC license. Case package; publication decision pending | **reviewed; case package** |
| Compound structures | ChEMBL | ChEMBL ID, canonical SMILES, release number | CC BY-SA 4.0 (attribution + share-alike obligations); record release | candidate |
| Compound names / natural products | NPASS / COCONUT | compound ID, source organism, SMILES | Check each database's academic-use terms; do not assume redistribution rights | candidate |
| Disease genes | Open Targets Platform | Ensembl gene IDs, disease ID, score, release | CC BY 4.0 typically; record release and attribution | candidate |
| Disease genes | CTD | exact MeSH `D001172` (Arthritis, Rheumatoid), no child expansion; direct marker/mechanism or therapeutic evidence | **CTD ticket #8545 (2026-10-26): public non-profit research incl. GitHub; cite CTD and date-stamp; commercial separate**; query/rules in `examples/demo/inputs/CTD-QUERY.md` | **permission confirmed; case package; not published** |
| Disease genes (excluded) | GeneCards / OMIM | — | Repository policy excludes vendored GeneCards/OMIM content | excluded |
| Gene identifiers | HGNC | complete set, HGNC ID, symbol, alias, UniProt | CC0; attribution recommended; frozen derived table with source record | **frozen** |
| PPI (optional) | STRING | v12.0, confidence cutoff, `protein.links` | CC BY 4.0; record attribution | optional |
| Enrichment sets | GO | GO release, `org.Hs.eg.db` version | GO CC BY 4.0; local GO.db 3.22.0 used through the locked R library | **local used** |
| Enrichment sets | Reactome | Reactome release, pathway IDs | Check Reactome terms for the release | candidate |
| Enrichment sets (excluded) | KEGG | — | KEGG is not redistributable in this repository; keep it user-provided | excluded |
| Target prediction | SwissTargetPrediction export | 8 XLSX, 800 rows, submission log, Homo sapiens | SwissDrugDesign reply 2026-10-23 confirms **CC BY 4.0** for the eight native tables; cite website/prediction date/Daina & Zoete 2024; originals unmodified. Derived analyses allowed; mixed-source outputs need per-source review. Local candidate: `CASE-PKG-2026-10-21` | **confirmed; case package; not published** |

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

- Review the complete candidate package and decide data inclusion, repository visibility and
  versioned release.
- Separately review PubChem structure/source terms before publishing the compound structure table;
  STP/CTD replies do not clear PubChem.
- Notify CTD of the public project link when publication occurs (recommended by CTD).

## Next step after local verification

The R lock is restored, the local dual-threshold chain plus independent checks are complete, and the
complete candidate has been reproduced from a clean clone. STP and CTD permissions cover the requested
public non-profit scope; PubChem source/terms review is complete with a residual third-party caveat.
The remaining decisions are candidate review, data inclusion, structure publication and final release.
Until the researcher approves publication, no public-case claim is allowed.
