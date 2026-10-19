# ADR 0001 — CLI core with a thin agent layer

- Status: accepted
- Date: 2026-10-18

## Context

The starting point was five locally written agent skills: two with real scripts, two with prose
report templates, and one browser-driven submission workflow. An audit found zero automated tests
in the self-written parts, four missing pipeline steps with no code, and project-specific constants
(hard-coded disease names, one group count, one R installation path).

For a portfolio-quality project, a repository of `SKILL.md` files proves prompt organisation, not
engineering. It also cannot be verified without the same agent and the same private data.

## Decision

Build a deterministic Python CLI (`rnp`) as the single source of truth, and keep the agent layer
thin: a `SKILL.md` that orchestrates commands, asks for human decisions at seven review gates, and
explains outputs. Every capability must be runnable without any agent.

## Alternatives considered

1. **Skills-only repository.** Fastest, but unverifiable and easily read as a prompt collection.
2. **Workflow engine first (Snakemake/Nextflow).** Strong signal for platform roles, but rewrites
   the stable parts before they are tested, and is too large for a part-time build.
3. **R package.** Fits the domain, but the parsing and provenance work is more natural in Python,
   and R is already used where it is strongest (enrichment).

## Consequences

- More upfront work (packaging, tests, CI) before anything is demonstrable.
- The skill layer stays small and cannot drift from the implementation.
- A workflow engine can be added later as a ~50-line wrapper around the same commands (planned v0.2).
- Reviewers can verify claims by running one command, without an agent or private data.
