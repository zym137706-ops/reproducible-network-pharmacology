# HGNC snapshot source

The case uses the HGNC complete set as a gene-symbol/alias/UniProt normalisation reference.

- Source: HGNC complete set, `https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt`
- License: **CC0** (HGNC recommends attribution); see <https://www.genenames.org/about/license/>.
  Recommended citation: Genenames.org: the HGNC resources in 2023, *Nucleic Acids Research*.
- Retrieved: `2026-10-21T04:28:03Z`
- HTTP `Last-Modified`: `Fri, 16 Oct 2026 13:36:15 GMT` (used as the snapshot date; no release date was guessed)
- Raw file SHA-256: `12363916be36f8f6f91879b0faade4eeaac973722de7136ec61329b77f2c2f91`
  (17 MB raw; not committed)
- Derived `hgnc_map.tsv` SHA-256: `af156dd54890b96eb8dc7e989d6a880669553ade7bcfea5d1cc4cd6cb494d4a3`
- Derived rows: 45,277 `Approved` records
- Columns: `hgnc_id`, `symbol`, `status`, `prev_symbol`, `alias_symbol`, `uniprot_ids`,
  `entrez_id`, `locus_group`
- Reproduce: `uv run python scripts/fetch_hgnc_snapshot.py --out examples/demo/inputs/hgnc_map.tsv`
  (the raw 17 MB file stays under `data/local/reference/`; the script records raw/derived hashes and
  HTTP metadata).

The full raw file is kept in `data/local/` (ignored). The derived table is committed because CC0
permits redistribution; attribution is retained here.
