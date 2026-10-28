# Final Skill real-agent acceptance — 2026-10-21

> 公开整理说明（2026-10-28）：原始本机路径已统一替换为 `<workspace>`；模型、commit、版本、命令、退出码和失败限制保留未变。

This is a real Codex session record, not pytest and not a DSH-subagent substitute. It validates the
installed final `skills/np-workflow/SKILL.md` at clean commit **e81f5bf**. Session logs are local
(`<workspace>/rnp-skill-logs/`); no restricted data is included.

## Runtime and installation

| Item | Value |
|---|---|
| Agent runtime | Codex CLI `0.147.0` (real `codex exec` sessions) |
| Model | `gpt-5.6-sol` |
| Host | Windows, checkout copy of clean clone e81f5bf |
| Skill install | copied to `%USERPROFILE%\.codex\skills\np-workflow\SKILL.md` |
| Skill SHA-256 at session | `f2002b726198d7d409d9e3efb43935e21bcf1805f2a2313d21719f91ac428147` |
| Current boundary-only Skill SHA-256 | `2934f2e5cdbd2291a381f82b84657b02be98ed80d60106c2a56aafb752b93b78` |
| Discovery | Codex listed `np-workflow`; each session read `SKILL.md` before actions |
| Trigger | normal/zero/partial/tamper/missing sessions invoked the workflow instructions |
| Fixed commit/worktree | `e81f5bf`, worktree clean before acceptance; only generated `_out/` ignored artifacts changed |

**2026-10-22 addendum.** A policy-only boundary was added to `SKILL.md` (third-party/Agent batch STP
submission must not create official case inputs; external runs are separate snapshots). This changes
the text hash but not any analysis/CLI behavior. None of the accepted scenarios invokes that batch
path, so no scenario was re-run; the installed skill was synced to the new hash. If the behavior
changes in future, affected scenarios must be re-run rather than relying on this record.

## Scenario results

| Scenario | Observed behavior | Verdict |
|---|---|---|
| normal | `validate`, `ingest`, `intersect`, `network`, `report` all exit 0; ingest complete 2/2 bound; intersection 2; network 4 nodes/4 edges; report complete 3 stages/8 artifacts | pass |
| missing input | actual `rnp validate` exit **2**; missing path named `...\inputs\missing_disease.txt`; no file created or repaired | pass |
| partial upstream | ingest exit **3**, audit `partial`, 1/2 bound, missing `compound_b.csv`; intersect without override exit **2** and no output; with my explicit approval `--allow-partial` exit 0, audit `partial_override` with override recorded | pass, override explicit |
| tamper | appended to `targets.tsv`; `report` exit **2**, error `artifact changed since upstream stage: targets.tsv`; no new report dir | pass |
| zero result | ingest complete; intersect complete; network/report `empty`; 0 intersection, no invented edges/terms; raw target/disease counts retained | pass |
| Linux enrichment/report | Codex session invoked the Linux Docker pipeline (`bioconductor/bioconductor_docker:RELEASE_3_22`, R 4.5.2); Docker exit **0**; enrich complete, effective foreground/background **2/30**, 558 terms, 0 significant; report complete; `manifest --check-inputs` 4 inputs, no drift | pass with environment note |

## Caveats recorded honestly

1. **Codex shell wrapper exit display.** The first missing-input session displayed `1` because
   Codex's PowerShell wrapper did not preserve the native exit. A retry ran the same command through
   `cmd.exe` and captured the actual **2**; the CLI behavior was correct. This is a runner/shell
   observation, not a Skill failure.
2. **Linux host.** Codex itself ran on Windows and invoked a Linux Docker container for the R
   enrichment/report. The actual computation was Linux; this is not a Codex process running inside
   Linux. A Codex-in-Linux session was attempted but the container's npm/apt install was blocked by
   package-network 502s, so it is not claimed. The Codex Linux session's Docker command completed
   with exit 0, but its PowerShell wrapper also exited 1 before writing the exit file (a non-fatal
   debconf/stderr handling issue); a direct rerun of the same wrapper wrote `0`. The Linux results
   themselves were complete and consistent on both runs.
3. **R bootstrap in partial/zero sessions.** The agent reported an R bootstrap quoting failure on
   Windows; those scenarios do not invoke R. The Linux enrichment session used the restored `/rlib`.
4. **Report hash stability.** Report hashes vary with run path/time. Sets/counts are the acceptance
   invariant; a rerun's report hash is not expected to equal an earlier run byte-for-byte.
5. Only one model/session family is represented; this is not a general claim about all agents.

## Not a pytest substitute

`tests/unit/test_skill.py` and `tests/skill/test_skill_scenarios.py` remain deterministic regression
coverage. The session above is separate evidence from Codex's actual tool calls. The final public
case gate remains blocked pending CTD/STP permission.

**Status update (2026-10-28):** the preceding sentence records the 2026-10-21 state. CTD ticket
#8545 and STP's 2026-10-23 reply now confirm the requested public non-profit scope; PubChem
source/terms review is complete with a residual caveat. The case candidate is reproduced, but
publication still awaits the researcher's final decision. The original Skill session result is
unchanged and remains valid.
