# Data licenses

The repository **never redistributes restricted data**. Code is MIT; each data source keeps its
own terms. STP's 2026-10-23 confirmation covers the eight native XLSX tables only; it does not clear
CTD, PubChem, private logs or mixed-source derived outputs.

| Source | Used for | Redistribution in this repo | Notes |
|---|---|---|---|
| [HGNC](https://www.genenames.org/) | gene-symbol normalization | derived `hgnc_map.tsv` committed (CC0) | CC0; attribution recommended and recorded in `examples/demo/inputs/HGNC-SOURCE.md` |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | public compound identity/structures | local candidate/table only (not committed) | Reviewed 2026-10-27: NCBI places no restrictions on use/distribution of molecular data, but submitters may claim third-party rights and NCBI cannot provide unrestricted permission; no CC license asserted. Cite PubChem/record URLs and NCBI policy; publication decision pending. See `docs/pubchem-structure-review-2026-10-27.md` |
| [GO](https://geneontology.org/) | enrichment gene sets | no bulk data; results derived | CC BY 4.0, attribution required |
| [Reactome](https://reactome.org/) | alternative gene sets (planned) | no bulk data | CC0 |
| [STRING](https://string-db.org/) | PPI input (planned) | no bulk network files | CC BY 4.0; record version (e.g. 12.0) |
| [CTD](https://ctdbase.org/) | disease gene sets (RA case) | **local candidate only, not committed** | CTD ticket **#8545** (2026-10-26) permits public non-profit research including GitHub for the requested 179-gene RA subset/derived outputs, with CTD citation and a data date-stamp; notify CTD of the public link. Commercial use is separate; do not relicense as MIT/CC0/CC BY. Query/rules: `examples/demo/inputs/CTD-QUERY.md`; permission: `docs/ctd-permission-2026-10-26.md` |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | literature evidence (planned) | no | NCBI terms of use |
| **GeneCards** | disease genes | **never** | commercial terms; do not redistribute |
| **OMIM** | disease genes | **never** | Johns Hopkins terms; do not redistribute |
| **KEGG** | pathway gene sets | **never** | proprietary; academic use via license; results are KEGG-derived |
| **DAVID** | legacy enrichment output | **never** | derived from KEGG/GO; do not publish the raw report |
| **SwissTargetPrediction** | target prediction demo | **local candidate only, not committed** | SwissDrugDesign reply 2026-10-23 confirms **CC BY 4.0** for the eight native XLSX tables; include attribution, cite website/prediction date/Daina & Zoete 2024, keep original tables unmodified. Derived analyses are allowed; mixed-source outputs need separate per-source review. Candidate: `C:/DSH/rnp-stp-release-candidate-2026-10-21/` (outside Git). Manual submission only; no automated access. Record: `docs/stp-permission-2026-10-23.md` |

## How licenses are enforced

- `data/SOURCES.yaml` records, per source: URL, license, release/version, SHA-256 and retrieval date.
- Restricted sources are obtained by a user-run download step; `.gitignore` excludes `data/local/`.
- `docs/review-gates.md` (G5) requires the disease-gene source and date to be recorded in the config.
- CI fails if a restricted file path appears in the repository (planned check).

If you believe a file violates a license, open an issue and it will be removed.
