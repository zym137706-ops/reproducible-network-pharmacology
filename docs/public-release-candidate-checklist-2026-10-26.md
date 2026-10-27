# Public release candidate checklist — 2026-10-27

This is a planning checklist, not a release. STP's 2026-10-23 reply confirms **CC BY 4.0** for the
eight native tables; CTD ticket **#8545** (2026-10-26) confirms **public non-profit research including
GitHub** for the requested 179-gene subset/derived outputs, with CTD citation and a data date-stamp.
Commercial use of CTD is separate. A complete review candidate is prepared and reproduced, but the
researcher has **not** approved publication; PubChem structure terms remain separately pending.

## 1. Ready to prepare (code/public synthetic)

| Item | Path/class | Status |
|---|---|---|
| Python package and CLI | `src/rnp/`, `pyproject.toml`, `uv.lock` | implement/tested; Linux CI green |
| R bridge and locked R environment | `R/`, `renv.lock`, `scripts/restore_r.sh` | restored/tested in Linux CI |
| Synthetic quickstart | `examples/quickstart/`, `tests/fixtures/` | complete chain, no restricted data |
| Portable case entry | `scripts/case_run.py`, `scripts/case_check.py`, `docs/case-run.md` | tested; synthetic CI e2e |
| User-supplied data instructions | README, `docs/case-run.md`, `docs/data-licenses.md` | documented |
| Licence/environment/limitations docs | `LICENSE`, `docs/environment.md`, `docs/limitations.md` | review before release |
| Code provenance | `docs/case-entry-clean-run-2026-10-22.md` | clean-clone evidence; no restricted data |

## 2. Complete public case candidate (review only)

- Local candidate: `C:/DSH/rnp-public-case-candidate-2026-10-21/`
- 33 files; `SHA256SUMS.tsv` covers all candidate files except itself.
- Includes relative-path `run-0.10.yaml`/`run-0.05.yaml`, STP XLSX, compounds with actual submitted
  structures, de-identified submission log, CTD genes/evidence/query metadata, HGNC, both universes
  and foregrounds, PubChem source note, permissions, expected counts and verification note.
- Reproduced from clean commit `90f3178`; see `docs/public-candidate-reproduction-2026-10-27.md`.
- STP: CC BY 4.0; originals unmodified; cite SwissTargetPrediction/prediction date/Daina & Zoete 2024.
- CTD: public non-profit research permission, ticket #8545; cite CTD and include a data date-stamp;
  commercial use separate; do not relicense as MIT/CC0/CC BY.
- Candidate is **outside Git**, not uploaded, and still requires researcher review/approval.

## 3. Still excluded or separately gated

- PubChem structure table/source terms: not cleared by STP/CTD; keep out of public release until
  separately reviewed.
- Private EMLs, full headers, screenshots, school/personal email, IP/session data and private
  submission correspondence.
- Any mixed-source derived output that cannot be attributed/cleared per source.
- Final version/tag/release and repository visibility changes.

## 4. Researcher decisions before release

1. Approve the complete candidate's data inclusion, repository visibility and versioned release.
2. Decide whether the PubChem structure table/compounds are published, deferred, or replaced by a
   query/source recipe after terms review.
3. When published, notify CTD of the public project link and include the required CTD date-stamp.
4. Confirm the final tag/release and attribution/CITATION files (not performed in this round).

## 5. Validation

- `uv run ruff check .`
- `uv run pytest -q` (code baseline) and targeted case/licence tests.
- Linux CI including synthetic portable entry and wrong-structure rejection.
- Candidate `SHA256SUMS.tsv` recheck; 33 files; STP XLSX byte-identical; clean-clone candidate
  reproduction passed both thresholds + checker with expected counts.
- No real restricted data in Git/CI; do not rewrite Git history if a private file is found—report it.

Tracked-file audit (2026-10-27): no real STP XLSX, CTD gene extract, private submission log, full
permission screenshot/EML, school/private email or detailed result table is tracked. The tracked
`STP-SUBMISSION-LOG.tsv` is the blank template; `compounds.tsv` has no structures; HGNC is public CC0;
test fixtures are synthetic. The complete candidate and private permission evidence remain outside Git.
