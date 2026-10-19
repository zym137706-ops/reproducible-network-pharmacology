# Scientific review decisions and gates

Updated 2026-10-19. This is the target decision contract, not a claim that an interactive gate
engine or every decision artifact exists. Current CLI behavior must be checked in source/tests.
Keep decisions and their evidence separate from approval to perform ordinary engineering work.

## Core decisions

| Gate | Scientific decision | Existing evidence / target recording |
|---|---|---|
| G1 | Which compounds are in scope and why | Current compound list; planned explicit include/exclude/needs_review decisions with stable IDs |
| G2 | Prediction threshold and rationale | Current run config; planned threshold/invalid/no-result states and sensitivity records |
| G3 | Resolve ambiguous/retired symbols and symbol–UniProt conflicts | Current gene_mapping_conflicts.tsv and exclusions; accepted resolutions need traceable decision references |
| G4 | Treatment of composite/multi-symbol targets | Current target_exclusions.tsv; no probability distributed to subunits |
| G5 | Disease source, query, inclusion criteria and retrieval version | Config/source records; actual file provenance required before calling the result reproducible |
| G6 | Pathway display filtering | Planned raw/filtered/excluded tables; correction family remains unchanged |
| G7 | Wording supported by actual evidence | Planned report linked to specific results; no claims of binding, effect direction or efficacy |

## Upstream and docking decisions (planned)

| Gate | Decision and stopping condition | Target recording |
|---|---|---|
| G8 | Structure identity, MSI evidence, salt/stereo/charge policy; unresolved identity cannot become a confirmed structure automatically | Structure registry, transformations and evidence references; see upstream.md |
| G9 | Explicit candidate inclusion/exclusion; property rules do not silently delete original records | Selection decisions, rules version, rationale and reviewer/method |
| G10 | Which compound–protein pairs and receptor/site/control are suitable | candidate_pairs.tsv plus eligibility and decision references; see docking.md |
| G11 | Preparation, sampling budget, redocking/QC acceptance and reporting | Locked protocol, per-check outputs, actual commands/logs and acceptance decision |

## Reuse recorded decisions

- A complete, applicable researcher decision already in config/records satisfies that gate.
  Do not ask again merely because the pipeline is re-run.
- Ask only for missing, conflicting or scientifically changed decisions; record the answer,
  relevant input/rules versions and evidence.
- Routine deterministic processing may continue for eligible records. Isolate unresolved records;
  do not label them included, validated or successfully processed.
- For missing scientific inputs, a synthetic engineering example may proceed if clearly labelled;
  it cannot substitute for a decision or evidence in the real scientific analysis.
- Do not change thresholds, boxes or states repeatedly until a desired conclusion appears.
- A skipped/not-applicable check is explicit in the report; it must not become a pass.
- Stage-state enforcement is implemented: partial/incomplete upstream runs are rejected by default
  (exit 2) unless `--allow-partial` records an explicit override; file existence alone is not success.

## Boundaries

No automatic STP submission in this project; no retrying around third-party restrictions.
Private/unpublished inputs are not published. Data redistribution requires source-specific terms,
not an inference from public accessibility.
Reports must distinguish predicted association, annotation enrichment, pose recovery, physical
plausibility and activity-discrimination evidence from experimental validation.
