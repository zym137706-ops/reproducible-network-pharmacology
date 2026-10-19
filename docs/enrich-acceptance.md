# Enrichment: acceptance criteria

Status: **implemented 2026-10-19** as `rnp enrich` + `R/ora.R`, with tests listed below.
CI execution evidence on GitHub is still pending; local results are recorded in the changelog.
The command refuses an incomplete intersection stage by default (`--allow-partial` records an
override).

## Contract

1. Input is the intersection gene table plus an explicit background/universe; both are recorded.
2. Output contains the **complete** tested-term table (not only significant rows), the actual
   background used, gene-set source/release, and the mapping loss (input → mapped → unmapped).
3. The result table is deterministic: fixed ordering, full precision, no wall-clock values.
4. A manifest records: R version, `clusterProfiler`, `DOSE`, OrgDb and gene-set versions, the
   universe, correction method and cutoffs.

## Failure semantics (must be distinguishable)

| Situation | Required behaviour |
|---|---|
| Background/universe cannot be mapped | stop with exit 2; do **not** fall back to all annotated genes |
| Foreground genes partially unmapped | continue only with the mapped subset, report the unmapped list and counts in the audit |
| R package missing / R service error | exit 2 or 3 with the R stderr; not "no significant terms" |
| Analysis completed, zero significant terms | exit 0 with `status: completed_no_significant_terms`, complete table present |
| KEGG unavailable (network/license) | explicit `kegg_unavailable` status; GO results unaffected |

"No significant result" and "the analysis failed" must never share a code path or a status value.

## Independent numeric benchmark

- Frozen synthetic gene sets (small, hand-written) and a frozen foreground list.
- Independent hypergeometric p-value computed in the test itself (e.g. `scipy.stats.hypergeom`
  or a direct combinatorial implementation), compared to the R engine with declared tolerance.
- Independent BH adjustment compared on a fixed p-value vector.
- Real GO contract test remains separate (column contract + ordering), because Bioconductor
  releases change p-values slightly.

## Environment

- Python and R versions recorded; R package versions recorded per run.
- No dependency on a live enrichment service in the default test path; a real-service test is
  opt-in and must be skipped with a reason when unavailable.
- Resource lookup must work from an installed wheel, not only from the source tree.

## CLI acceptance tests

- [x] `rnp enrich --config run.yaml --intersect <dir>` writes `enrichment/<group>/` with complete
      table, significant view, meta and `enrichment_audit.json` + manifest.
- [x] incomplete/partial intersection is refused by default (`--allow-partial` override recorded).
- [x] unmapped explicit background stops the run; unmapped foreground is reported and counted.
- [x] zero-significant run exits 0 and says so explicitly (`completed_no_significant_terms`).
- [x] synthetic hypergeometric/BH benchmark passes against an independent Python calculation;
      live GO contract test remains green.
- [x] manifest/audit contain R/annotation versions, actual background counts and mapping loss.
- [x] CI execution on GitHub recorded: [run 39247312505](https://github.com/zym137706-ops/reproducible-network-pharmacology/actions/runs/39247312505)
      — all four jobs green (Python 3.10/3.11/3.12 + R 4.5 enrichment bridge).
