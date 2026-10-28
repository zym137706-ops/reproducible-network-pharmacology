# Citations and data attribution

Status: v0.1.0 release candidate, **not published**. Software and upstream data have separate
licenses; cite both the software and the sources actually used.

## Software

Zhu Y. *reproducible-network-pharmacology* v0.1.0 (release candidate). MIT-licensed code.
No DOI is assigned; a DOI/release date must not be invented before an actual release.

## Upstream data citations

### SwissTargetPrediction (STP)

- Website: <https://www.swisstargetprediction.ch/>
- Prediction generation date used here: **2026-10-21**; manual submission, *Homo sapiens*.
- Daina A, Zoete V. Testing the predictive power of reverse screening to infer drug targets, with the
  help of machine learning. *Communications Chemistry* **7**, 105 (2024).
  <https://doi.org/10.1038/s42004-024-01179-2>
- The eight native XLSX tables are used under **CC BY 4.0** (confirmation 2026-10-23); keep the
  original tables unmodified and include the website/prediction date/paper citation.
  See `docs/stp-permission-2026-10-23.md`.

### Comparative Toxicogenomics Database (CTD)

- Website: <https://ctdbase.org/>
- Data status used here: **September 2026**; retrieved **2026-10-21**; exact MeSH **D001172**,
  no child expansion; 179 direct-evidence genes.
- Davis AP, Wiegers TC, Sciaky D, Barkalow F, Strong M, Wyatt B, Wiegers J, McMorran R, Abrar S,
  Mattingly CJ. Comparative Toxicogenomics Database's 20th anniversary: update 2025.
  *Nucleic Acids Research* **53**(D1), D1328–D1334 (2025).
  <https://doi.org/10.1093/nar/gkae883>
- Permission: CTD ticket **#8545** (2026-10-26) permits public non-profit research including GitHub
  for this requested subset/derived outputs, with CTD citation and a data date-stamp; commercial use
  is separate. Do not relicense CTD data as MIT/CC0/CC BY. See `docs/ctd-permission-2026-10-26.md`.

### HGNC

- Website: <https://www.genenames.org/>
- Snapshot: **2026-10-16**, 45,277 Approved symbols; CC0.
- Seal RL, Braschi B, Gray K, McClay J, Tweedie S, Bruford EA. Genenames.org: the HGNC and PGNC
  resources in 2026. *Nucleic Acids Research* (2025), gkaf1229.
  <https://doi.org/10.1093/nar/gkaf1229>

### PubChem

- Website/records: <https://pubchem.ncbi.nlm.nih.gov/>; searched/retrieved **2026-10-20**.
- Kim S, Chen J, Cheng T, Gindulyte A, He J, He S, Li Q, Shoemaker BA, Thiessen PA, Yu B, Zaslavsky L,
  Zhang J, Bolton EE. PubChem 2025 update. *Nucleic Acids Research* **53**(D1), D1516–D1525 (2025).
  <https://doi.org/10.1093/nar/gkae1059>
- Fields used: `SMILES` and `ConnectivitySMILES` from the PUG REST property endpoint; these are
  PubChem-computed descriptors, with per-record OEChem/PubChem release references in
  `docs/pubchem-structure-review-2026-10-27.md`.
- NCBI policy: <https://www.ncbi.nlm.nih.gov/home/about/policies/>. NCBI places no restrictions on
  use/distribution of molecular data, but third-party submitters may retain rights and NCBI cannot
  grant unrestricted permission. This is not asserted as MIT/CC0/CC BY.
