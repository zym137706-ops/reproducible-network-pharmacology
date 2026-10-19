# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Enrichment CLI — 2026-10-19

- Added `rnp enrich`: per-group ORA through the R `clusterProfiler` bridge with an explicit
  background (`enrichment.universe_file`, required). An unmappable explicit background is a hard
  error and is never replaced by the default annotated genome.
- The complete tested-term table is always written (`enrichment_result.tsv`), plus a filtered
  `enrichment_significant.tsv`. "Completed with no significant term" is a distinct status from a
  failed R analysis and from an unmapped foreground.
- Added `enrichment.schema.json` (stage audit) and recorded per-group mapping loss, tested-term
  counts, result/meta hashes, R exit code and package versions.
- R bridge now computes the complete table with `pvalueCutoff = qvalueCutoff = 1`, reports the
  requested cutoffs and the explicit background counts, and supports frozen
  `synthetic_gene_sets` for an independent hypergeometric/BH benchmark.
- Added tests: background required, zero-foreground empty result, missing Rscript, overwrite guard,
  live GO contract, CLI, and a combinatorial hypergeometric/BH benchmark that computes expected
  values independently in Python.
- Updated README (quickstart, command table), architecture, enrichment acceptance notes and CI
  R job to include the new stage.
- CI: [run 39247312505](https://github.com/zym137706-ops/reproducible-network-pharmacology/actions/runs/39247312505)
  completed green for all four jobs (Python 3.10/3.11/3.12 lint+tests+demo+wheel, R 4.5 bridge tests).

### Hardening — 2026-10-19 (v0.1 slice)

- Ingest now requires an explicit compound↔export binding (`stp_file`) unless
  `inputs.allow_filename_match: true` is set as a recorded compatibility mode. Unbound exports are
  quarantined in `stp_audit.json` and never enter `targets.tsv`.
- File status is a taxonomy, not a boolean: `ok`, `partial`, `below_threshold`, `invalid_rows`,
  `no_predictions`, `error`, `quarantined`. `rows_invalid` is counted separately from
  `rows_below_threshold`; `rows_valid` and `rows_below_threshold` are both reported. Missing required
  columns raise a consistent error.
- Run-level `stage_status` (`complete` / `partial` / `failed`) is written to the audit; failed runs
  leave no output directory, partial runs exit 3.
- `rnp intersect` and `rnp network` verify the parent audit, stage status, parent hashes and config
  identity, and refuse incomplete upstream stages unless `--allow-partial` is passed; the override is
  recorded in the audit and manifest.
- Output directories are written through a temporary sibling and atomically moved; existing outputs
  are refused unless `--force` is passed.
- Stable compound identity: a persistent registry (`results/registry/compound_registry.tsv` by
  default, or `inputs.compound_registry`) assigns/reuses `compound_id`; explicit IDs, case-insensitive
  matches and renames matched by `stp_file` are recorded as such. This is a name-based migration, not
  a chemical-structure registration (v0.2).
- Manifest schema 2.0 separates **code identity** (package version/commit/root) from **config
  identity** (path, SHA-256, config-repository state), records parent-stage audit hashes and the
  stage status, and records whether an output was overwritten.
- Zero-intersection runs now produce a valid **empty** network audit and no fabricated group
  directory.
- Added `scripts/synthetic_demo.py`: one command runs five synthetic scenarios (normal, extra export,
  zero intersection, ambiguous mapping, partial upstream) and compares results with hand-computed
  expectations.
- Packaged `R/` scripts into the wheel and added `rnp.resources` so the Venn script is locatable after
  installation.
- 28 new/changed tests (88 total in this environment); schemas updated to `stp_audit` 1.1,
  `intersection` 1.1, `network` 1.1, `run_manifest` 2.0.
- Added `docs/public-case-checklist.md` and `docs/enrich-acceptance.md`; synchronized README,
  architecture and this changelog with implemented vs pending status.
- Still pending: enrichment CLI, report, Skill layer, public scientific case, generated Python lock
  and recorded CI/wheel-install evidence.

### Documentation / design — 2026-10-19

- Added the maintained Chinese v3 plan, upstream identity/selection contract, candidate-pair/docking
  contract and a bounded DSH implementation handoff.
- ADR 0004 stages the v0.1 core, v0.2 upstream and v0.3 minimal calibrated docking; topology/MCODE
  remain independent extensions. ADR 0003 scope is partially superseded.
- Corrected mass/identity, redocking/RMSD, pLDDT, failure-status and numeric-validation requirements;
  synchronized README, architecture, limitations and review decisions with pending implementation.
- These are documentation changes only: no CLI/Schema/runtime behavior or dependency was changed,
  no new test run/release is claimed, and prior staged work is preserved.

### Added (existing implementation)

- `rnp intersect`: HGNC normalization of target genes (approved/previous/alias/unique-UniProt,
  with ambiguity and symbol↔UniProt conflicts reported), best-probability deduplication per
  compound–gene pair, disease intersection, per-group set counts, `venn.json`, and an audit of every
  excluded row.
- `rnp network`: per-group Cytoscape node/edge/MOLlist tables with invariant checks (endpoint/node
  consistency, no duplicate edges, MOLID coverage, compound↔gene collision detection).
- `R/venny.R`: optional two-set Venn figure (PNG + PDF) rendered from `venn.json`.
- Schemas `intersection.schema.json` and `network.schema.json`; `inputs.hgnc_map` and `network.*`
  added to the run schema.
- 22 new tests (60 total): mapping rules, exclusions, collision handling, CLI chain, manifest
  contracts, optional R Venn rendering.

### Planned

- Public-data demo with golden files
- `rnp enrich` CLI, explicit background/status handling and independent numeric tests
- Upstream structure identity/selection (v0.2); limited calibrated docking (v0.3)
- Independent later topology/RRA and MCODE extensions
- `rnp report` and the agent skill layer

## [0.0.1] scaffold - 2026-10-18

Local package/scaffold milestone; this heading does not assert a published tag or GitHub release.
Historical test totals below are prior reports, not a fresh result from this documentation revision.

### Added

- Python package `reproducible-network-pharmacology` with the `rnp` CLI.
- JSON Schemas for the run config, STP audit, run manifest and the R enrichment bridge.
- `rnp validate`: schema validation plus existence checks for every declared input.
- `rnp ingest stp`: SwissTargetPrediction `.csv` / `.xlsx` parsing with merged-title-row
  detection, multi-symbol and composite-target handling, probability validation, per-file
  audit (`stp_audit.json`), deterministic `targets.tsv`, and a `run_manifest.json`.
- `rnp manifest`: schema validation plus input-hash drift detection.
- `R/ora.R`: GO/KEGG over-representation bridge via `clusterProfiler`, reporting its own
  package versions and writing a stable result table.
- Tests: 38 cases covering config validation, every known STP trap, CLI exit codes, manifest
  drift, and the R bridge contract (live run when `Rscript` is available).
- CI: lint + tests on Python 3.10–3.12, plus an R contract job on `main`.
- Documentation: architecture, review gates, limitations, data licenses, three ADRs.
