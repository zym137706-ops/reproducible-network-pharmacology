# Citations and data attribution

Status: v0.1.0, **published 2026-11-02**. Software and upstream data have separate
licenses; cite both the software and the sources actually used.

## Software

Zhu Y. *reproducible-network-pharmacology* v0.1.0 (published 2026-11-02). MIT-licensed code.
Release: https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/tag/v0.1.0
No DOI is assigned.

Optional software (extra `chem`, used by the structure library `rnp.structures`; v0.2.0):

- RDKit: open-source cheminformatics, <https://www.rdkit.org/>; source <https://github.com/rdkit/rdkit>.
  License BSD-3-Clause (PyPI metadata of rdkit 2026.9.1, read 2026-11-10). The installed version is
  recorded in every structure-registry row (`toolkit_version`).
- InChI and InChIKey come from the InChI support of RDKit. Heller SR, McNaught A, Pletnev I, Stein S,
  Tchekhovskoi D. InChI, the IUPAC International Chemical Identifier. *Journal of Cheminformatics* **7**, 23
  (2015). <https://doi.org/10.1186/s13321-015-0068-4>

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

### RCSB Protein Data Bank (RCSB PDB / wwPDB)

- Website: <https://www.rcsb.org/>; worldwide PDB: <https://www.wwpdb.org/>
- Used only by `rnp acquire` (v0.2.0), not by the published v0.1.0 case. Each retrieval
  records the entry ID, retrieval time and SHA-256; the frozen files stay in the git-ignored `data/local/`
  and are not redistributed here.
- Berman HM, Westbrook J, Feng Z, Gilliland G, Bhat TN, Weissig H, Shindyalov IN, Bourne PE. The Protein
  Data Bank. *Nucleic Acids Research* **28**(1), 235–242 (2000). <https://doi.org/10.1093/nar/28.1.235>
- Burley SK, Bhatt R, Bhikadiya C, et al. Updated resources for exploring experimentally-determined PDB
  structures and Computed Structure Models at the RCSB Protein Data Bank. *Nucleic Acids Research*
  **53**(D1), D564–D574 (2025). <https://doi.org/10.1093/nar/gkae1091>
- wwPDB: Berman H, Henrick K, Nakamura H. Announcing the worldwide Protein Data Bank. *Nature Structural
  Biology* **10**(12), 980 (2003). <https://doi.org/10.1038/nsb1203-980>; wwPDB consortium. Protein Data
  Bank: the single global archive for 3D macromolecular structure data. *Nucleic Acids Research*
  **47**(D1), D520–D528 (2019). <https://doi.org/10.1093/nar/gky949>
- Terms checked 2026-11-07 and re-read on 2026-11-08 (<https://www.rcsb.org/pages/policies>): the data of
  the PDB archive are CC0 1.0; data from the RCSB programmatic APIs have the same license unless they
  originate from an integrated external resource, whose restrictions then apply. RCSB asks that RCSB PDB
  be cited as above and that every PDB entry used be cited by its PDB ID together with the publication of
  its structure authors (an entry without a publication: PDB ID, deposition year, authors, title and
  entry DOI). See `docs/data-licenses.md`.

### UniProt

- Website: <https://www.uniprot.org/>
- Used only by `rnp acquire` (v0.2.0), not by the published v0.1.0 case. The UniProt
  release is recorded with each retrieval when the response carries `x-uniprot-release`; the frozen
  records stay in the git-ignored `data/local/` and are not redistributed here.
- The UniProt Consortium. UniProt: the Universal Protein Knowledgebase in 2025. *Nucleic Acids Research*
  **53**(D1), D609–D617 (2025). <https://doi.org/10.1093/nar/gkae1010>
- Ahmad S, et al.; UniProt Consortium. The UniProt website API: facilitating programmatic access to
  protein knowledge. *Nucleic Acids Research* **53**(W1), W547–W553 (2025).
  <https://doi.org/10.1093/nar/gkaf394> (covers the REST API that `rnp acquire` uses).
- License: CC BY 4.0 (terms checked 2026-11-07, see `docs/data-licenses.md`): attribution is required and
  the UniProt copyright statement must be reproduced with any redistributed copy. UniProt's citation page
  (<https://www.uniprot.org/help/publications>, read 2026-11-08) asks users to cite the publication that
  best covers the components they used.
