# CTD disease query and inclusion rule

The complete request outputs are **prepared in the candidate case package**
`CASE-PKG-2026-10-21/inputs/` (not yet publicly released); the `data/local/` paths below are for
rebuilding only and are not part of the public repository.

Recorded decision: **Arthritis, Rheumatoid**, exact MeSH ID **D001172**; no child disease expansion.

## Query

Reproduce the exact request (requires network; keep the output under `data/local/`):

```bash
curl -sS -X POST "https://ctdbase.org/tools/batchQuery.go?q" \
  -F inputType=disease \
  -F 'inputTerms=MeSH:D001172' \
  -F report=genes_curated \
  -F format=tsv \
  -o data/local/case/ctd_ra_genes.tsv
```

- Endpoint: `https://ctdbase.org/tools/batchQuery.go?q` (POST multipart/form-data)
- Fields: `inputType=disease`, `inputTerms=MeSH:D001172`, `report=genes_curated`, `format=tsv`
- Retrieved: `2026-10-21T05:03:53Z`
- CTD data status: **September 2026** (CTD Data Status page says the latest monthly release)
- Returned rows: 179; disease IDs all exactly `MESH:D001172`
- Evidence types: `marker/mechanism` 175; `marker/mechanism|therapeutic` 3; `therapeutic` 1

## Inclusion / exclusion

- Include rows whose CTD `DirectEvidence` contains `marker/mechanism` or `therapeutic`.
- Exclude inferred-only associations.
- No child disease terms or automatic expansion.
- Gene identifier namespace: HGNC symbol, as returned by CTD.

## Evidence retained (candidate package; not Git)

- Raw query TSV: `CASE-PKG-2026-10-21/inputs/ctd_ra_genes.tsv`
- Filtered evidence table: `CASE-PKG-2026-10-21/inputs/ctd_ra_evidence.tsv` (gene, Entrez ID,
  evidence type, disease ID/name, PubMed IDs, source)
- Gene list: `CASE-PKG-2026-10-21/inputs/disease_genes.txt` (179 unique symbols, SHA-256
  `321e5441560904bc7d926be3c8955420654dae22166526f65db69becbb29064a`)
- Metadata: `CASE-PKG-2026-10-21/inputs/ctd_metadata.json` (query/hashes/evidence counts)

The repository keeps only this query/rule/provenance description; the actual extract is in the
versioned case package, not in Git.

## Licence status

CTD ticket **#8545** (2026-10-26) confirms the requested **public non-profit research** use,
including GitHub, for the 179-gene RA subset and derived outputs. Conditions: cite CTD and include the
data date-stamp; commercial use is separate; do not relicense CTD data as MIT/CC0/CC BY. The data
version used here is **September 2026**, retrieved **2026-10-21**. The case package is prepared but not
yet publicly uploaded; no redistribution beyond this confirmed scope is claimed. Citation and
permission details: [`docs/ctd-permission-2026-10-26.md`](../../../docs/ctd-permission-2026-10-26.md).

Raw query SHA-256: `3742a52f6ed0662098b240beac3a3cf28159a46d73e3642b4fa35ff8878d0fac`.
