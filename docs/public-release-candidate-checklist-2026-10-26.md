# Public release candidate checklist — 2026-10-28

This is a planning/approval checklist, **not a release**. The software is v0.1.0 release candidate;
the case package is prepared, complete and reproduced, but no real case data has been committed,
uploaded, made public or released. STP/CTD/PubChem review and the publication decision are separate.

## 1. Software candidate

| Item | Path/class | Status |
|---|---|---|
| Python package and CLI | `src/rnp/`, `pyproject.toml`, `uv.lock` | version 0.1.0; tests pass; Linux CI green |
| R bridge and locked R environment | `R/`, `renv.lock`, `scripts/restore_r.sh` | restored/tested in Linux CI |
| Synthetic quickstart | `examples/quickstart/`, `tests/fixtures/` | complete chain, no restricted data |
| Portable case entry | `scripts/case_run.py`, `scripts/case_check.py`, `docs/case-run.md` | tested; final candidate reproduction passed |
| Wheel/sdist | `dist/reproducible_network_pharmacology-0.1.0-*` | built; clean-venv install checked |
| Wheel SHA-256 | `reproducible_network_pharmacology-0.1.0-py3-none-any.whl` | `42843decc041009366b27e0b7630dface924c2ba946faf7550dc544abf3fca13` |
| Sdist SHA-256 | `reproducible_network_pharmacology-0.1.0.tar.gz` | `309bfc0d5a9ee34024a8cd75d73c8371542712c7149e06b977e2450db449015e` |
| Citation/version | `CITATION.cff`, `docs/citations.md` | 0.1.0, unreleased, upstream citations added |
| Code provenance | `docs/case-entry-clean-run-2026-10-22.md`; final run below | no restricted data |

## 2. Final case package (review only)

- Review candidate: `CASE-PKG-2026-10-21` (review-only; not committed)
- Data access and reproduction entry: `examples/demo/DATA-ACCESS.md`
- Versioned release asset: `rnp-case-v0.1.0-2026-10-21.zip`
- Zip SHA-256: `5fe85b4ec737ada8b86c88d2e5596e1582105ab89d8dbf4c6c83188e108a3d2c`
- Package counts: **35 payload files + `SHA256SUMS.tsv` = 36 total files**; 35/35 hashes and sizes
  verified after extraction.
- Contents: relative-path `run-0.10.yaml`/`run-0.05.yaml`, STP XLSX, compounds with exact submitted
  structures, de-identified submission log, CTD genes/evidence/query metadata, HGNC, both universes
  and foregrounds, PubChem per-CID provenance/source note, permissions, citations, expected counts,
  verification and checksum manifest.
- STP: CC BY 4.0; originals unmodified; cite SwissTargetPrediction/prediction date/Daina & Zoete 2024.
- CTD: public non-profit research permission, ticket #8545; cite CTD (2025 update paper) and include
  the data date-stamp (September 2026; retrieval 2026-10-21); commercial use separate; do not
  relicense as MIT/CC0/CC BY.
- PubChem: computed descriptors from PUG REST; NCBI no-restrictions-by-NCBI statement plus
  third-party-rights caveat; no CC license. Publication is a separate researcher decision.
- Code remains MIT; the mixed-source data package is not MIT or CC BY as a whole.
- The package is **outside Git** and must not be uploaded until the researcher approves.

## 3. Still excluded

- Private EMLs, full headers, screenshots, school/personal email, IP/session data and private
  submission correspondence.
- Unredacted logs or any file not listed in `SHA256SUMS.tsv`.
- Final version/tag/release and repository visibility changes until the decision below.

## 4. Researcher decisions before release

1. Approve the final file list and this package's data inclusion.
2. Decide whether the PubChem structure table/compounds are published with the documented caveat,
   deferred, or replaced by a query/source recipe.
3. Approve repository visibility and the `v0.1.0` tag/release.
4. After publication, notify CTD of the public project link and include the CTD date-stamp.
5. Do not send a new CTD/STP permission request for the already-confirmed scope.

## 5. Final verification

- Commit: `49c86ee0e09c05433c22102011d705c60df72f45` (software v0.1.0 metadata/provenance).
- Clean-clone candidate reproduction: both thresholds `complete`; checker passed; manifest no drift;
  source hash `fc6784e6f46fe5dff71cc8c00a943980ded31d495689c237fb280fb17fcc8aca`.
- Counts: 0.10 T_r 239 / intersection 15 / network 23-67 / effective background 234 / 704 terms /
  0 significant; 0.05 T_r 267 / intersection 17 / network 26-74 / effective background 262 / 747
  terms / 2 significant.
- Image: tag `bioconductor/bioconductor_docker:RELEASE_3_22`; local image/container identity
  `sha256:e341…`; platform `linux/amd64`; manifest `sha256:67ab…`; config `sha256:7da6…`.
  See `docs/public-candidate-reproduction-2026-10-28.md`.
- `uv run ruff check .`; `uv run pytest` (160 passed, 17 skipped on Windows host); wheel/sdist build;
  clean-venv wheel install; `rnp --version` = `0.1.0`; packaged schemas/R resources present.
- No real restricted data in Git/CI; no history rewrite.

Tracked-file audit (2026-10-28): no real STP XLSX, CTD gene extract, private submission log, full
permission screenshot/EML, school/private email or detailed result table is tracked. The tracked
`STP-SUBMISSION-LOG.tsv` is the blank template; `compounds.tsv` has no structures; HGNC is public CC0;
test fixtures are synthetic. The complete candidate and private permission evidence remain outside Git.
