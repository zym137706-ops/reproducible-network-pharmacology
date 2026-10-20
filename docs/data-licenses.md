# Data licenses

The repository **never redistributes restricted data**. Code is MIT; each data source keeps its
own terms. When in doubt, check the upstream license before publishing derived tables.

| Source | Used for | Redistribution in this repo | Notes |
|---|---|---|---|
| [HGNC](https://www.genenames.org/) | gene-symbol normalization | version string only (no bulk data) | free to use with attribution; check current terms on genenames.org |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | public compound identity/structures | local fetched table only (not committed) | check PubChem terms before redistribution; the fetch script writes to `data/local/` |
| [GO](https://geneontology.org/) | enrichment gene sets | no bulk data; results derived | CC BY 4.0, attribution required |
| [Reactome](https://reactome.org/) | alternative gene sets (planned) | no bulk data | CC0 |
| [STRING](https://string-db.org/) | PPI input (planned) | no bulk network files | CC BY 4.0; record version (e.g. 12.0) |
| [CTD](https://ctdbase.org/) | disease gene sets (demo) | small demo list only | free for academic use with citation; check terms for redistribution |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | literature evidence (planned) | no | NCBI terms of use |
| **GeneCards** | disease genes | **never** | commercial terms; do not redistribute |
| **OMIM** | disease genes | **never** | Johns Hopkins terms; do not redistribute |
| **KEGG** | pathway gene sets | **never** | proprietary; academic use via license; results are KEGG-derived |
| **DAVID** | legacy enrichment output | **never** | derived from KEGG/GO; do not publish the raw report |
| **SwissTargetPrediction** | target prediction demo | cached demo exports with retrieval date | public academic service; do not automate submissions |

## How licenses are enforced

- `data/SOURCES.yaml` records, per source: URL, license, release/version, SHA-256 and retrieval date.
- Restricted sources are obtained by a user-run download step; `.gitignore` excludes `data/local/`.
- `docs/review-gates.md` (G5) requires the disease-gene source and date to be recorded in the config.
- CI fails if a restricted file path appears in the repository (planned check).

If you believe a file violates a license, open an issue and it will be removed.
