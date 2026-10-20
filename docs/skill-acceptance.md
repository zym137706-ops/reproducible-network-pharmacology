# Skill behavior acceptance

Scope: the thin `skills/np-workflow/SKILL.md` layer, exercised through the **existing CLI only**.
This is not a real-agent transcript and is not a claim that the Skill is validated generally.

## Recorded decisions reused

The scenario tests do not ask for new scientific decisions. They reuse the decisions recorded in
`examples/demo/run.yaml` / `CASE-FREEZE.yaml`:

- 8 PubChem-CID compounds, STP exports submitted manually;
- `stp_probability: 0.10`, separate `0.05` sensitivity run;
- GO BP, BH correction, explicit `enrichment.universe_file`;
- disease source/date from the config; no invented disease term;
- predictions are hypotheses, not validation.

## Scenario matrix

Executable evidence: `tests/skill/test_skill_scenarios.py` (all pass in the normal test suite).

| Scenario | Action | Expected observable behavior |
|---|---|---|
| normal | validate → ingest → intersect → network → report | exit 0; report audit `stage_status: complete`; stages present |
| missing file | `rnp validate` with a nonexistent disease file | exit 2; missing path named; no output directory |
| partial upstream | ingest with one of two exports missing → intersect without/with `--allow-partial` | ingest exit 3, audit `partial`; intersect exit 2 and no output; with override exit 0 and `partial_override`; report refuses without `--allow-partial` |
| tamper | append to `targets.tsv` after ingest → `rnp report` | exit 2; error names `targets.tsv` / changed upstream; no report directory |
| zero result | disease gene absent from targets → ingest/intersect/network/report | exit 0; report audit `stage_status: empty`; zero intersection shown, no invented edges/terms |
| R process failure | simulated rc=1/137 with normal-looking meta | wrapper rejects with exit 3; no staged output (`tests/unit/test_enrich_wrapper.py`) |

## Explicit non-claims

- The Skill draft is not validated against a live agent/model run; the table above is CLI behavior.
- No public scientific case exists yet; `examples/demo/CASE-FREEZE.yaml` is `blocked`.
- Windows R native exit `0xC0000005` is unresolved; Linux CI is the verified environment.
