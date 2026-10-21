# CTD disease query and inclusion rule

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

## Evidence retained (local only)

- Raw query TSV: `data/local/case/ctd_ra_genes.tsv`
- Filtered evidence table: `data/local/case/ctd_ra_evidence.tsv` (gene, Entrez ID, evidence type,
  disease ID/name, PubMed IDs, source)
- Gene list: `data/local/case/disease_genes.txt` (179 unique symbols, SHA-256
  `321e5441560904bc7d926be3c8955420654dae22166526f65db69becbb29064a`)
- Metadata: `data/local/case/ctd_metadata.json` (query/hashes/evidence counts)

## Licence status

CTD's legal page states research/educational use; reproduction or commercial use requires prior
permission, and publications must cite/notify CTD. **Redistribution is not confirmed**, so the
disease genes/evidence are **not committed**. The repository records only this query/rule/provenance;
the actual extract must be supplied with permission or kept local for analysis.

Raw query SHA-256: `3742a52f6ed0662098b240beac3a3cf28159a46d73e3642b4fa35ff8878d0fac`.
