# Architecture

> Status: current implementation plus explicitly marked target contracts. Updated 2026-10-19.
> The accepted scope extension is [ADR-0004](adr/0004-staged-upstream-and-docking.md).
> See the [maintained plan](project-plan.zh-CN.md), [upstream design](upstream.md),
> [docking design](docking.md) and [next implementation slice](next-steps-dsh.md).
> No new runtime capability is added by these documents.

## 1. Purpose

Make a network-pharmacology analysis **explainable and re-runnable**: given the same inputs,
reference-data versions and parameters, the same tables should come out, and every run should
record enough metadata to reconstruct what happened.

## 2. Non-goals

- No online prediction, no scraping of third-party services, no hidden-form replaying.
- v0.1 core remains post-prediction. v0.2 adds confirmed-list/processed-metabolomics identity,
  annotation and explicit selection; v0.3 adds limited, controlled noncovalent docking.
- No raw LC-MS processing, ADMET model training, QSAR or broad receptor/chemistry support in these releases.
- No claims of biological validation; the output is *predicted association* and *annotation overlap*.

## 3. Layering

```
┌──────────────────────────────────────────────────────────────┐
│ Agent layer (skills/np-workflow/SKILL.md)                     │
│ Orchestrates commands, asks a human at review gates,          │
│ explains results and wording. Contains NO business logic.     │
└───────────────────────────┬──────────────────────────────────┘
                            │ subprocess: rnp <command>
┌───────────────────────────▼──────────────────────────────────┐
│ Deterministic core (src/rnp)                                  │
│ validate → ingest → normalize → intersect → network           │
│ → enrich → report → manifest; optional extensions            │
│ Each command: schema check, explicit exit code, audit file.   │
└───────────────────────────┬──────────────────────────────────┘
                            │ files
┌───────────────────────────▼──────────────────────────────────┐
│ Data layer                                                     │
│ schemas/ (contracts) · data/reference/ (downloaded, hashed)   │
│ examples/demo/ (public) · results/<run_id>/ (git-ignored)     │
└──────────────────────────────────────────────────────────────┘
```

**Rule:** if a capability is missing, it is added to `src/rnp` and exposed as a CLI command.
The skill may not re-implement it in prose or in a snippet.

## 4. Module map

| Module | Responsibility |
|---|---|
| `rnp.config` | load YAML/JSON, validate against `schemas/run.schema.json`, resolve paths relative to the config file |
| `rnp.errors` | exit-code contract (`0/2/3/1`) and user-facing messages |
| `rnp.provenance` | SHA-256, environment capture, `run_manifest.json` |
| `rnp.io.stp` | SwissTargetPrediction export parsing, file-status taxonomy and audit |
| `rnp.io.tables` | delimited-table readers/writers shared by pipeline commands |
| `rnp.normalize.hgnc` | HGNC symbol/alias/UniProt normalization with conflict reporting |
| `rnp.normalize.identities` | persistent `compound_id` registry and explicit export binding |
| `rnp.analysis.ingest` | binding, quarantine, stage status, `targets.tsv` + audit |
| `rnp.analysis.intersect` | compound–target edges, disease intersection, exclusion audit, Venn data |
| `rnp.analysis.network` | Cytoscape node/edge/MOLlist tables and their invariants |
| `rnp.analysis.enrich` | explicit-background ORA via the R bridge; complete table + significant view |
| `rnp.analysis.report` | Markdown rendering from hash-verified stage audits; no re-computation |
| `rnp.analysis.parents` | parent-stage status/hash checks and refusal semantics |
| `rnp.output` | staged, atomic output directories; no silent overwrite |
| `rnp.resources` | packaged resource lookup (schemas/R scripts) in source tree and wheel |
| `rnp.analysis.*` | report CLI (pending); MCODE/topology later, independently validated |
| `R/ora.R` | over-representation analysis via `clusterProfiler`; writes its own version metadata |
| `R/venny.R` | two-set Venn figure from `intersect/venn.json` (optional) |

## 5. Run lifecycle

1. `rnp validate --config run.yaml` — schema + path checks; nothing is written.
2. `rnp ingest stp --config run.yaml` — per-file parse, audit, `targets.tsv`, manifest.
3. `rnp intersect --config run.yaml --targets results/<id>/targets.tsv` — HGNC mapping,
   compound–target edges, disease intersection, exclusions, `venn.json`, manifest.
4. `rnp network --config run.yaml --intersect results/<id>/intersect` — Cytoscape node/edge/
   MOLlist tables per group, invariant checks, manifest.
5. `rnp enrich --config run.yaml --intersect results/<id>/intersect` — per-group ORA with an
   explicit background; complete tested-term table, significant view, function-loss and R versions
   recorded. STRING/PPI import, topology and MCODE are optional downstream branches; PPI edges are
   not an input prerequisite for gene-set intersection.
6. `rnp report --config run.yaml --run-dir results/<id>` — verifies stage audits/hashes and renders
   Markdown; missing stages are "not run", partial stages need an explicit override.
7. `rnp manifest --run-dir results/<id> --check-inputs` — verify nothing drifted.

`run_id` = UTC timestamp + first 8 hex of the config SHA-256, e.g. `20261018T051500Z_6f037817`.
It is overridable (`--run-id`) so tests and re-runs are reproducible.

## 6. Output layout

```
results/<run_id>/
├── targets.tsv           # audited, thresholded target table
├── stp_audit.json        # what each export contained, what was warned/errored
├── run_manifest.json     # tool/commit/params/hashes/reference versions
├── intersect/
│   ├── edges.tsv         # mapped compound–target edges
│   ├── intersection_genes.tsv
│   ├── disease_genes.tsv
│   ├── target_exclusions.tsv     # every row that did not become an edge, with a reason
│   ├── gene_mapping_conflicts.tsv
│   ├── venn.json         # per-group set membership and counts
│   ├── venn_<group>.png/.pdf     # optional
│   ├── intersect_audit.json
│   └── run_manifest.json
├── network/<group>/
│   ├── edges.tsv         # Source, Target, Interaction
│   ├── nodes.tsv         # Node, Type, Label
│   ├── mol_list.tsv      # MOLID, moleculename
│   ├── node_attributes.tsv
│   └── network_audit.json + run_manifest.json (at network/ level)
├── enrichment/           # (planned) result table + meta from R
└── report.md             # (planned)
```

## 7. Exit-code contract

| Code | Meaning | What the caller should do |
|---|---|---|
| 0 | success | continue |
| 2 | validation/config error; nothing written | fix the config/inputs, do not retry |
| 3 | partial: some inputs processed, at least one failed | read the audit; the run is incomplete |
| 1 | unexpected internal error (bug) | report it; do not paper over |

Implemented: a failed ingest writes no run directory; a partial ingest writes outputs with
`stage_status: partial` and exits 3; `intersect`/`network` refuse a non-complete parent stage unless
`--allow-partial` is passed, and record the override (`status_override`, `stage_status:
partial_override`). File existence alone is not treated as success evidence.

## 8. Determinism rules

- Tables are sorted by explicit keys before writing.
- Machine-readable probability columns keep up to 10 significant digits (`targets.tsv`, edges,
  intersection); presentation rounding is a separate display concern and never changes selection.
- Result tables contain no wall-clock values; timestamps live only in `run_manifest.json`.
- The R bridge orders by `p.adjust` then term ID, and reports its package versions.
- Manifests also contain timestamps, paths and environment details. Golden tests compare normalized
  scientific tables with declared numeric tolerance, not byte-identical directories.

## 9. Schemas

Every input and output artifact is described by a JSON Schema in `schemas/`. The schema is
validated on load and re-validated on write (`SchemaViolation`, exit 1, means a bug, not bad data).
This makes the R bridge and the Python side independently testable. Current schemas do not yet cover
all planned artifacts, and some runtime cross-table checks remain incomplete. A JSON Schema cannot
replace foreign-key, cardinality or scientific-consistency checks.

## 10. Provenance

Implemented: the manifest separates **code identity** (package version, commit, dirty flag, root)
from **config identity** (config path, SHA-256, config-repository state), lists every consumed input
with its hash, records parent-stage audit files with their SHA-256, and carries a `stage_status`.
`rnp manifest --check-inputs` re-hashes recorded inputs and reports drift.
Remaining limitation: reference-data *files* are not yet bound by hash (only user-supplied version
strings), and the lock file / controlled R environment record is still pending.

## 11. Extension recipe

1. Add the artifact to `schemas/` (input and output).
2. Implement in `src/rnp/...` as a pure function that takes paths and returns a dict.
3. Add a CLI subcommand in `src/rnp/cli.py`; wire exit codes via `RnpError`.
4. Add fixtures: one good file, one real trap, one empty/invalid case.
5. Add the command to the README table and to the skill's command list.
6. Record any design trade-off as an ADR in `docs/adr/`.

## 12. Windows notes

The workstation this was developed on has MGLTools first on `PATH`, so bare `python` resolves to
Python 2.7. Use `py -3.12`, `uv run`, or the virtual environment interpreter explicitly. R lives at
`C:\Program Files\R\R-4.5.2\bin\Rscript.exe`; pass `RNP_RSCRIPT` to tests if it is not on `PATH`.

## 13. Accepted extension contracts (not implemented)

- v0.2: confirmed lists and processed annotations converge on stable compound/structure identity,
  separate feature/group occurrences, transformation history and explicit selection. See upstream.md.
- A reviewed candidate-pair table binds target identity, evidence, suitable receptor/site and controls.
- v0.3: suitable co-crystal systems and ordinary noncovalent small molecules only; preparation,
  actual seeded executions, redocking and pose plausibility are recorded separately.
- No native reference means redocking is not applicable; predicted structures need separately
  validated protocols. pLDDT is not sufficient docking eligibility evidence.
- RRA consensus ranks nodes; MCODE identifies modules. Neither substitutes for the other.

## 14. Release checks: closed in the 2026-10-19 slice, and still pending

Closed:

- compound/export linkage is enforced; unmatched exports are quarantined, never formal edges;
- no-predictions, below-threshold, invalid-rows, failed and partial runs are separate states;
- zero-intersection runs produce valid empty outputs without invented edges;
- downstream stages refuse incomplete upstream state by default (override recorded);
- code/config identities are separated and parent audit hashes are chained;
- an offline synthetic demo with hand-computed expectations exists;
- R scripts are packaged and resolved from the wheel (`rnp.resources`, tested).

Still pending (do not claim released):

- the Skill layer and a public scientific case with verified data terms
  ([checklist](public-case-checklist.md));
- generated Python lock file and a recorded R/Bioconductor/annotation environment;
- recorded CI results and a wheel-install smoke test in CI (workflow exists; execution evidence is
  tracked in the changelog);
- docking/upstream contracts (design only).

Closed with enrichment: explicit background enforcement, complete tested-term tables, no-hit vs
failure separation, per-group mapping loss, and an independent synthetic hypergeometric/BH
benchmark ([acceptance evidence](enrich-acceptance.md)). Closed with report: hash-verified stage
readings, "not run" handling, partial override, and evidence-bound wording.
