# Public case: data and license checklist

Status: **local calculation complete; public release BLOCKED pending official permission.** The
recorded decisions and evidence are in [`examples/demo/CASE-FREEZE.yaml`](../examples/demo/CASE-FREEZE.yaml).
The synthetic demo (`scripts/synthetic_demo.py`) is an engineering test, not a public scientific case.
Do not describe the local case as a public case until the permission gate is cleared.

Current public-release blockers: CTD redistribution permission for the 179-gene subset/derived
outputs, and confirmation whether the eight STP exports/derived tables are Licensed Materials under
CC BY 4.0. Disease/STP/backgrounds and detailed results exist locally and were used for the completed
calculation; they are **not missing local inputs**. HGNC is frozen and committed (CC0).

## What the case must contain

| Item | Required detail | License / provenance check | Status |
|---|---|---|---|
| Compound list | stable `compound_id`, name, SMILES or documented structure source; explicit `stp_file` binding | public compounds; PubChem CID and retrieval date recorded | local verified: 8 CIDs; actual `.xlsx` bindings; structures local-only |
| SwissTargetPrediction exports | one export per compound, species recorded, retrieval date, submission log | produced manually; no automatic submission; redistribution scope pending | local verified: 8 XLSX, 800 rows, 676/740 after thresholds |
| Disease gene list | exact MeSH D001172 (Arthritis, Rheumatoid); CTD query and direct evidence rule | CTD redistribution not confirmed; extract local-only; query/rules in `inputs/CTD-QUERY.md` | local prepared + used; public commit pending |
| HGNC snapshot | complete-set TSV version/date; which release | CC0; attribution recorded | FROZEN: 2026-10-16, 45,277 Approved |
| STRING/PPI (optional) | version, confidence cutoff, retrieval date | CC BY 4.0; attribution | not used |
| Enrichment gene sets | GO BP release; explicit conditional background | GO CC BY 4.0; background rule documented | local GO.db 3.22.0; T_r=239/267; effective 234/262 |
| Demo commands + expected tables | exact command log, independently checked expected counts | public/synthetic only for committed artifacts | local commands/check passed; no public expected tables yet |

## Acceptance for calling it a "public case"

1. Every input above is public, or a documented derivative whose redistribution terms were checked
   for that specific release.
2. The full chain runs from a clean clone with the documented local input parameters.
3. Expected tables are reproducible from the committed inputs; numeric tolerances are declared.
4. The case README states source, retrieval date, license, and what was **not** verified.
5. No unpublished compound identity, disease hypothesis or report text is included.

## Open decisions for the researcher

- Whether CTD permits the 179-gene subset and derived outputs on public GitHub/releases.
- Whether the STP exports and derived tables fall within Licensed Materials/CC BY 4.0.
- If neither permits the data, whether to keep the local case and publish only a query/filter recipe
  plus checksums, or choose another case with clear redistribution terms.

## Explicit non-goals

- No automatic STP submission.
- No bulk migration of historical docking tasks.
- No claim that a public case exists before the permission and redistribution gates are complete.
- No inference that public accessibility or non-commercial intent automatically grants permission.
