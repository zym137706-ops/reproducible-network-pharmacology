# Public release candidate checklist — 2026-10-26

This is a planning checklist, not a release. The overall public RA case remains **blocked** pending
CTD permission. STP's reply confirms CC BY 4.0 for the eight native tables only; it does not authorize
CTD data, PubChem structures, the private submission log or mixed-source detailed results.

## 1. Ready to prepare (code/public synthetic)

| Item | Path/class | Status |
|---|---|---|
| Python package and CLI | `src/rnp/`, `pyproject.toml`, `uv.lock` | implement/tested; Linux CI green |
| R bridge and locked R environment | `R/`, `renv.lock`, `scripts/restore_r.sh` | restored/tested in Linux CI |
| Synthetic quickstart | `examples/quickstart/`, `tests/fixtures/` | complete chain, no restricted data |
| Portable case entry | `scripts/case_run.py`, `scripts/case_check.py`, `docs/case-run.md` | tested; synthetic CI e2e |
| User-supplied data instructions | README, `docs/case-run.md`, `docs/data-licenses.md` | requires users to obtain their own upstream data |
| Licence/environment/limitations docs | `LICENSE`, `docs/environment.md`, `docs/limitations.md` | review before release |
| Code provenance | `docs/case-entry-clean-run-2026-10-22.md` | clean-clone evidence; no restricted data |

## 2. STP confirmed, candidate review pending

- Local candidate: `C:/DSH/rnp-stp-release-candidate-2026-10-21/`
- Eight byte-identical XLSX files under `data/`; `SHA256SUMS.tsv`, `FILES.tsv`, `README.md`,
  `ATTRIBUTION.md`, `DATA-LICENSE.md`.
- Licence: CC BY 4.0; original tables unmodified; attribution and citation required.
- Candidate is **outside Git**, not uploaded, and still requires researcher review before publication.
- Do not add the private submission log, actual structures, school email correspondence or full
  permission screenshot.
- If only the STP tables are published, state clearly that they are data, not code; code remains MIT.

## 3. Still excluded pending CTD or other-source clearance

- `examples/demo/inputs/disease_genes.txt` (local 179 CTD genes) and CTD evidence table.
- Disease intersection, compound-gene network tables, GO enrichment tables and detailed reports that
  contain or derive from CTD data.
- PubChem structure table/local files until PubChem terms are separately reviewed.
- Private submission log, school/personal email correspondence and complete permission screenshots.
- Any mixed-source derived output that cannot be attributed/cleared per source.

## 4. Researcher decisions before release

1. CTD reply/scope: permit the 179-gene subset and derived outputs, or keep them local?
2. If CTD does not permit, publish only code/synthetic/query recipe/checksums, or choose another
   public source with clear terms?
3. Which STP-derived outputs (only tables vs selected derived tables) should be public?
4. Final version/tag/release and visibility change (not performed in this round).

## 5. Validation

- `uv run ruff check .`
- `uv run pytest -q`
- Linux CI including synthetic portable entry and wrong-structure rejection.
- Candidate hash comparison against the frozen 2026-10-21 file-checks.
- No real restricted data in Git/CI; do not rewrite Git history if a private file is found—report it.

Tracked-file audit (2026-10-26): no real STP XLSX, CTD gene extract, private submission log, full
permission screenshot, school/private email or detailed result table is tracked. The tracked
`STP-SUBMISSION-LOG.tsv` is the blank template; `compounds.tsv` has no structures; HGNC is public CC0;
test fixtures are synthetic. The real candidate and CTD follow-up remain outside Git.
