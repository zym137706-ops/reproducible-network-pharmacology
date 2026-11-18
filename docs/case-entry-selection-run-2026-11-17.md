# Case entry with a selection, run on the RA case package — 2026-11-17

Fixed implementation commit: `b13ca0cf5fe06bdd93d4c23cefaf56b54c518f3d` (`b13ca0c`), the last of the three
commits that add `--selection` to `scripts/case_run.py` and the selection recheck to `scripts/case_check.py`
(on `origin/main`, after v0.1.0; part of the v0.2.0 release candidate).
The run was made from the repository working tree at that commit (`git status` clean; `case_provenance.json`
records `dirty: false`), not from a fresh clone. Every output went to a directory outside the repository.
Inputs: the `rnp-case-v0.1.0-2026-10-21` case package, extracted outside the repository. The ZIP is the one
published as the v0.1.0 release asset (938,555 bytes, SHA-256
`55b65aefe8ff97c08d12b16945db9313931aa65aea947c96bfdf2aab5fe927e4`, equal to `release-notes-v0.1.0.md`); its 35
payload files match `SHA256SUMS.tsv` (size and SHA-256) and no unlisted file is present. The entry only reads the
package; no restricted file entered the repository.

This is a local technical record of code in the v0.2.0 release candidate. The final reproduction of the published
v0.1.0 remains `docs/public-candidate-reproduction-2026-10-28.md`.

## What this run exercises

Three real runs of `scripts/case_run.py` on the case package, with `--log` (structure mode: `rnp ingest compounds`
checks the eight submitted structures with RDKit) and the same configuration template for the two thresholds:

| Chain | Options | Decision table |
|---|---|---|
| `plain` | `--log` | none (the baseline of the same commit) |
| `all` | `--log --selection` | all eight compounds `include` |
| `mixed` | `--log --selection` | six `include`, two `exclude` |

The decision tables are **verification inputs, not scientific selections.** They exist to exercise the code. In
`mixed` the two excluded compounds (Kaempferol, Naringenin) were picked arbitrarily; the reason codes
`out_of_scope` and `no_standard` are labels with no meaning for those compounds; rules version `RA-check-v1`,
reviewer `verification`. Nothing here says anything about the compounds or about their relevance.

```text
compound          decision  reason_codes
Quercetin         include
Kaempferol        exclude   out_of_scope;no_standard
Luteolin          include
Apigenin          include
Naringenin        exclude   no_standard
Catechin          include
Gallic acid       include
Chlorogenic acid  include
```

Five refusals were run on the same inputs as well, with `--preflight-only`: a compound without a decision, a
decision `needs_review`, a table that selects nobody, a decision for a compound that is not in the compound table,
and `--selection` without `--log`. Each stopped before anything was written, named the problem, and left no
output directory.

## Environment / provenance

| Item | Value |
|---|---|
| Host | Windows 11 Home China 10.0.26200, local workstation; **not** the container of the v0.1.0 reproduction (the image fields of the provenance are empty) |
| Python | 3.12.5, the repository's own virtual environment (with the `chem` extra) |
| RDKit | 2026.09.1 (extra `chem`; the version the compounds stage recorded) |
| R | 4.5.2, default user library; **not** the renv-restored library |
| R packages | `clusterProfiler` **4.18.2** installed against 4.18.4 in `renv.lock` (as in the 2026-11-13 record) |
| Source hash (`case-source-hash-v2`, combined, 62 files) | `80878ae6db03fb4cd031c68be0a4ae6092c0b9a61205ab0185115f3473ad9d13` |
| Manifest commit / dirty | `b13ca0c` / `false` |
| `case_provenance.json` | status `complete` for all three chains; `inputs.log.policy` `case-log-policy-v2`; for `mixed` also `inputs.selection.policy` `case-selection-policy-v1`, 24 commands recorded |

## Results

The counts are those of `independent-check.json` of each chain.

| Item | `plain` / `all` 0.10 | `plain` / `all` 0.05 | `mixed` 0.10 | `mixed` 0.05 |
|---|---:|---:|---:|---:|
| `T_r` | 239 | 267 | 214 | 243 |
| Foreground / intersection | 15 / 15 | 17 / 17 | 14 / 14 | 16 / 16 |
| Network nodes/edges | 23/67 | 26/74 | 20/51 | 23/58 |
| Effective foreground/background | 15/234 | 17/262 | 14/210 | 16/239 |
| GO terms tested | 704 | 747 | 667 | 711 |
| Significant | 0 | 2 | 0 | 0 |

- `plain` and `all`: both thresholds `complete`; the independent check's counts equal the frozen
  `expected/EXPECTED.json`.
- `all` against `plain`: every non-JSON result file under `<threshold>/run` and `backgrounds/` is byte-identical
  (`compounds_registered.tsv` apart from its new last column `selection_status`, and the report apart from the new
  selection line, which says 8 selected, 0 excluded, 0 needs review or quarantined).
- `mixed` counts are lower because the targets of the two excluded compounds are no longer counted. They show
  that exclusion works as designed and are not a result of the study.

## Selection checks (`mixed`)

- Both thresholds register 6 selected and 2 excluded compounds; `targets.tsv` has no row of an excluded compound;
  `stp_audit.json` is schema 1.2 with two files `not_selected` and none quarantined; the targets table is smaller
  than `plain`'s.
- `independent-check.json` has a `selection` record from the independent re-derivation: rule
  `case-selection-recheck-v1`, 8 rows, 6 selected and 2 excluded, decision table SHA-256 `5883066e…` (equal to the
  hash in `case_provenance.json`), and the selection stage hashes of both thresholds.
- `case_provenance.json` records `inputs.selection` (policy, rows, counts, hash, `verified_by`), the selection
  stage of each threshold and the recheck result `passed`; the `plain` provenance has none of those keys.
- `rnp manifest --check-inputs` is clean on every stage directory (`run`, `run_compounds` and `run_selection` of
  both thresholds).
- Differential check: the `check_selection` of the repository and a second implementation written independently
  (kept outside the repository) give the same record on the real outputs, and on six deliberate tamperings of the
  real outputs (a changed reviewer cell in the selection table, a target row of an excluded compound, a reason
  code of the decision table edited after the run, a registered status changed from excluded to selected, a changed
  compound count in the intersection audit, an extra decision row for an unknown compound) both object, with the
  same lines.

## Limits of this record

- One Windows workstation, the user's R library, one commit; not a clean clone and not the container of the v0.1.0
  reproduction. Linux with the locked R library is the verified case platform; this run is a record, not a
  support claim for Windows.
- The package is the published v0.1.0 case package; the case package was not re-frozen and its records are
  unchanged.
- The predicted associations are annotation overlap, not validation. "Selected" only means kept by the recorded
  decision.
