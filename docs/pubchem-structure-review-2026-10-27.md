# PubChem structure source and terms review — 2026-10-27

Scope: the eight PubChem CIDs used in the RA candidate. This is a source/terms review, not a claim of
a separate permissive data license.

## Actual fields and provenance

- Retrieval: **2026-10-20T12:40:37Z** via PubChem PUG REST property endpoint:
  `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/SMILES,ConnectivitySMILES/JSON`.
- Requested fields: **`SMILES`** (stereochemistry included where the record defines it) and
  **`ConnectivitySMILES`** (connectivity only; no stereochemistry). No local RDKit normalization,
  salt stripping or structure rewriting was applied.
- The eight CID records are listed in `CASE-PKG-2026-10-21/inputs/pubchem_record_provenance.tsv` with:
  CID, record title, record URL, PUG View URL, PUG REST URL, the exact returned SMILES fields,
  retrieval time and raw-response SHA-256.
- PUG View `Computed Descriptors` identifies these SMILES as **computed** descriptors, not
  user-submitted structures. The per-record references observed are:
  - `Computed by OEChem 2.3.0 (PubChem release 2025.04.14)` for Quercetin, Luteolin and Catechin;
  - `Computed by OEChem 4.2.0 (PubChem release 2025.09.15)` for Kaempferol, Apigenin, Naringenin,
    Gallic acid and Chlorogenic acid.
- PubChem records can change over time; the candidate preserves the exact returned fields and
  retrieval hash.

## Terms and citation

Official policy reviewed: NCBI, *Website and Data Usage Policies and Disclaimers*,
<https://www.ncbi.nlm.nih.gov/home/about/policies/>.

Relevant statements:

- NCBI itself places **no restrictions on the use or distribution** of molecular data in its
  databases.
- However, some submitters may claim patent/copyright/other rights in submitted data; NCBI has no
  rights to transfer and **cannot provide unrestricted permission** for use, copying or distribution.
- NLM-created public-domain content may be freely distributed/copied with appropriate acknowledgment;
  the policy also notes that PubChem incorporates contributed/licensed material.
- NCBI advises acknowledgment and citation; no CC license is asserted for PubChem data.

Citation/reference practice for this case:

- Cite **PubChem** and the record URLs, e.g.
  <https://pubchem.ncbi.nlm.nih.gov/compound/5280343>, with the retrieval date 2026-10-20.
- Cite NCBI's policies page above when reproducing the data/description.
- Do not label the structures as MIT/CC0/CC BY. This review is not a replacement for separate legal
  advice or for STP/CTD terms.

## Status

PubChem structure source/field/terms/citation review is **complete**, with the residual caveat that
third-party rights in contributed records cannot be excluded by NCBI. The eight structures are
included in the case package by the selected data-inclusion decision; actual publication is still pending. This review
does not authorize commercial use and does not relicense PubChem data.
