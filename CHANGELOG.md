# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

### v0.1.0 release candidate — 2026-10-28

- Raised the software version to **0.1.0** (`pyproject.toml`, `uv.lock`, `src/rnp/__init__.py`,
  `CITATION.cff`) while keeping the release explicitly **unreleased**; no date-released, DOI, tag or
  release was invented.
- Corrected `CITATION.cff`: removed the unimplemented module-analysis claim, described only current
  CLI/report/provenance capabilities, and added software-separated upstream references (STP, CTD,
  HGNC, PubChem). Added `docs/citations.md` as the direct citation sheet.
- Corrected the publication-status text across README/README.zh-CN, case README, CASE-FREEZE,
  skill-acceptance (dated status note, original session result preserved) and the candidate
  permission summaries. Permission review, publication decision and actual release are now separate.
- Added optional provenance fields for image platform, platform-manifest digest and config digest;
  `case_provenance.json` and `run_manifest.json` now carry the host-observed values rather than
  conflating an index digest with a config digest.
- Prepared the final case package layout: 35 payload files + `SHA256SUMS.tsv` (36 total), renamed
  `PUBCHEM-SOURCE.md`, added `ATTRIBUTION.md`, and documented the versioned release-asset zip,
  verification counts, two-directory execution and exact checksum commands.
- Rebuilt wheel/sdist and installed the wheel into a fresh virtual environment; `rnp --version`
  reports `0.1.0`, and packaged `schemas/` and `R/` resources are present.
- No repository visibility, tag/release, real-data upload, email or CTD notification was performed.

### Candidate README, image provenance and PubChem review — 2026-10-27

- Replaced the candidate README's mixed-directory command with an explicit two-directory workflow:
  run from the repository clone and point `--compounds/--stp-dir/...` and
  `--config-template` at `$CANDIDATE`; verified the command from the repo against the candidate.
- Re-ran the candidate in Linux with explicit `RNP_CONTAINER_IMAGE*` values. New
  `case_provenance.json` records image tag/ID/digest (not null); the earlier image-null run is kept
  historical and was not backfilled.
- Completed PubChem source/field/terms/citation review for the eight CIDs: PUG REST
  `SMILES`/`ConnectivitySMILES` are computed descriptors; per-record OEChem/PubChem releases and
  raw-response hashes are recorded. NCBI states no restrictions by NCBI but submitters may retain
  rights; no CC license is asserted. Added per-CID provenance table and updated candidate/docs;
  publication remains a researcher decision.
- Candidate now has 34 files and refreshed `SHA256SUMS.tsv`; no private/local paths in candidate
  configs/docs, no EML/screenshot/private correspondence included.
- No tag/release/visibility change.

### CTD public non-profit permission and complete candidate — 2026-10-27

- Recorded CTD ticket **#8545** (2026-10-26): public non-profit research including GitHub is permitted
  for the requested 179-gene RA subset/derived outputs, with CTD citation and a data date-stamp;
  commercial use remains separate. Original EML archived locally (`d63991ff…`); full headers parsed,
  no independent cryptographic signature verification claimed; private EML/screenshot not committed.
- Updated source records, CASE-FREEZE, README, handoff/checklist/plan: CTD permission confirmed;
  publication decision and candidate review pending; PubChem structure terms still separately pending.
- Prepared a 33-file complete review candidate outside Git with relative-path configs, STP XLSX,
  actual submitted structures, de-identified log, CTD genes/evidence/query, HGNC, both universes and
  foregrounds, permission/citation files, expected counts and `SHA256SUMS.tsv`.
- Reproduced the candidate from clean commit `90f3178` in Linux: both thresholds complete, checker
  passed, supplied universe hashes matched, manifest no drift; counts match frozen expectations.
- No real data/private correspondence uploaded; no tag/release/visibility change.

### STP original EML archive and submission-date clarification — 2026-10-26

- Archived the original 2026-10-23 SwissDrugDesign reply EML outside Git in the local evidence
  directory; SHA-256 `4085f48a…`; original bytes preserved and removed from the candidate package.
- Parsed full headers: Date `Fri, 23 Oct 2026 11:40:44 +0200` (`2026-10-23T17:40:44+08:00`). The
  receiver headers report SPF pass / DKIM permerror / DMARC none; no independent cryptographic
  signature verification is claimed.
- Recorded the researcher's 2026-10-26 confirmation that the CTD and STP Contact requests were sent
  on the same day. No CTD submission screenshot exists; exact calendar date/time remains unverified.
  The EML Date is the reply date and the quoted 2026-10-21 is prediction generation, not Contact
  submission.
- Updated the de-identified permission summary and CASE-FREEZE evidence/submission-relation fields.
  CTD still awaits a reply; no redistribution permission is inferred from the EML metadata.
- The EML, headers, screenshot and private correspondence remain local-only; no Git/CI/release
  upload, no tag/release/visibility change.

### STP permission confirmation and local release candidate — 2026-10-26

- Recorded the 2026-10-23 SwissDrugDesign reply: the eight native XLSX tables are **CC BY 4.0**;
  attribution is required; the original tables must not be modified; derived analyses are permitted.
  Required citation includes the SwissTargetPrediction website, prediction date 2026-10-21 and
  Daina & Zoete, *Communications Chemistry* 7, 105 (2024).
- Archived the reply screenshot in the local ignored evidence directory (`2880a092…`); `.eml`/full
  headers were not supplied, so signature/header authenticity is not claimed. The screenshot/private
  correspondence is not committed.
- Added a de-identified permission summary, a byte-identical local STP candidate package with per-file
  SHA-256/`FILES.tsv`/README/ATTRIBUTION/DATA-LICENSE, and a release-candidate checklist. The
  candidate is outside Git and not published.
- Updated LICENSE/source records, CASE-FREEZE, HANDOFF, case README, public checklist/sources, README
  and plan: STP tables confirmed; CTD remains pending; the overall public case stays blocked.
- Added an unsent CTD follow-up draft outside Git (suggested 2026-10-28–30).
- No real XLSX, CTD data, private log or full correspondence was uploaded/committed; no tag, release or
  visibility change.

### v0.1 case-entry hardening — 2026-10-22

- `case_run.py` now strictly binds every submission-log row to `stp_file`, rejects duplicate/missing/
  unbound rows, checks CID/submission_id/species/hash, and compares `submitted_structure` to the
  compound's exact stripped SMILES before analysis. A missing/blank compound structure or log column
  fails with the file/entry/field; optional-log behavior remains.
- Source hashing is versioned as `case-source-hash-v2`: it covers `src/rnp`, `R`, `schemas`, the three
  case entrypoint scripts and `uv.lock`/`renv.lock`, excludes caches/venv/build/results/data, records
  core/entrypoint/lock/combined hashes separately, and is explicitly not a full repository/package
  hash. Missing caches no longer change the hash; controlled source edits do.
- The formal `case_run.py` entry now invokes `case_check.py` after both manifest checks. Overall
  `complete` requires analysis + manifests + independent check; child/checker failure exits non-zero
  and persists `status=failed`, `failed_stage`, `failed_command`, `child_exit_code` and prior commands.
- Linux CI R job now runs the synthetic case entry end-to-end (both thresholds + checker with expected
  counts) and a wrong-structure rejection path. Docs, schema, Skill boundary and tests updated.

### v0.1 portable case entry, provenance and final acceptance — 2026-10-21

- Fixed case-record consistency: actual `.xlsx` bindings, actual local submitted-structure evidence,
  no stale "missing disease/STP/background" text; split local-complete vs public-release-blocked
  status and replaced the fixed `blocked` assertion with evidence-based status checks.
- Added `scripts/case_run.py` (portable preflight, fixed 0.10/0.05 configs, full CLI chain, no
  overwrite, no downloads/submissions) and `scripts/case_check.py` (independent T_r/foreground and
  hypergeometric/BH checks). Added `docs/case-run.md`, schemas and tests.
- Added optional manifest `code.source_attestation` and `container` provenance plus a case
  `case_provenance.json` schema; source/container values are explicitly host-declared, never
  fabricated. Avoided backfilling old manifests.
- Clean-clone `e81f5bf` Linux run: source hash `f271…`, image digest `sha256:e341…`,
  R 4.5.2/clusterProfiler 4.18.4, both thresholds complete, manifest 10 inputs no drift, independent
  check passed; synthetic quickstart also complete.
- Final-revision Codex real-agent acceptance: normal/missing/partial/tamper/zero plus Linux
  enrichment/report via Docker; Skill hash `f2002b72…`. One PowerShell wrapper exit-display caveat
  and the fact that Codex ran on the host are recorded; no Codex-in-Linux claim.
- Public CTD/STP redistribution remains permission-pending; local inputs/results not committed or
  uploaded. No tag/release/visibility change.

### v0.1 RA case local Linux calculation — 2026-10-21

- Verified the Codex handoff: 8 XLSX files match `file-checks.json` (size/SHA-256), 8/8 explicit
  `stp_file` bindings match `compounds.tsv`, log hashes match; 800 rows, 0 invalid, 676 rows at 0.10
  and 740 at 0.05. Original XLSX files were not renamed or modified.
- Received local materials are not committed/uploaded: CTD disease extract, STP XLSX, submission log
  and result tables remain in `data/local`/the external handoff directory; CTD/STP redistribution
  permission is still unconfirmed.
- Generated and froze local conditional backgrounds by the approved rule: 0.10 T_r=239,
  foreground=15; 0.05 T_r=267, foreground=17 (multi/composite excluded, no mapping loss).
- Ran the full chain in Linux Docker (`bioconductor/bioconductor_docker:RELEASE_3_22`, R 4.5.2,
  clusterProfiler 4.18.4, DOSE 4.4.0): both thresholds complete; `manifest --check-inputs` 10 inputs,
  no drift.
  - 0.10: intersection 15, network 23 nodes/67 edges, effective background 234, 704 terms,
    0 significant (`completed_no_significant_terms`).
  - 0.05: intersection 17, network 26 nodes/74 edges, effective background 262, 747 terms,
    2 significant GO BP terms at p.adjust 0.0481979 (conditional within predicted targets).
- Independent check recomputed hypergeometric p-values and BH for all 704/747 result rows and
  rederived T_r/foreground from targets + HGNC + CTD genes; passed. Results remain local-only.
- Updated CASE-FREEZE to record `case_computed_in_linux: true`, local run paths/counts and
  `public_release_status: blocked`; no repository visibility/tag/release change.

### v0.1 case decisions: RA disease, background rule and STP pending list — 2026-10-21

- Applied the researcher's disease decision: **Arthritis, Rheumatoid**, exact MeSH `D001172`, no
  child expansion; CTD `genes_curated` query with `marker/mechanism` or `therapeutic` direct evidence,
  inferred-only excluded. Local extract: 179 unique genes, 179 rows; query/release/date/rules/evidence
  counts and hashes recorded in `examples/demo/inputs/CTD-QUERY.md`. CTD redistribution is not
  confirmed, so the disease data remains local-only and the case stays blocked.
- Applied the pre-declared conditional background rule: for each threshold r, T_r = HGNC-normalised
  unique targets before disease; background=T_r, foreground=T_r∩D; 0.10 and 0.05 generated
  separately. Added `scripts/build_case_background.py`, `run-0.05.yaml`, `BACKGROUND-RULE.md`, and a
  rule/foreground regression test. Actual universes remain blocked until STP exports exist.
- Added `STP-PENDING-SUBMISSIONS.tsv` (CID, species, expected filename, log row) and a local
  version with the actual PubChem SMILES; no STP submission is automated. The submission log remains
  outside the export scan directory.
- Fixed `test_case_freeze.py`: CSV/XLSX exports are now allowed in `inputs/stp/`, while the log is
  still checked not to be mixed into that directory; when exports exist, they must match the explicit
  bindings and the completed log evidence.
- Updated README/plan/HANDOFF/freeze checklist for HGNC frozen, RA decision, background rule and the
  remaining permission/STP gaps.

### v0.1 case data preparation fixes — 2026-10-20

- Fixed `scripts/fetch_pubchem_structures.py`: the current PUG REST endpoint returns `SMILES`
  (stereochemistry included where defined) and `ConnectivitySMILES` (connectivity only), not the old
  `CanonicalSMILES`/`IsomericSMILES` names. The parser now checks the returned CID, requires both
  structure fields non-empty, records field meanings/raw-response hashes/retrieval time, writes
  atomically, and fails instead of producing an empty-structure success table.
- Re-fetched the 8 local structures; new local table SHA-256
  `c43811542fe1ef1856c8e9aefd2c1805e400d0c87d6093117565c04e9ebc6d02`, 8/8 non-empty SMILES.
  Local-only (`data/local/`), not committed.
- Moved the STP submission log out of the export scan directory:
  `examples/demo/inputs/STP-SUBMISSION-LOG.tsv` (was inside `inputs/stp/`, where ingest would
  quarantine it as an unbound export). Updated the template references, HANDOFF, freeze and tests;
  the unbound-export isolation rule is unchanged.
- Corrected the Skill zero-result guidance: only intersection/network are zero; raw target, disease
  gene, linkage and mapping-loss counts keep their audited values.
- Added PubChem field/CID/empty-response regressions and a local metadata-vs-freeze consistency test.
- Frozen the HGNC normalisation input: downloaded the 2026-10-16 complete-set snapshot under CC0,
  derived a 45,277-row Approved `hgnc_map.tsv`, committed it with raw/derived SHA-256, snapshot date,
  source URL and attribution (`examples/demo/inputs/HGNC-SOURCE.md`); updated the `run.yaml`
  reference to the actual snapshot date and removed HGNC from the missing-input list.

### v0.1 restore entry, case handoff and real-agent Skill acceptance — 2026-10-20

- Fixed `scripts/restore_r.ps1`: every Rscript call now checks `$LASTEXITCODE`; bootstrap or restore
  failure stops with a non-zero status and no success hint. Both entry points resolve the **actual
  absolute library path** (explicit path absolutized; default path resolved by renv, never guessed)
  and print the exact `R_LIBS`/`RNP_RSCRIPT` to use.
- `scripts/restore_r.sh` is now executable in Git (100755); CI calls the project restore script
  instead of an inline `renv::restore`, checks the printed absolute path, and verifies that a
  Python-launched `Rscript` sees the restored library through `R_LIBS`.
- Added restore-script regressions for bootstrap failure, restore failure, explicit path and
  default path, using temporary substitute processes (no real R download).
- Case preparation: compounds now carry explicit `stp_file`/`submission_id` bindings; added the
  `SUBMISSION-LOG.tsv` template, a compact `HANDOFF.md`, and a reproducible local PubChem fetch
  script. The PubChem structures were fetched locally (8 rows, SHA-256 recorded) into the ignored
  `data/local/` only; disease/HGNC/universe/STP inputs and licence evidence remain missing. The
  case stays `blocked`; no source, date, structure or STP export was fabricated.
- Skill: instructions now reuse recorded/applicable decisions and ask only for missing, conflicting
  or changed decisions; the 8 compounds/CTD/0.10 thresholds are explicitly case configuration, not
  generic defaults. A **real-agent session** (DeepSeek Harness/`deepseek-flash`, Windows, commit
  `49f0996` + dirty worktree) executed normal/missing/partial/tamper/zero: 5/5 passed, enrichment
  skipped due the Windows R `0xC0000005`, no pytest used. Full report:
  `docs/skill-agent-acceptance-2026-10-20.md`.
- Linux CI run 39415883483: 4/4 jobs success; the R job called `scripts/restore_r.sh`, checked the
  absolute `R_LIBS` path, verified a Python-launched `Rscript` saw that library, and ran the full
  synthetic chain.

### v0.1 case freeze and Skill acceptance — 2026-10-20

- Environment status corrected: Linux CI (run 39393951056) restores `renv.lock` and passes the full
  synthetic chain; an independent Codex run on Windows reproduced R exit `0xC0000005`
  (3221225477) with a normal-looking meta and 11 failing R tests. Windows remains unverified; the
  non-zero exit guard is kept and no failures are hidden.
- Added explicit R bootstrap/restore/library scripts (`scripts/restore_r.sh`,
  `scripts/restore_r.ps1`) and documented library selection (`R_LIBS`, `renv::restore`) and system
  dependencies.
- Public case frozen as **BLOCKED** in `examples/demo/CASE-FREEZE.yaml`: recorded decisions
  (8 PubChem CIDs, 0.10/0.05 thresholds, GO BP/BH, manual STP) are reused; disease genes, eight
  manual STP exports, HGNC snapshot and licence evidence are listed as missing. No source, hash or
  scientific result was invented, and no STP submission was automated.
- Thin Skill behavior acceptance: `tests/skill/test_skill_scenarios.py` exercises normal, missing
  input, partial upstream, hash tampering and zero-result flows through the existing CLI; the Skill
  records the scientific decisions and failure handling. Not yet a real-agent validation claim.
- CI R job continues to restore the lock; Linux remains the verified case environment.

### Release hardening, R lock and clean-environment verification — 2026-10-20

- Wrapper layer: every non-zero `Rscript` status is now authoritative. Exit code 2 remains an
  input/background error; any other non-zero status (crash, kill, wrapper failure) raises an
  external-tool failure even when `enrichment_meta.json` says `ok`. Exit 0 without a meta file is
  rejected too. Added simulated regressions for rc=1/137 with a normal-looking meta and for the
  no-meta case.
- Enrichment engine sets: R now writes `effective_foreground.tsv` and `effective_background.tsv`
  (actual Entrez sets passed to the engine), records their counts/hashes in the audit, and uses
  them for ORA. Added a distinct `no_ontology_annotation` status for "mapping succeeded but no
  selected-ontology annotation" (e.g. XIST/H19 with GO BP); this is not reported as a mapping
  failure or a generic analysis failure. Report verifies the new files and shows effective counts.
- Clean R environment: a fresh isolated library was installed from CRAN + Bioconductor 3.22 with
  `pak` (clusterProfiler 4.18.4, DOSE 4.4.0, org.Hs.eg.db 3.22.0) and passed 25 R-dependent tests
  (bridge, synthetic hypergeometric/BH benchmark, enrichment, report). `renv.lock` (121 packages,
  R 4.5.2) was generated from that verified library, not from the host library.
- Clean project restore: a copy of the working tree with no `.venv`/results was installed with
  `uv sync --locked --extra dev`; the full suite passed 130 tests, including the hypergeometric/BH
  benchmark and the enrich→report chain. A separate clean-project quickstart with the isolated R
  library completed ingest→intersect→network→enrich→report→manifest with all stages `complete`.
- CI R job now restores `renv.lock` (`renv::restore`) and exposes it through `R_LIBS` instead of
  installing unpinned Bioconductor packages.
- Added a thin CLI-only Skill draft (`skills/np-workflow/SKILL.md`) with static tests, plus
  `docs/public-case-sources.md` (candidate data sources and license checks, no dataset committed).
  The Skill is **not** claimed validated, and no public case exists yet.

### Release hardening — 2026-10-19

- Compound identity: explicit IDs are reserved before automatic allocation, new explicit IDs are
  persisted to the registry, and reusing a registered ID for a different name/group is now a hard
  error instead of a note. Regression tests cover explicit/auto collision, persistence and conflict.
- Report: verifies every artifact it reads (targets, compounds, edges, intersection, disease,
  exclusions, conflicts, Venn data, enrichment result/meta/significant views, universe) and checks
  each stage's parent-audit hash/status/directory link. `report_audit.json` now lists verified
  artifacts; missing hashes are errors, not silent skips.
- Enrichment: `universe` now separates mapping input/mapped/unmapped from the **statistical
  background** actually passed to the engine; a full mapping failure records every input symbol as
  unmapped and `statistical: null`; foreground full failure likewise counts all genes as unmapped.
  The R bridge passes the statistical background to clusterProfiler and records it.
- Quickstart: one config `examples/quickstart/run.yaml` is used by both README and CI; the README
  paths (`results/quickstart/...`) are now real. Makefile installs with `uv sync --locked`.
- CI: installs from `uv.lock` via `uv sync --locked --extra dev`; the smoke job runs the same
  quickstart config, and the R job runs the full quickstart including enrichment and report.
- Added `docs/environment.md` recording the actual Windows/R/DOSE environment, the R exit-status
  behavior (DOSE stderr is not a failure), and CI versions; added R exit-status regression tests.
- Stale docs cleaned: public-case/demo notices, next-steps task marked historical, enrichment
  acceptance updated (mapped vs statistical background, CI evidence).

### Report command — 2026-10-19

- Added `rnp report`: renders Markdown from a run directory's audited stages after verifying the
  recorded hashes (targets, compounds, edges, intersection, disease, universe) and the config
  identity of every stage.
- Missing stages are rendered as "not run"; partial stages are refused by default and only included
  with `--allow-partial`, with the override recorded in the report and the manifest.
- Added `report.schema.json` and `report_audit.json` (stage statuses, audit hashes, report SHA-256),
  plus a per-report manifest chaining the stage audits.
- The report contains only evidence-bound numbers: per-group intersection/network counts, exclusion
  and mapping-conflict counts, enrichment mapping loss and top filtered terms, provenance and
  explicit limitations. It does not claim mechanism, direction, or efficacy.
- Added 9 report tests (ingest-only, full chain, enrichment, tampered hash, overwrite, partial
  override, zero result, CLI) and added report rendering to the CI smoke test.

### Enrichment CLI — 2026-10-19

- Added `rnp enrich`: per-group ORA through the R `clusterProfiler` bridge with an explicit
  background (`enrichment.universe_file`, required). An unmappable explicit background is a hard
  error and is never replaced by the default annotated genome.
- The complete tested-term table is always written (`enrichment_result.tsv`), plus a filtered
  `enrichment_significant.tsv`. "Completed with no significant term" is a distinct status from a
  failed R analysis and from an unmapped foreground.
- Added `enrichment.schema.json` (stage audit) and recorded per-group mapping loss, tested-term
  counts, result/meta hashes, R exit code and package versions.
- R bridge now computes the complete table with `pvalueCutoff = qvalueCutoff = 1`, reports the
  requested cutoffs and the explicit background counts, and supports frozen
  `synthetic_gene_sets` for an independent hypergeometric/BH benchmark.
- Added tests: background required, zero-foreground empty result, missing Rscript, overwrite guard,
  live GO contract, CLI, and a combinatorial hypergeometric/BH benchmark that computes expected
  values independently in Python.
- Updated README (quickstart, command table), architecture, enrichment acceptance notes and CI
  R job to include the new stage.
- CI: [run 39247312505](https://github.com/zym137706-ops/reproducible-network-pharmacology/actions/runs/39247312505)
  completed green for all four jobs (Python 3.10/3.11/3.12 lint+tests+demo+wheel, R 4.5 bridge tests).

### Hardening — 2026-10-19 (v0.1 slice)

- Ingest now requires an explicit compound↔export binding (`stp_file`) unless
  `inputs.allow_filename_match: true` is set as a recorded compatibility mode. Unbound exports are
  quarantined in `stp_audit.json` and never enter `targets.tsv`.
- File status is a taxonomy, not a boolean: `ok`, `partial`, `below_threshold`, `invalid_rows`,
  `no_predictions`, `error`, `quarantined`. `rows_invalid` is counted separately from
  `rows_below_threshold`; `rows_valid` and `rows_below_threshold` are both reported. Missing required
  columns raise a consistent error.
- Run-level `stage_status` (`complete` / `partial` / `failed`) is written to the audit; failed runs
  leave no output directory, partial runs exit 3.
- `rnp intersect` and `rnp network` verify the parent audit, stage status, parent hashes and config
  identity, and refuse incomplete upstream stages unless `--allow-partial` is passed; the override is
  recorded in the audit and manifest.
- Output directories are written through a temporary sibling and atomically moved; existing outputs
  are refused unless `--force` is passed.
- Stable compound identity: a persistent registry (`results/registry/compound_registry.tsv` by
  default, or `inputs.compound_registry`) assigns/reuses `compound_id`; explicit IDs, case-insensitive
  matches and renames matched by `stp_file` are recorded as such. This is a name-based migration, not
  a chemical-structure registration (v0.2).
- Manifest schema 2.0 separates **code identity** (package version/commit/root) from **config
  identity** (path, SHA-256, config-repository state), records parent-stage audit hashes and the
  stage status, and records whether an output was overwritten.
- Zero-intersection runs now produce a valid **empty** network audit and no fabricated group
  directory.
- Added `scripts/synthetic_demo.py`: one command runs five synthetic scenarios (normal, extra export,
  zero intersection, ambiguous mapping, partial upstream) and compares results with hand-computed
  expectations.
- Packaged `R/` scripts into the wheel and added `rnp.resources` so the Venn script is locatable after
  installation.
- 28 new/changed tests (88 total in this environment); schemas updated to `stp_audit` 1.1,
  `intersection` 1.1, `network` 1.1, `run_manifest` 2.0.
- Added `docs/public-case-checklist.md` and `docs/enrich-acceptance.md`; synchronized README,
  architecture and this changelog with implemented vs pending status.
- Still pending: enrichment CLI, report, Skill layer, public scientific case, generated Python lock
  and recorded CI/wheel-install evidence.

### Documentation / design — 2026-10-19

- Added the maintained Chinese v3 plan, upstream identity/selection contract, candidate-pair/docking
  contract and a bounded DSH implementation handoff.
- ADR 0004 stages the v0.1 core, v0.2 upstream and v0.3 minimal calibrated docking; topology/MCODE
  remain independent extensions. ADR 0003 scope is partially superseded.
- Corrected mass/identity, redocking/RMSD, pLDDT, failure-status and numeric-validation requirements;
  synchronized README, architecture, limitations and review decisions with pending implementation.
- These are documentation changes only: no CLI/Schema/runtime behavior or dependency was changed,
  no new test run/release is claimed, and prior staged work is preserved.

### Added (existing implementation)

- `rnp intersect`: HGNC normalization of target genes (approved/previous/alias/unique-UniProt,
  with ambiguity and symbol↔UniProt conflicts reported), best-probability deduplication per
  compound–gene pair, disease intersection, per-group set counts, `venn.json`, and an audit of every
  excluded row.
- `rnp network`: per-group Cytoscape node/edge/MOLlist tables with invariant checks (endpoint/node
  consistency, no duplicate edges, MOLID coverage, compound↔gene collision detection).
- `R/venny.R`: optional two-set Venn figure (PNG + PDF) rendered from `venn.json`.
- Schemas `intersection.schema.json` and `network.schema.json`; `inputs.hgnc_map` and `network.*`
  added to the run schema.
- 22 new tests (60 total): mapping rules, exclusions, collision handling, CLI chain, manifest
  contracts, optional R Venn rendering.

### Planned

- Public-data demo with golden files
- `rnp enrich` CLI, explicit background/status handling and independent numeric tests
- Upstream structure identity/selection (v0.2); limited calibrated docking (v0.3)
- Independent later topology/RRA and MCODE extensions
- `rnp report` and the agent skill layer

## [0.0.1] scaffold - 2026-10-18

Local package/scaffold milestone; this heading does not assert a published tag or GitHub release.
Historical test totals below are prior reports, not a fresh result from this documentation revision.

### Added

- Python package `reproducible-network-pharmacology` with the `rnp` CLI.
- JSON Schemas for the run config, STP audit, run manifest and the R enrichment bridge.
- `rnp validate`: schema validation plus existence checks for every declared input.
- `rnp ingest stp`: SwissTargetPrediction `.csv` / `.xlsx` parsing with merged-title-row
  detection, multi-symbol and composite-target handling, probability validation, per-file
  audit (`stp_audit.json`), deterministic `targets.tsv`, and a `run_manifest.json`.
- `rnp manifest`: schema validation plus input-hash drift detection.
- `R/ora.R`: GO/KEGG over-representation bridge via `clusterProfiler`, reporting its own
  package versions and writing a stable result table.
- Tests: 38 cases covering config validation, every known STP trap, CLI exit codes, manifest
  drift, and the R bridge contract (live run when `Rscript` is available).
- CI: lint + tests on Python 3.10–3.12, plus an R contract job on `main`.
- Documentation: architecture, review gates, limitations, data licenses, three ADRs.
