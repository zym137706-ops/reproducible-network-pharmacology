# ADR 0002 — R `clusterProfiler` as the enrichment engine

- Status: accepted
- Date: 2026-10-18
- Clarified: 2026-10-19; engine choice retained, numeric validation and provenance requirements corrected.

## Context

Enrichment (GO / KEGG over-representation) is the step with the most hidden choices: background
universe, ontology, gene-set size limits, multiple-testing correction, and package version. The
existing local workflow used DAVID (a website) and, for module enrichment, a hand-written R
hypergeometric test. Reproducibility depends on recorded inputs, reference snapshots, parameters and
independent validation; neither a website export nor hand-written statistics is intrinsically
unreproducible. The project needs an explicit testable contract for its chosen implementation.

Candidates:

1. pure-Python hypergeometric + BH implementation with frozen gene sets;
2. `gseapy` (Python) against Enrichr;
3. R `clusterProfiler` (Bioconductor);
4. keep DAVID.

## Decision

Use R `clusterProfiler` behind a JSON contract (`R/ora.R` ↔ `schemas/enrichment_input.schema.json`).
Python owns orchestration, input validation and provenance; R owns the statistics and reports its
own package versions (`clusterProfiler`, `DOSE`, OrgDb, R) in `enrichment_meta.json`.

## Why not the alternatives

- **Pure Python** is a viable approach with frozen annotations and numerical validation. We retain
  the existing R ecosystem to reduce implementation scope; engine choice alone does not guarantee
  reproducibility or reviewer-expected values.
- **gseapy/Enrichr** depends on a live service and on gene-set libraries that change over time;
  neither the library version nor the background is recorded by default.
- **DAVID** exports may be audited as external historical artifacts. This repository chooses a
  local R bridge for its controlled/offline tests; this decision does not assert DAVID has no APIs.

## Consequences

- The project has an R + Bioconductor dependency. It is isolated behind one command and one schema,
  and the rest of the pipeline (parsing, intersection, networks, provenance) still works without R.
- CI needs an R job. It is restricted to `main` / manual dispatch so pull requests stay fast.
- Live GO contract tests tolerate annotation-version changes and are not numeric truth tests.
  Independently calculable frozen synthetic gene sets must additionally test hypergeometric
  probabilities, universe denominators, test-family definition and BH with declared tolerance.
  Fixed-environment golden tests remain useful; dependency drift is not a reason to omit them.
- KEGG remains network- and license-constrained. Offline CI uses GO; KEGG is opt-in.

## Acceptance requirements still pending

User-specified background mapping failures must not fall back silently to default annotations.
Record mapped/unmapped foreground and background plus the actual eligible universe and its hash.
Keep all tested terms and their corrected values before significance/display filtering.
Define zero-hit test-family inclusion and per-module versus across-module correction explicitly.
Separate service/mapping failure from successfully computed no-significant results and propagate
machine-readable status. Record actual reference/package bindings; user-entered version text is insufficient.
These are design corrections, not changes to the current R script.
