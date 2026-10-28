# Public case: data and license checklist

Status: **local calculation complete; STP tables CC BY 4.0-confirmed; CTD public non-profit research
permission confirmed (ticket #8545); publication decision/candidate review pending.** The recorded
decisions and evidence are in [`examples/demo/CASE-FREEZE.yaml`](../examples/demo/CASE-FREEZE.yaml).
The synthetic demo (`scripts/synthetic_demo.py`) is an engineering test, not a public scientific case.
Do not describe the candidate as a published public case until the researcher approves publication.

STP confirmed on 2026-10-23 that the eight native XLSX tables are CC BY 4.0, with attribution and no
modification. CTD confirmed on 2026-10-26 (ticket #8545) that the requested 179-gene RA subset and
derived outputs may be used for public non-profit research including GitHub, with CTD citation and a
data date-stamp; commercial use is separate. Disease/STP/backgrounds and detailed results exist
locally and were used for the completed calculation; they are **not missing local inputs**. HGNC is
frozen and committed (CC0). PubChem structure source/terms/citation review is complete with a
residual third-party caveat; publication remains a separate researcher decision.

## What the case must contain

| Item | Required detail | License / provenance check | Status |
|---|---|---|---|
| Compound list | stable `compound_id`, name, SMILES or documented structure source; explicit `stp_file` binding | public compounds; PubChem CID and retrieval date recorded; source/terms review complete with residual caveat | local verified: 8 CIDs; actual `.xlsx` bindings; publication decision pending |
| SwissTargetPrediction exports | one export per compound, species recorded, retrieval date, submission log | **CC BY 4.0 confirmed 2026-10-23 for eight native tables**; cite website/date/Daina & Zoete 2024; originals unmodified | **confirmed; candidate prepared; not published** |
| Disease gene list | exact MeSH D001172 (Arthritis, Rheumatoid); CTD query and direct evidence rule | **CTD ticket #8545: public non-profit research incl. GitHub; cite CTD/date-stamp; commercial separate** | **permission confirmed; case package; not published** |
| HGNC snapshot | complete-set TSV version/date; which release | CC0; attribution recorded | FROZEN: 2026-10-16, 45,277 Approved |
| STRING/PPI (optional) | version, confidence cutoff, retrieval date | CC BY 4.0; attribution | not used |
| Enrichment gene sets | GO BP release; explicit conditional background | GO CC BY 4.0; background rule documented | local GO.db 3.22.0; T_r=239/267; effective 234/262 |
| Demo commands + expected tables | exact command log, independently checked expected counts | candidate expected counts documented | local commands/check passed; candidate review pending |

## Acceptance for calling it a "public case"

1. Every input above is public, or a documented derivative whose redistribution terms were checked
   for that specific release.
2. The full chain runs from a clean clone with the documented local input parameters.
3. Expected tables are reproducible from the committed inputs; numeric tolerances are declared.
4. The case README states source, retrieval date, license, and what was **not** verified.
5. No unpublished compound identity, disease hypothesis or report text is included.

## Open decisions for the researcher

- Review the complete candidate package (inputs/expected/attribution/hashes) and decide data
  inclusion, repository visibility and versioned release.
- Separate review of PubChem structure/source terms before publishing compounds/structure tables;
  STP/CTD replies do not clear PubChem.
- Whether to notify CTD of the public project link when publication occurs (recommended by CTD).
- Do not relabel CTD data as MIT/CC0/CC BY or claim commercial rights.

## Explicit non-goals

- No automatic STP submission.
- No bulk migration of historical docking tasks.
- No claim that the candidate is a published public case before the researcher's publication decision.
- No inference that public accessibility or a permission reply grants commercial/unrestricted rights.
