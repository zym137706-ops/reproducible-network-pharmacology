# Data licenses

The repository **never redistributes restricted data**. Code is MIT; each data source keeps its
own terms. STP's 2026-10-23 confirmation covers the eight native XLSX tables only; it does not clear
CTD, PubChem, private logs or mixed-source derived outputs.

| Source | Used for | Redistribution in this repo | Notes |
|---|---|---|---|
| [HGNC](https://www.genenames.org/) | gene-symbol normalization | derived `hgnc_map.tsv` committed (CC0) | CC0; attribution recommended and recorded in `examples/demo/inputs/HGNC-SOURCE.md` |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | public compound identity/structures | case package/table only (not committed) | Reviewed 2026-10-27: NCBI places no restrictions on use/distribution of molecular data, but submitters may claim third-party rights and NCBI cannot provide unrestricted permission; no CC license asserted. Cite PubChem/record URLs and NCBI policy; data inclusion selected for the case package, release pending. See `docs/pubchem-structure-review-2026-10-27.md` |
| [GO](https://geneontology.org/) | enrichment gene sets | no bulk data; results derived | CC BY 4.0, attribution required |
| [Reactome](https://reactome.org/) | alternative gene sets (planned) | no bulk data | CC0 |
| [STRING](https://string-db.org/) | PPI input (planned) | no bulk network files | CC BY 4.0; record version (e.g. 12.0) |
| [CTD](https://ctdbase.org/) | disease gene sets (RA case) | **case package only, not committed** | CTD ticket **#8545** (2026-10-26) permits public non-profit research including GitHub for the requested 179-gene RA subset/derived outputs, with CTD citation and a data date-stamp; notify CTD of the public link. Commercial use is separate; do not relicense as MIT/CC0/CC BY. Query/rules: `examples/demo/inputs/CTD-QUERY.md`; permission: `docs/ctd-permission-2026-10-26.md` |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | literature evidence (planned) | no | NCBI terms of use |
| **GeneCards** | disease genes | **never** | commercial terms; do not redistribute |
| **OMIM** | disease genes | **never** | Johns Hopkins terms; do not redistribute |
| **KEGG** | pathway gene sets | **never** | proprietary; academic use via license; results are KEGG-derived |
| **DAVID** | legacy enrichment output | **never** | derived from KEGG/GO; do not publish the raw report |
| **SwissTargetPrediction** | target prediction demo | **case package only, not committed** | SwissDrugDesign reply 2026-10-23 confirms **CC BY 4.0** for the eight native XLSX tables; include attribution, cite website/prediction date/Daina & Zoete 2024, keep original tables unmodified. Derived analyses are allowed; mixed-source outputs need separate per-source review. Candidate: `CASE-PKG-2026-10-21` (outside Git). Manual submission only; no automated access. Record: `docs/stp-permission-2026-10-23.md` |
| [RCSB PDB](https://www.rcsb.org/) / [wwPDB](https://www.wwpdb.org/) | receptor structures and entry metadata (planned, v0.3; [ADR-0005](adr/0005-structure-acquisition-boundary.md)) | no bulk data; frozen files stay in git-ignored `data/local/structures/`; only small trimmed test fixtures with provenance may be committed | Terms checked 2026-11-07 ([wwPDB usage policies](https://www.wwpdb.org/about/usage-policies), [RCSB policies](https://www.rcsb.org/pages/policies), [RCSB usage policy](https://www.rcsb.org/pages/usage-policy)): data files of the PDB archive are available under CC0 1.0; data from the RCSB PDB programmatic APIs are available under the same license unless they originate from an integrated external resource, in which case that provider's licensing restrictions must be followed (the RCSB policies page states this exception, the shorter usage-policy page does not; the stricter statement is used); attributing the original structure authors is encouraged; no warranties. RCSB.org website text and images are not data used here and follow separate terms on those pages. Record the entry ID, retrieval time and hash for every structure used. |
| [UniProt](https://www.uniprot.org/) | target sequences, accession status and site annotations (planned, v0.3; [ADR-0005](adr/0005-structure-acquisition-boundary.md)) | no bulk data; frozen records stay in git-ignored `data/local/structures/`; only small trimmed test fixtures with provenance may be committed | Terms checked 2026-11-07 ([UniProt FTP `LICENSE`](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/LICENSE), last modified 2026-09-03): CC BY 4.0 applies to all copyrightable parts; copies may be redistributed freely without advance permission provided the UniProt copyright statement is reproduced with each copy. Attribution required; record the UniProt release (response header `x-uniprot-release`) with every record. |

## How licenses are enforced

- `data/SOURCES.yaml` records, per source: URL, license, release/version, SHA-256 and retrieval date.
- Restricted sources are obtained by a user-run download step; `.gitignore` excludes `data/local/`.
- `docs/review-gates.md` (G5) requires the disease-gene source and date to be recorded in the config.
- CI fails if a restricted file path appears in the repository (planned check).

If you believe a file violates a license, open an issue and it will be removed.
