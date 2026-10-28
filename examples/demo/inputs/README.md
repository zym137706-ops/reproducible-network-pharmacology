# Public demo inputs: repository templates and case package

This repository publishes **code, templates and public reference tables**, not the real RA case data.
The complete case inputs and expected outputs are distributed as the versioned release asset
[`rnp-case-v0.1.0-2026-10-21.zip`](../DATA-ACCESS.md); they are not committed here.

| Input | In this repository | Complete case package |
|---|---|---|
| `compounds.tsv` | template: 8 PubChem CIDs, no structures | exact submitted SMILES/structures + same CID bindings |
| `STP-SUBMISSION-LOG.tsv` | blank template with the 8 bindings | de-identified completed 2026-10-21 log with hashes/times/proxy notes |
| `STP-PENDING-SUBMISSIONS.tsv` | removed (superseded) | not needed; the completed log is authoritative |
| `disease_genes.txt` | synthetic test fixture only | 179 CTD genes, exact query/release/retrieval metadata |
| `stp/` exports | empty by design | eight byte-identical native XLSX tables |
| `hgnc_map.tsv` | frozen public CC0 table | same public snapshot |
| expected counts | not stored here | `expected/EXPECTED.json` and `VERIFICATION.md` |

Use [`../DATA-ACCESS.md`](../DATA-ACCESS.md) for download, checksum and reproduction steps. Private
EMLs, screenshots, full headers, school/personal email and IP/session data are never included.
