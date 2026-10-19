# ADR 0003 — Naming, scope and data policy

- Status: accepted; scope partially superseded by ADR 0004 (2026-10-19)
- Date: 2026-10-18

## Context

The project needs a name that says what it is without over-claiming, and a scope that can be
finished part-time alongside wet-lab work. Two constraints dominate:

1. The author's real projects are **unpublished 2026 work** (three herbal-enzyme lines). Their
   reports are marked "for supervisor discussion". None of that data may be published.
2. Network pharmacology has a reputation problem (pipeline papers with unrecorded thresholds and
   predicted-then-claimed mechanisms). The repository must look like the opposite of that.

## Decision

- Distribution name: `reproducible-network-pharmacology` (descriptive, searchable, states the claim).
- Import package and CLI: `rnp` (short, typeable, stable if the long name is ever changed).
- Original scope: post-prediction analysis only. [ADR 0004](0004-staged-upstream-and-docking.md)
  retains this for v0.1, adds confirmed-list/processed-metabolomics identity and selection in v0.2,
  and limited calibrated docking in v0.3. No automatic online submission or ADMET model training.
- Data policy: zero unpublished data in the repository. Real projects contribute *format contracts
  and failure modes*, never values. The public demo uses public compounds and public databases.

## Consequences

- The long distribution name is a little unwieldy; the `rnp` CLI keeps daily use short. Renaming
  the distribution later does not break imports.
- Release scope remains staged and evidence-gated. Adding identity or docking does not make
  the project a complete drug-discovery or experimentally validated target-discovery platform.
- Reviewers asking "where is the data?" get a demo they can re-run and a documented boundary,
  instead of a private dataset they cannot inspect.
- If a real project is later published, `docs/case-study.md` can map its methods to commands —
  with the supervisor's permission and only after publication.
