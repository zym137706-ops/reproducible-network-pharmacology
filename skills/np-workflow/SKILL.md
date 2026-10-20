---
name: np-workflow
description: Orchestrate the reproducible-network-pharmacology CLI (rnp) for a compound–target–disease run. Use when the user asks for a network-pharmacology workflow, needs to validate/ingest SwissTargetPrediction exports, intersect disease genes, build Cytoscape tables, run enrichment, or render a traceable report. This skill only calls the installed rnp commands; it contains no analysis logic.
---

# Network-pharmacology workflow (CLI orchestrator)

The deterministic core is the `rnp` command. This skill **only** runs those commands, stops at
review gates, and explains their audit output. Never re-implement parsing, mapping, intersection,
statistics or report wording in the skill, and never edit generated files by hand.

## Preconditions

1. Work in the repository checkout and use its locked environment:
   `uv sync --locked --extra dev`, then `uv run rnp --version`.
2. R is only needed for enrichment. If `Rscript` is not on `PATH`, ask for its path and use
   `--rscript` (or set `RNP_RSCRIPT`).
3. Do not invent or silently repair input data. If a required input is missing, stop and ask.

## Command sequence

Run these in order; a later command refuses an incomplete earlier stage unless the user explicitly
accepts `--allow-partial` (recorded in the audit):

```bash
uv run rnp validate --config <run.yaml>
uv run rnp ingest stp --config <run.yaml> --run-id <run-id>
uv run rnp intersect --config <run.yaml> --targets results/<run-id>/targets.tsv
uv run rnp network --config <run.yaml> --intersect results/<run-id>/intersect
uv run rnp enrich --config <run.yaml> --intersect results/<run-id>/intersect
uv run rnp report --config <run.yaml> --run-dir results/<run-id>
uv run rnp manifest --run-dir results/<run-id> --check-inputs
```

`--force` is only used after the user agrees to replace an existing output directory.

## Review gates (ask the human; do not bypass)

- **After ingest**: report bound/quarantined exports and invalid rows. Confirm the binding is what
  the user intended before intersecting.
- **After intersect**: report per-group counts and exclusions; ask whether to continue.
- **Before enrichment**: confirm the explicit `enrichment.universe_file` is the intended background;
  never substitute "all genes".
- **Before sharing a report**: show the output path and state that predictions are hypotheses, not
  validated mechanisms, direction of effect, or efficacy.

## Reading results

- Trust exit codes: `0` success, `2` input/validation error (nothing usable written), `3` partial
  failure/override, `1` unexpected bug. A non-zero R process is a failure even if a meta file looks
  normal.
- Each stage writes `run_manifest.json` and an audit file. Quote counts from the audit, not from
  the console narration.
- `rnp report` verifies recorded hashes. If it refuses, do not hand-edit the report: find what
  changed and re-run the affected stage.
- Use `rnp manifest --check-inputs` before calling a run reproducible.

## Boundaries

- No automatic SwissTargetPrediction submission.
- No docking, topology, ADMET or upstream metabolomics commands in this skill.
- No claims of experimental validation; keep the generated report's limitation statement.
