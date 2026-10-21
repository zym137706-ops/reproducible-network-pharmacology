# Skill behavior acceptance

Scope: the thin `skills/np-workflow/SKILL.md` layer. Three layers exist:

1. CLI scenario tests in `tests/skill/test_skill_scenarios.py` (deterministic pytest coverage).
2. A **real-agent session** (2026-10-20) that followed the SKILL and executed the same five
   scenarios through the CLI; report:
   [`skill-agent-acceptance-2026-10-20.md`](skill-agent-acceptance-2026-10-20.md).
3. The **final-revision Codex acceptance** (2026-10-21) at clean commit `e81f5bf`; report:
   [`skill-agent-acceptance-2026-10-21.md`](skill-agent-acceptance-2026-10-21.md). It covers
   normal/missing/partial/tamper/zero plus Linux enrichment/report (Codex invoked a Linux Docker
   pipeline); Codex CLI `0.147.0`, model `gpt-5.6-sol`, Skill SHA-256 `f2002b72…`. The report records
   the PowerShell-wrapper exit-display caveat and that Codex itself ran on the host.

The earlier real session passed 5/5 scenarios on DeepSeek Harness/`deepseek-flash`, Windows 11,
commit `49f0996` plus a dirty worktree. Enrichment was intentionally skipped because Windows R exits
`0xC0000005`; no enrichment result is claimed. This is one model/session and is not a general
validation claim.

## Recorded decisions reused

The scenarios reuse the decisions recorded in the supplied config / `examples/demo/CASE-FREEZE.yaml`
without re-asking. Only missing, conflicting or scientifically changed decisions are questions. The
8 compounds/CTD/0.10 thresholds are **case configuration**, not generic Skill defaults.

## Scenario matrix

Executable evidence: `tests/skill/test_skill_scenarios.py` (all pass in the normal test suite).

| Scenario | Action | Expected observable behavior |
|---|---|---|
| normal | validate → ingest → intersect → network → report | exit 0; report audit `stage_status: complete`; stages present |
| missing file | `rnp validate` with a nonexistent disease file | exit 2; missing path named; no output directory |
| partial upstream | ingest with one of two exports missing → intersect without/with `--allow-partial` | ingest exit 3, audit `partial`; intersect exit 2 and no output; with override exit 0 and `partial_override`; report refuses without `--allow-partial` |
| tamper | append to `targets.tsv` after ingest → `rnp report` | exit 2; error names `targets.tsv` / changed upstream; no report directory |
| zero result | disease gene absent from targets → ingest/intersect/network/report | exit 0; report audit `stage_status: empty`; zero intersection/network, but raw target/disease counts retain audit values; no invented edges/terms |
| R process failure | simulated rc=1/137 with normal-looking meta | wrapper rejects with exit 3; no staged output (`tests/unit/test_enrich_wrapper.py`) |

## Explicit non-claims

- The real sessions verify the scenarios for specific models/runs; they do not prove every agent will
  behave the same. The 2026-10-20 session did not exercise enrichment; the 2026-10-21 final-revision
  session exercised Linux R enrichment/report via a Docker invocation, not a Codex process running
  inside Linux.
- The local RA case is computed and independently checked, but `examples/demo/CASE-FREEZE.yaml` is
  **public-release blocked** pending CTD/STP permission. Local completion is not a public case pass.
- Windows R native exit `0xC0000005` is unresolved; Linux is the verified case environment.
- The final Skill at commit `e81f5bf` was used for the 2026-10-21 Codex session. Later documentation
  edits do not change its behavior; if `SKILL.md` changes, rerun the affected scenarios.
