---
name: np-workflow
description: Orchestrate the reproducible-network-pharmacology CLI (rnp) for a compound–target–disease run. Use when the user asks for a network-pharmacology workflow, needs to validate/ingest SwissTargetPrediction exports, intersect disease genes, build Cytoscape tables, run enrichment, or render a traceable report. This skill only calls the installed rnp commands; it contains no analysis logic.
---

# Network-pharmacology workflow (CLI orchestrator)

The deterministic core is the `rnp` command. This skill **only** runs those commands, stops at
review gates, and explains their audit output. Never re-implement parsing, mapping, intersection,
statistics or report wording in the skill, and never edit generated files by hand.

## Recorded decisions: reuse, do not re-ask

Decisions already recorded in the **active** config/audit are reused; ask only when a decision is
missing, conflicting or scientifically changed. Do not ask the same question on every stage.

- **Case-specific configuration (not generic defaults).** The eight `examples/demo` PubChem-CID
  compounds, CTD disease source, `stp_probability: 0.10`, the `0.05` sensitivity, GO BP/BH cutoffs
  and the demo's explicit universe belong to that case's `run.yaml`. Never apply them to another
  user's task or invent them when a case config is absent.
- **Generic policy:** use the config's thresholds, correction and explicit `enrichment.universe_file`;
  never fall back to the annotated genome. SwissTargetPrediction exports are submitted manually by
  the researcher; never automate STP submissions.
- A public case is not complete until `docs/public-case-checklist.md` is satisfied; a blocked
  `examples/demo/CASE-FREEZE.yaml` is not a public case and must not be described as one.

## Preconditions

1. Work in the repository checkout and use its locked environment:
   `uv sync --locked --extra dev`, then use the project R entry point:
   - Linux/macOS: `bash scripts/restore_r.sh` (or `bash scripts/restore_r.sh /abs/lib`), then
     `export R_LIBS="<exact R_LIBS path printed by the script>"`;
   - Windows: `.\scripts\restore_r.ps1` (or `-Library C:\abs\lib`), then set `$env:R_LIBS` to the
     printed absolute path.
   Do not guess a platform/version `renv/library` subdirectory; use the exact path the script prints.
2. Set `RNP_RSCRIPT` only if `Rscript` is not on `PATH`; keep the same `R_LIBS` for every command.
3. Use the actual config path and output paths from the user's case; do not hard-code the quickstart.
4. Do not invent or silently repair input data. If a required input is missing, stop and report the
   exact missing path.

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

## Review gates: reuse first, ask only on a real decision

- **After ingest**: report bound/quarantined exports and invalid rows from the audit. Do **not** ask
  for confirmation when the binding matches the recorded config and there are no anomalies. Ask only
  if exports are missing/quarantined, rows invalid, or the config has no explicit binding.
- **After intersect**: report per-group counts and exclusions. Continue without a new question when
  the stage is complete and no decision changed. Ask only for a conflict, unexpected exclusion, or
  a changed disease/source decision.
- **Before enrichment**: use the `enrichment.universe_file` already recorded in the config. Ask only
  if it is missing, conflicts with a newer decision, or the user changes the background.
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

## Failure handling (scenario acceptance)

- **Missing file/config**: `rnp validate` exits 2; report the missing path, do not create a substitute
  file or switch to `allow_filename_match` silently.
- **Partial upstream**: a partial ingest exits 3; downstream `intersect` refuses unless the user
  chooses `--allow-partial`. If used, show the override and keep it recorded; never hide it.
- **Tampered artifact**: `rnp report` exits 2 because a recorded hash no longer matches. Do not edit
  the report or weaken the hash check; identify the changed file and re-run the affected stage.
- **Zero result**: an empty intersection/network is a valid `empty` result, not an error. Report the
  real audited counts: the intersection and network are zero, but raw target, disease-gene,
  compound-linkage and mapping-loss counts keep their actual values (do not zero them), and no edges
  or enrichment terms may be invented.
- **R process failure**: any non-zero R exit is a failure even if `enrichment_meta.json` looks
  normal; surface the exit code and stderr.

## Boundaries

- No automatic SwissTargetPrediction submission.
- No docking, topology, ADMET or upstream metabolomics commands in this skill.
- No claims of experimental validation; keep the generated report's limitation statement.
