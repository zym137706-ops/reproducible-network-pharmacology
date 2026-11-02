# Public release candidate checklist — 2026-10-28

This checklist records the **published v0.1.0** state. Software and the case data asset are released;
real case data is not duplicated in the Git tree. Source-specific data terms are recorded below.
Release: <https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/tag/v0.1.0>
(tag target `de7ac950fd2da5fde231a36755a7a3af37a5dbe0`).

## 1. Software candidate

| Item | Path/class | Status |
|---|---|---|
| Python package and CLI | `src/rnp/`, `pyproject.toml`, `uv.lock` | version 0.1.0; published 2026-11-02 |
| R bridge and locked R environment | `R/`, `renv.lock`, `scripts/restore_r.sh` | restored/tested in Linux CI |
| Synthetic quickstart | `examples/quickstart/`, `tests/fixtures/` | complete chain, no restricted data |
| Portable case entry | `scripts/case_run.py`, `scripts/case_check.py`, `docs/case-run.md` | tested; final candidate reproduction passed |
| Wheel/sdist | `dist/reproducible_network_pharmacology-0.1.0-*` | built; clean-venv install checked |
| Wheel (70,154 bytes) | `reproducible_network_pharmacology-0.1.0-py3-none-any.whl` | `40a0f21339e70a7a2c0422866573f20077ab3d3ed2f9ff8c6db07c049b78c1fb` |
| Sdist (1,131,479 bytes) | `reproducible_network_pharmacology-0.1.0.tar.gz` | `1dea9b2075396eaa009b2d0eeb96ea6c99fdbf99b2c83432a1f82fb74b84ab5e` |
| Citation/version | `CITATION.cff`, `docs/citations.md` | 0.1.0, unreleased, upstream citations added |
| Code provenance | `docs/case-entry-clean-run-2026-10-22.md`; final run below | no restricted data |

## 2. Published case package

- Published asset: `CASE-PKG-2026-10-21`; release URL https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/tag/v0.1.0
- Data access and reproduction entry: `examples/demo/DATA-ACCESS.md`
- Versioned release asset: `rnp-case-v0.1.0-2026-10-21.zip` (938,555 bytes)
- Zip SHA-256: `55b65aefe8ff97c08d12b16945db9313931aa65aea947c96bfdf2aab5fe927e4`
- Package counts: **35 payload files + `SHA256SUMS.tsv` = 36 total files**; 35/35 hashes and sizes
  verified after extraction.
- Contents: relative-path `run-0.10.yaml`/`run-0.05.yaml`, STP XLSX, compounds with exact submitted
  structures, de-identified submission log, CTD genes/evidence/query metadata, HGNC, both universes
  and foregrounds, PubChem per-CID provenance/source note, permissions, citations, expected counts,
  verification and checksum manifest.
- **Data-inclusion decision:** the complete case package above is selected for publication as the
  versioned release asset; real case data is not duplicated into the Git tree.
- STP: CC BY 4.0; originals unmodified; cite SwissTargetPrediction/prediction date/Daina & Zoete 2024.
- CTD: public non-profit research permission, ticket #8545; cite CTD (2025 update paper) and include
  the data date-stamp (September 2026; retrieval 2026-10-21); commercial use separate; do not
  relicense as MIT/CC0/CC BY.
- PubChem: included in the selected case package; computed descriptors from PUG REST; NCBI
  no-restrictions-by-NCBI statement plus third-party-rights caveat; no CC license.
- Code remains MIT; the mixed-source data package is not MIT or CC BY as a whole.
- The package is **outside Git**; the approved release asset is published. Real case data is not
  duplicated in the repository.

## 3. Still excluded

- Private EMLs, full headers, screenshots, school/personal email, IP/session data and private
  submission correspondence.
- Unredacted logs or any file not listed in `SHA256SUMS.tsv`.
- Final version/tag/release and repository visibility changes until the decision below.

## 4. Release outcome

1. v0.1.0 tag and release were created from build commit `de7ac95`.
2. Repository was made public; four manual release assets were uploaded and published.
3. The public release was downloaded independently and the asset/checksum checks passed.
4. Post-release follow-up: notify CTD of the public project link and data date-stamp.
5. Do not send a new CTD/STP permission request for the already-confirmed scope.

## 5. Final verification

- Build commit / tag target: `de7ac950fd2da5fde231a36755a7a3af37a5dbe0` (`v0.1.0`).
- Case reproduction commit: `49c86ee0e09c05433c22102011d705c60df72f45` (scientific inputs unchanged).
- Clean-clone candidate reproduction: both thresholds `complete`; checker passed; manifest no drift;
  source hash `fc6784e6f46fe5dff71cc8c00a943980ded31d495689c237fb280fb17fcc8aca`.
- Counts: 0.10 T_r 239 / intersection 15 / network 23-67 / effective background 234 / 704 terms /
  0 significant; 0.05 T_r 267 / intersection 17 / network 26-74 / effective background 262 / 747
  terms / 2 significant.
- Image: tag `bioconductor/bioconductor_docker:RELEASE_3_22`; local image/container identity
  `sha256:e341…`; platform `linux/amd64`; manifest `sha256:67ab…`; config `sha256:7da6…`.
  See `docs/public-candidate-reproduction-2026-10-28.md`.
- `uv run ruff check .`; `uv run pytest` (160 passed, 17 skipped on Windows host); wheel/sdist built from
  clean checkout `de7ac95`; clean-venv wheel install; `rnp --version` = `0.1.0`; schemas/R resources present.
- Archive check: wheel 36 members; sdist 148 members; `next-steps-dsh`, `HANDOFF`, `STP-PENDING` absent;
  no EML/screenshot/private email/session/key/cache hits. `data/local/README.md` is the tracked public
  guidance page, not local data.
- Public download verification (2026-11-02): unauthenticated repository/release pages HTTP 200; all four
  manual assets downloaded; `SHA256SUMS.txt` matched all three payloads; case ZIP 35/35 valid;
  downloaded wheel installed `rnp 0.1.0` in a fresh environment.
- No real restricted data in Git/CI; no history rewrite.

Tracked-file audit (2026-11-02): no real STP XLSX, CTD gene extract, private submission log, full
permission screenshot/EML, school/private email or detailed result table is tracked. The tracked
`STP-SUBMISSION-LOG.tsv` is the blank template; `compounds.tsv` has no structures; HGNC is public CC0;
test fixtures are synthetic. The complete candidate and private permission evidence remain outside Git.
