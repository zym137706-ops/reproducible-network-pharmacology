# AGENTS.md — instructions for coding agents

This repository is a reproducible network-pharmacology toolkit. Keep the deterministic core and the
agent layer strictly separated.

## Before changing code

1. Read `docs/architecture.md` and `docs/review-gates.md`.
2. Read the relevant ADR in `docs/adr/` before questioning a design decision. Scope revisions are
   in ADR 0004; the maintained roadmap is `docs/project-plan.zh-CN.md`. Planned upstream/docking
   contracts in `docs/upstream.md` and `docs/docking.md` are not implemented capabilities.
3. Use the project virtual environment: `uv run python ...`, `uv run pytest`, `uv run ruff check .`.

## Rules

- **Keep research data private.** Never commit unpublished/patient-derived data or generated
  research outputs. `results/` and `data/local/` stay ignored. Explicit synthetic fixtures and
  independently checkable expected tables are allowed in tests/examples; public demo inputs need
  documented provenance and verified redistribution terms.
- **Never put business logic in `skills/`.** The skill calls the CLI; if a capability is missing,
  add it to `src/rnp/` and expose it as a command.
- **Schemas before code.** A new input or output artifact needs a JSON Schema in `schemas/` and a
  test validating both a good and a bad example.
- **Explicit failure over silent recovery.** If a row cannot be parsed, raise with the file, row and
  the reason; do not drop it silently.
- **Deterministic outputs.** Sort tables, format numbers, never embed wall-clock time inside result
  tables (timestamps belong in `run_manifest.json`).
- **No claims of validation.** A predicted association is not a validated mechanism. Do not add
  wording that implies efficacy, direction of effect, or experimental confirmation.
- **Licenses.** Repository policy excludes vendored GeneCards, OMIM, KEGG or DAVID output.
  Other sources are not automatically redistributable: check the particular release, terms and
  attribution in `docs/data-licenses.md`. Public accessibility alone is insufficient.
- **Status and decisions.** Separate designed/implemented/tested/released. Honor already recorded
  researcher choices and ask only about missing/conflicting scientific decisions.

## Commit convention

Conventional Commits, e.g. `feat(ingest): parse merged-title xlsx exports`,
`test(intersect): cover retired HGNC symbols`, `docs(adr): record R enrichment decision`.

## Definition of done for a feature

- [ ] schema updated (if inputs/outputs changed)
- [ ] unit test for the happy path **and** at least one failure mode
- [ ] `uv run ruff check .` and `uv run pytest -q` pass
- [ ] docs updated (`README` command table, `docs/` if behaviour changed)
- [ ] no new dependency without a line in `CHANGELOG.md`
