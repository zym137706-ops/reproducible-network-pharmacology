# Real-agent acceptance report — `np-workflow` skill (2026-10-20)

> 公开整理说明（2026-10-28）：原始本机路径已统一替换为 `<workspace>`；模型、commit、版本、命令、退出码和失败限制保留未变。

**This was a real agent session, not pytest.** No test file was read, no `pytest` command was
executed, and no test was imported or invoked. The only access to `tests/` was indirect: the
supplied YAML configs declare data paths under `tests/fixtures/`, and the `rnp` CLI read those
fixture files as ordinary inputs. The scenarios below were executed by following
`skills/np-workflow/SKILL.md` and the CLI's own `--help`/audit output, not by copying assertions
from tests.

- Date of session: 2026-10-20 (Asia/Hong_Kong)
- Agent: DeepSeek Harness (DSH) delegated subagent
- Model route: `deepseek-flash` (as reported by the session runtime; the exact model build/version
  is **unknown** and was not exposed to the agent)
- Working sandbox: `<workspace>\rnp-skill-agent-run`
- Repository under test: `<workspace>\reproducible-network-pharmacology`
- OS: Microsoft Windows 11 家庭版 中文版, version 10.0.26200, build 26200, 64-bit
  (`platform.platform()` = `Windows-11-10.0.26200-SP0`); CPU: 12th Gen Intel Core i7-12800HX
- Toolchain: `uv 0.12.5`, project venv Python 3.12.5, `rnp 0.0.1`
- Git commit: `49f0996da8e93bf087d414751cf1e9ec1cdbc6d2` (short `49f0996`); the checkout was
  already dirty on arrival (`git status` showed pre-existing modifications/untracked files). The
  run manifests record `"dirty": true`.
- Repository working tree: **not modified by this session.** All commands that write used only
  `runs/` under the sandbox. No command targeted a repository path. Details and the observed
  concurrent changes are in §12.

## 1. Method

The five scenarios were run in the order requested: normal, missing, partial, tamper, zero. Each
command below was executed from `<workspace>\reproducible-network-pharmacology` with
`uv run rnp ...`. Exit codes were captured from the process (`$LASTEXITCODE`); structured audit
files and report provenance were read after each stage. No generated file was edited except the
single intentional `targets.tsv` newline append required by the tamper scenario.

Enrichment was **not run** and is **not claimed**. Per the task brief and this session's
pre-recorded environment decision, Windows native R exits `0xC0000005`; the normal chain therefore
ends at `report` + `manifest --check-inputs`, and the reports correctly show
`enrichment | not run`.

## 2. Configurations used

All five configs live in `<workspace>\rnp-skill-agent-run\`. Their SHA-256 values were computed locally
and cross-checked against the `config_sha256` values emitted by `rnp validate`/audits.

| Config | SHA-256 | Purpose |
|---|---|---|
| `normal.yaml` | `55597917cbcf873481f8c47332482068b12248ee191d6fe005298f43f3cc7971` | complete synthetic chain |
| `missing.yaml` | `6356bdaa896dec44d63c6fb833081bf17a166e0bc44c632742eec454619dec7a` | nonexistent disease file |
| `partial.yaml` | `75825a7c6235a737ac05cc03cc36e9db02c3b4a0be8b25d61f23ce8c5647d83f` | compound B has no export |
| `tamper.yaml` | `e6473c0a969857edf3172ed542eba2028017530f85bb24694f33408f4d6d61f8` | normal chain, then tamper |
| `zero.yaml` | `4bba48e1f31f6107b340d017f1f06715b6ceb2cb1d638cafedcc32288ff24c62` | disease ICAM1 not in targets |

Shared recorded settings (reused, not re-asked): `project: quickstart`; `species: Homo_sapiens`;
`thresholds.stp_probability: 0.1`; `disease_source: fixture`; `disease_retrieval_date:
2026-10-01`; references GO `2026-09-01`, HGNC `2026-09`; compounds/STP/disease/HGNC paths as
declared; output dirs `runs/{normal,missing,partial,tamper,zero}`; GO BP / BH enrichment settings
and an explicit `enrichment.universe_file` recorded in config (not exercised because enrichment
was skipped).

## 3. Result summary

| Scenario | Result | Exit codes observed |
|---|---|---|
| normal | **PASS** — complete chain, report + manifest check | validate 0, ingest 0, intersect 0, network 0, report 0, manifest 0 |
| missing | **PASS** — clean missing-input refusal, nothing written | validate 2 |
| partial | **PASS** — partial ingest 3; downstream refuses without override; pre-authorized override works and is recorded | ingest 3, intersect 2 (refused), intersect 0 (`--allow-partial`), report 2 (refused), report 0 (`--allow-partial`) |
| tamper | **PASS** — report refuses changed `targets.tsv` | validate 0, ingest 0, intersect 0, network 0, report 2 |
| zero | **PASS** — empty intersection/network is a valid `empty` result | validate 0, ingest 0, intersect 0, network 0, report 0 |

No scenario failed, and no scenario required fabricating data or overriding a hash check.

## 4. Scenario 1 — normal (canonical run `normal-acceptance-20261020`)

Canonical run directory:
`<workspace>\rnp-skill-agent-run\runs\normal\normal-acceptance-20261020`

| # | Exact command | Exit | Key status/audit output |
|---|---|---|---|
| 1 | `uv run rnp validate --config <workspace>\rnp-skill-agent-run\normal.yaml` | 0 | `status: ok`; config sha `55597917…`; `export_files: 2` |
| 2 | `uv run rnp ingest stp --config <workspace>\rnp-skill-agent-run\normal.yaml --run-id normal-acceptance-20261020` | 0 | `stage_status: complete`; files 2, bound 2, quarantined 0, missing 0; rows total 7, valid 7, used 6, below threshold 1, invalid 0; compounds 2; warnings 2, errors 0 |
| 3 | `uv run rnp intersect --config <workspace>\rnp-skill-agent-run\normal.yaml --targets <workspace>\rnp-skill-agent-run\runs\normal\normal-acceptance-20261020\targets.tsv` | 0 | `stage_status: complete`; compounds 2, linked 1, edges 4, targets 4, disease 10, intersection 2, target_only 2, disease_only 8, union 12; `compounds_without_edges: ["Kaempferol"]`; exclusions `multi_symbol_common_name: 2`; warnings 0 |
| 4 | `uv run rnp network --config <workspace>\rnp-skill-agent-run\normal.yaml --intersect <workspace>\rnp-skill-agent-run\runs\normal\normal-acceptance-20261020\intersect` | 0 | `stage_status: complete`; nodes 4, edges 4; compound–target edges 2, disease edges 2; all invariant checks passed |
| 5 | `uv run rnp report --config <workspace>\rnp-skill-agent-run\normal.yaml --run-dir <workspace>\rnp-skill-agent-run\runs\normal\normal-acceptance-20261020` | 0 | `stage_status: complete`; stages ingest/intersect/network all `complete`; warnings 0; `report_sha256: 6f3b5fdbbe4ff767dd0f3f8c84066a040f7b0f58dbac09cc2bab09f8938da552` |
| 6 | `uv run rnp manifest --run-dir <workspace>\rnp-skill-agent-run\runs\normal\normal-acceptance-20261020 --check-inputs` | 0 | `status: ok`; `inputs_checked: 4`; `drift: []`; tool `reproducible-network-pharmacology 0.0.1` |

Observations:

- Ingest audit: `compound_a.csv` 5 rows valid, 1 below threshold, 4 used; `compound_b.csv` 2 rows
  valid, 2 used. The two warnings are `multi_symbol_common_name` (“CDK5R1 CDK5”, “MAPK1 MAPK3”),
  which are also the 2 excluded rows reported by intersect. No rows invalid, no files quarantined,
  no exports missing.
- The run manifest records `python: 3.12.5`, `platform: Windows-11-10.0.26200-SP0`,
  `code.commit: 49f0996`, `code.dirty: true`, config sha `55597917…`, and `exit_code: 0`.
- `report.md` states the predicted/annotation-overlap limitation and lists enrichment as
  `not run`. It was not edited.
- `--run-id` is accepted by the CLI but suppressed from `--help` (the SKILL documents it). The
  first attempt used the CLI default and produced run id `20261020T112207Z_55597917`; the chain was
  then re-run with the explicit id above. The probe run is retained, complete, and not used as the
  canonical run. Because the compound registry is per `outputs.dir`, the canonical re-ingest found
  the two compounds already registered (`identity_basis: registry_name`, `first_seen_utc` from the
  probe) while producing an identical `targets.tsv`
  (`94a917a5e1b8a811d7f948ac1554bc4f8aa7bec175d77c6d7767b94562cbc8f8`); see §12.

Probe run (auto-generated id `20261020T112207Z_55597917`, retained for transparency; all exit 0):
`validate`; `ingest stp` (no `--run-id`); `intersect --targets ...\20261020T112207Z_55597917\targets.tsv`;
`network --intersect ...\intersect`; `report --run-dir ...\20261020T112207Z_55597917` (report sha
`a0193f84295de9ef80324241172bbc8c8e79d381555c66f8008b7b047bf6210b`); `manifest --check-inputs`
(`inputs_checked: 4`, `drift: []`). Same counts as the canonical run.

## 5. Scenario 2 — missing (`missing.yaml`)

| # | Exact command | Exit | Output |
|---|---|---|---|
| 1 | `uv run rnp validate --config <workspace>\rnp-skill-agent-run\missing.yaml` | 2 | `error: declared inputs are missing` / `- inputs.disease_genes: not a file: <workspace>\rnp-skill-agent-run\inputs\missing-disease.txt` |

Observations: the failure is clean, names the exact missing path and config key, and writes
nothing (`runs\missing` does not exist). The missing file was **not** created and no filename-match
fallback was used. Per SKILL, this is the expected `exit 2` behavior.

## 6. Scenario 3 — partial (`partial.yaml`)

Run directory: `<workspace>\rnp-skill-agent-run\runs\partial\20261020T112231Z_75825a7c`

| # | Exact command | Exit | Key status/audit output |
|---|---|---|---|
| 1 | `uv run rnp ingest stp --config <workspace>\rnp-skill-agent-run\partial.yaml` | 3 | `status: partial`, `stage_status: partial`; files 1, bound 1, missing 1; rows total 1, valid 1, used 1; errors 1; `missing_exports: [{compound_id: CMP0002, stp_file: b.csv, status: error, reason: missing_export}]` |
| 2 | `uv run rnp intersect --config <workspace>\rnp-skill-agent-run\partial.yaml --targets <workspace>\rnp-skill-agent-run\runs\partial\20261020T112231Z_75825a7c\targets.tsv` | 2 | `error: upstream ingest stage is 'partial', not 'complete'` / `- fix the upstream inputs and re-run, or pass --allow-partial to explicitly continue with an audited override`; no `intersect` dir created |
| 3 | `uv run rnp intersect --config <workspace>\rnp-skill-agent-run\partial.yaml --targets <workspace>\rnp-skill-agent-run\runs\partial\20261020T112231Z_75825a7c\targets.tsv --allow-partial` | 0 | `stage_status: partial_override`; compounds 2, linked 1, edges 1, targets 1, disease 10, intersection 1, target_only 0, disease_only 9, union 10; `compounds_without_edges: ["B"]`; warnings 1 |
| 4 | `uv run rnp report --config <workspace>\rnp-skill-agent-run\partial.yaml --run-dir <workspace>\rnp-skill-agent-run\runs\partial\20261020T112231Z_75825a7c` | 2 | `error: run contains incomplete stages; report would be summarised as partial` / `- ingest: partial` / `- intersect: partial_override` / `- fix/re-run the stages, or pass --allow-partial to render a partial report`; no report written |
| 5 | `uv run rnp report --config <workspace>\rnp-skill-agent-run\partial.yaml --run-dir <workspace>\rnp-skill-agent-run\runs\partial\20261020T112231Z_75825a7c --allow-partial` | 0 | `stage_status: partial_override`; stages ingest `partial`, intersect `partial_override`; warnings 1; `report_sha256: e1d9d4d6b76a4d55d971625ada940a6e1733dd7c4a97c11d7cfa2f8988d2fbab` |

Observations: B has no `b.csv`, so ingest is partial (exit 3) and intersect refuses by default
(exit 2). The user **pre-authorized** the `--allow-partial` validation override for this run; it was
used only for intersect and report, and both audits record it: the intersect audit has
`parents[0].status_override: true` and warning
`upstream_status_override: ingest stage_status='partial'; results are explicitly partial`. The
rendered partial report lists the override in §7 (“partial stages included by explicit override:
ingest=partial, intersect=partial_override”). No attempt was made to hide or repair the missing
export, and network/enrichment were not run for this run.

## 7. Scenario 4 — tamper (`tamper.yaml`)

Run directory: `<workspace>\rnp-skill-agent-run\runs\tamper\20261020T112249Z_e6473c0a`

| # | Exact command | Exit | Key status/audit output |
|---|---|---|---|
| 1 | `uv run rnp validate --config <workspace>\rnp-skill-agent-run\tamper.yaml` | 0 | `status: ok`; config sha `e6473c0a…`; `export_files: 2` |
| 2 | `uv run rnp ingest stp --config <workspace>\rnp-skill-agent-run\tamper.yaml` | 0 | `stage_status: complete`; 2/2 exports bound; 7 rows, 6 used, 1 below threshold; warnings 2, errors 0 |
| 3 | `uv run rnp intersect --config <workspace>\rnp-skill-agent-run\tamper.yaml --targets <workspace>\rnp-skill-agent-run\runs\tamper\20261020T112249Z_e6473c0a\targets.tsv` | 0 | `stage_status: complete`; edges 4, targets 4, disease 10, intersection 2; warnings 0 |
| 4 | `uv run rnp network --config <workspace>\rnp-skill-agent-run\tamper.yaml --intersect <workspace>\rnp-skill-agent-run\runs\tamper\20261020T112249Z_e6473c0a\intersect` | 0 | `stage_status: complete`; nodes 4, edges 4; checks passed |
| 5 | mutation, executed as `$p` = the run's `targets.tsv`: `Add-Content -LiteralPath $p -Value "" -NoNewline:$false` (one intentional newline append; Windows CRLF, +2 bytes) | 0 | before: 919 bytes, SHA-256 `94a917a5e1b8a811d7f948ac1554bc4f8aa7bec175d77c6d7767b94562cbc8f8`; after: 921 bytes, SHA-256 `7243fa84aefd2c2edfd06671f0337768ef24246386c8c9c7a6fd711b8598b83a` |
| 6 | `uv run rnp report --config <workspace>\rnp-skill-agent-run\tamper.yaml --run-dir <workspace>\rnp-skill-agent-run\runs\tamper\20261020T112249Z_e6473c0a` | 2 | `error: artifact changed since upstream stage: targets.tsv`; no `report` dir created |

Observations: the recorded hash in `stp_audit.json` was
`94a917a5e1b8a811d7f948ac1554bc4f8aa7bec175d77c6d7767b94562cbc8f8`; after the append it no longer
matches, and `rnp report` refused with exit 2, naming `targets.tsv` as the changed artifact. The
report was **not** hand-edited and the hash check was **not** weakened. Per SKILL, recovery would
be to re-run the affected stage (`ingest`/`intersect`/`network`) after fixing the input; no such
repair was performed because the purpose was the refusal.

## 8. Scenario 5 — zero (`zero.yaml`)

Run directory: `<workspace>\rnp-skill-agent-run\runs\zero\20261020T112306Z_4bba48e1`

| # | Exact command | Exit | Key status/audit output |
|---|---|---|---|
| 1 | `uv run rnp validate --config <workspace>\rnp-skill-agent-run\zero.yaml` | 0 | `status: ok`; config sha `4bba48e1…`; disease file `inputs\zero-disease.txt` |
| 2 | `uv run rnp ingest stp --config <workspace>\rnp-skill-agent-run\zero.yaml` | 0 | `stage_status: complete`; 2/2 exports bound; 7 rows, 6 used, 1 below threshold; warnings 2, errors 0 |
| 3 | `uv run rnp intersect --config <workspace>\rnp-skill-agent-run\zero.yaml --targets <workspace>\rnp-skill-agent-run\runs\zero\20261020T112306Z_4bba48e1\targets.tsv` | 0 | `stage_status: complete`; compounds 2, linked 1, edges 4, targets 4, disease 1, **intersection 0**, target_only 4, disease_only 1, union 5; exclusions `multi_symbol_common_name: 2` |
| 4 | `uv run rnp network --config <workspace>\rnp-skill-agent-run\zero.yaml --intersect <workspace>\rnp-skill-agent-run\runs\zero\20261020T112306Z_4bba48e1\intersect` | 0 | `status: empty`, `stage_status: empty`; `groups: {}`; no network tables written (only audit + manifest) |
| 5 | `uv run rnp report --config <workspace>\rnp-skill-agent-run\zero.yaml --run-dir <workspace>\rnp-skill-agent-run\runs\zero\20261020T112306Z_4bba48e1` | 0 | `status: ok`, `stage_status: empty`; stages ingest/intersect `complete`, network `empty`; warnings 0; `report_sha256: c79a6f7127bd275bb78c84e542e2c173307ba37f4a4d46f90ce3368e2566fa69` |

Observations: the disease set contains only `ICAM1`; the intersection is genuinely empty
(`intersection_genes.tsv` contains only the header; the network audit has `groups: {}`; the report
shows network “not run or produced no graph”). This is treated as a valid `empty` result with exit
0, not an error. No edges or enrichment terms were invented, and the report still lists the full
intersection counts (0 intersection, 4 target-only, 1 disease-only).

## 9. Recorded decisions reused and human questions

Reused without re-asking (recorded in the supplied configs/audit):

- Compound→export binding (`compounds.tsv` + `stp_dir`) and the fixture disease/HGNC inputs.
- `thresholds.stp_probability: 0.1` (config note explicitly says it is a fixture threshold, not a
  recommendation).
- `disease_source: fixture` and `disease_retrieval_date: 2026-10-01`.
- Project/species/reference settings and the per-scenario `outputs.dir`.
- Generic policy settings: GO BP, BH correction, `pvalue_cutoff 0.05`, `qvalue_cutoff 0.2`,
  explicit `enrichment.universe_file` (recorded but not exercised because enrichment was skipped).
- The user's pre-authorization of `--allow-partial` for the partial scenario, used and recorded as
  an audited override; not asked again.

Human questions asked: **none.** No missing/conflicting/changed scientific decision arose:

- missing: a validation failure with an exact path; SKILL says report it and stop — no question.
- partial: missing export is the designed scenario; the override was already authorized.
- tamper: SKILL prescribes identifying the changed file and re-running the affected stage — no
  scientific decision to ask about.
- zero: an empty result is explicitly valid — no question.
- enrichment: skipped for the pre-recorded Windows R reason; no enrichment claim made.

One non-scientific interface observation: `SKILL.md` shows `--run-id`, but this CLI version hides
that option from `--help` (it is accepted). This was resolved by using the explicit id after
inspecting the CLI source; it did not require a human decision.

## 10. Artifacts produced

Everything is under `<workspace>\rnp-skill-agent-run\runs\` (96 files total). No repository file was
written.

| Scenario | Run directory (relative to `runs\`) | Files | Key artifacts |
|---|---|---|---|
| normal (canonical) | `normal\normal-acceptance-20261020\` | 21 | `targets.tsv`, `compounds_registered.tsv`, `stp_audit.json`, `run_manifest.json`; `intersect\{intersect_audit.json,edges.tsv,intersection_genes.tsv,disease_genes.tsv,target_exclusions.tsv,gene_mapping_conflicts.tsv,venn.json}`; `network\all\{nodes.tsv,edges.tsv,node_attributes.tsv,mol_list.tsv}` + `network_audit.json`; `report\{report.md,report_audit.json}` |
| normal (probe) | `normal\20261020T112207Z_55597917\` | 21 | same structure; report sha `a0193f84…` |
| missing | — | 0 | no output directory created |
| partial | `partial\20261020T112231Z_75825a7c\` | 15 | `targets.tsv` (1 row), `stp_audit.json` (`partial`), `intersect\intersect_audit.json` (`partial_override`), `report\report.md` (partial, `e1d9d4d6…`) |
| tamper | `tamper\20261020T112249Z_e6473c0a\` | 18 | complete ingest/intersect/network artifacts; tampered `targets.tsv` (921 bytes); **no report dir** (refused) |
| zero | `zero\20261020T112306Z_4bba48e1\` | 17 | `intersect\intersection_genes.tsv` (header only), `network\network_audit.json` (`empty`), `report\report.md` (`c79a6f71…`) |
| registry | `{normal,partial,tamper,zero}\registry\compound_registry.tsv` | 4 | name-based compound identity registry, one per `outputs.dir` |

Recorded hashes (from CLI output/local computation, not invented):

- normal canonical `report\report.md`: `6f3b5fdbbe4ff767dd0f3f8c84066a040f7b0f58dbac09cc2bab09f8938da552`
- normal probe `report\report.md`: `a0193f84295de9ef80324241172bbc8c8e79d381555c66f8008b7b047bf6210b`
- partial `report\report.md`: `e1d9d4d6b76a4d55d971625ada940a6e1733dd7c4a97c11d7cfa2f8988d2fbab`
- zero `report\report.md`: `c79a6f7127bd275bb78c84e542e2c173307ba37f4a4d46f90ce3368e2566fa69`
- normal/zero `targets.tsv` (identical): `94a917a5e1b8a811d7f948ac1554bc4f8aa7bec175d77c6d7767b94562cbc8f8`
- tampered `targets.tsv`: `7243fa84aefd2c2edfd06671f0337768ef24246386c8c9c7a6fd711b8598b83a`

## 11. Explicit non-goals

- No `pytest`, no test imports, no test-file reading, no use of test assertions as expected values.
- No `tests/` execution; fixture data was consumed only as CLI input paths declared in the configs.
- No R execution, no `rnp enrich`, and no claim of enrichment, GO terms, q-values, or mechanism.
- No SwissTargetPrediction submission, docking, ADMET, or upstream data retrieval.
- No claim of experimental validation, direction of effect, or efficacy. The generated reports keep
  their limitation statements.

## 12. Limitations, deviations, and environment notes

1. **Enrichment was intentionally skipped** (Windows native R exit `0xC0000005`). The normal and
   zero reports therefore show `enrichment: not run`; this acceptance makes no enrichment claim.
2. **Run id**: the CLI derives `<UTC timestamp>_<config sha prefix>` by default; `--run-id` exists
   but is hidden in `--help`. The canonical normal run uses an explicit id; the first probe run with
   the automatic id is retained. The canonical re-ingest reused the per-`outputs.dir` compound
   registry, so its `compounds_registered.tsv` differs from the probe only in `identity_basis`
   (`registry_name` vs `new`) and the registry's `first_seen_utc` reflects the probe; `targets.tsv`
   is byte-identical. This is a real, documented observation about registry scope, not a hash
   mismatch: the run's own recorded hashes are internally consistent and `manifest --check-inputs`
   reported `drift: []`.
3. **Repository was dirty on arrival.** At session start `git status` showed 12 modified files
   (including `skills/np-workflow/SKILL.md`, `examples/demo/*`, `tests/unit/*`, docs) plus 2
   untracked files. During the session, additional changes appeared in the shared checkout
   (`data/SOURCES.yaml`, `docs/data-licenses.md`, `docs/public-case-sources.md`,
   `examples/demo/DATA-ACCESS.md`, `scripts/fetch_pubchem_structures.py`; timestamps 19:21:59–19:22:46
   local). Those paths are unrelated to `rnp` and no command in this session targeted them; they
   are attributed to a concurrent process sharing the workspace, not to this acceptance run. All
   outputs from this session are confined to `runs/` and this report. Consequently the manifests'
   `code.dirty: true` (and the `git status` drift) must not be read as this session's edits.
4. **`manifest --check-inputs` scope**: on the normal run it checked 4 inputs (config, compounds
   TSV, two STP exports) and reported no drift. It did not check `targets.tsv` or the compound
   registry; the tamper was caught by `rnp report`, which verifies stage artifact hashes. This is
   consistent with the SKILL's guidance to use report hash verification for artifacts.
5. **Tamper append form**: PowerShell `Add-Content` appended a Windows CRLF (+2 bytes), not a bare
   LF; this is still “append a newline” on this platform and changed the SHA-256 exactly as shown.
6. **No scientific interpretation**: all counts come from the audit JSON of synthetic fixtures.
   The fixture probability threshold (0.1) is explicitly not a recommendation, and this acceptance
   says nothing about any real compound–target–disease relationship.

## 13. Real-agent session statement

I, the agent, read `skills/np-workflow/SKILL.md` and `rnp-skill-agent-run/README.md`, inspected the
five YAML configs, ran the existing `rnp` CLI through `uv run` in the repository checkout, captured
every exit code and audit output, and wrote only under `<workspace>\rnp-skill-agent-run\runs` plus this
report. I did not read or run anything under `tests/` (beyond fixture data implicitly consumed by
the CLI), did not run `pytest`, and did not modify the repository working tree. This report is a
factual record of that real session.
