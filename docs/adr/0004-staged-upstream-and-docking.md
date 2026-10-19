# ADR 0004 — Staged upstream identity and calibrated docking

- Status: accepted design; implementation pending
- Date: 2026-10-19
- Supersedes: the post-prediction-only/no-docking scope in ADR 0003; naming and private-data policy remain.
- Updates: roadmap and acceptance requirements in architecture.md; enrichment validation clarification in ADR 0002.

## Context

The user authorized adding upstream compound selection and downstream molecular docking.
The existing core has ingest/intersection/network implementations; the full demo, enrichment CLI,
report and Skill are still incomplete. Expanded scope must not be described as implemented.

## Decision

1. Ship the v0.1 core and minimal Skill/demo first, with explicit export binding and failure semantics.
2. In v0.2 accept both confirmed compound lists and processed metabolomics annotations. Preserve
   identity evidence, all candidates, structure transformations and explicit selection decisions.
3. Add stable compound/structure/submission identity, separate group occurrences and ligand states;
   migrate existing name-based input explicitly rather than inventing chemical identities.
4. Put a reviewed compound–protein pair table between network prioritization and docking.
5. v0.3 docking initially covers suitable co-crystal reference systems and ordinary noncovalent
   small molecules, with target-relevant controls, redocking and pose plausibility checks.
6. PPI topology/RRA and MCODE are independent later extensions. RRA ranking does not replace module
   detection. STRING is a downstream optional branch, not an intersection prerequisite.
7. Predicted structures, unusual chemistries and historical batch migration require separate
   validation before becoming supported capabilities.

## Consequences

- CLI remains the only computational implementation; no automatic external STP submission.
- New artifact schemas and good/bad examples are required before implementing these contracts.
- Missing identity/evidence remains unresolved; mass agreement cannot confirm an isomer.
- Redocking, physical plausibility, screening discrimination and biological validation are
  different assessments and must be reported separately.
- Existing historical files are retained with provenance, not deleted during migration.
- The repository plan is docs/project-plan.zh-CN.md; detailed contracts are upstream.md and docking.md.
- This ADR and the detailed designs do not add commands or change existing runtime behavior.
