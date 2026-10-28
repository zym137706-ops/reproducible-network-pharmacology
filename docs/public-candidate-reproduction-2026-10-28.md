# Public case final reproduction — 2026-10-28

Main verification record for the v0.1.0 release candidate. The 2026-10-27 run remains historical.

## Inputs and source

- Candidate package: `C:/DSH/rnp-public-case-candidate-2026-10-21/`
- Clean clone: `C:/DSH/rnp-clean-clone-49c86ee`
- Commit: `49c86ee0e09c05433c22102011d705c60df72f45` (`49c86ee`), dirty `false`
- Source hash (`case-source-hash-v2` combined):
  `fc6784e6f46fe5dff71cc8c00a943980ded31d495689c237fb280fb17fcc8aca`
- Candidate payload: **35 files + `SHA256SUMS.tsv` = 36 total** (recount from manifest).
- The candidate was mounted read-only; no STP/CTD re-download and no parameter change.

## Image identity

| Field | Value | Source |
|---|---|---|
| image reference | `bioconductor/bioconductor_docker:RELEASE_3_22` | runner |
| local image `.Id` / container `.Image` | `sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a` | Docker inspect of final container + local image |
| RepoDigest / OCI index digest | `bioconductor/bioconductor_docker@sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a` | local `RepoDigests` |
| run platform | `linux/amd64` | image/container inspect |
| `linux/amd64` manifest digest | `sha256:67ab741591c5cd068f8993ca5f0371794c300da9cc5e0b3b2c1c90c9058e4c6f` | Registry check (not old-container measurement) |
| `linux/amd64` config digest | `sha256:7da6175410ad783fab92656b46c247ce6b72473e485e4aca0c176703fb381c63` | Registry check (not old-container measurement) |

The final container was created without `--rm`; `docker inspect <container> --format '{{.Image}}'`
was captured before removal. The old 2026-10-27 container was removed with `--rm`; its `.Image` is
**not recoverable**, and its provenance is preserved rather than backfilled. See
`docs/image-provenance-errata-2026-10-28.md`.

Launch attestation (local output):
`C:/DSH/rnp-public-candidate-launch-2026-10-28/launch-attestation.json`
SHA-256 `dda160d31d42cb5d49e50626cc30f3253b32c6416b8026d4b16580826b23233a`.

## Result

| Item | 0.10 | 0.05 |
|---|---:|---:|
| `T_r` | 239 | 267 |
| Foreground / intersection | 15 / 15 | 17 / 17 |
| Network nodes/edges | 23/67 | 26/74 |
| Effective foreground/background | 15/234 | 17/262 |
| GO terms tested | 704 | 747 |
| Significant | 0 | 2 |
| Report SHA-256 | `ace88ac1…` | `8c6725c3…` |

- Both thresholds `complete`; all stage audits complete.
- `manifest --check-inputs`: 10 inputs, no drift.
- Independent `case_check.py` passed; generated universes match the supplied candidate universe
  hashes.
- Report hashes are path/time-dependent; they are not cross-path equality tests. Counts are the
  invariant.

Final output: `C:/DSH/rnp-public-candidate-launch-2026-10-28/` (not committed).
Older run `C:/DSH/rnp-public-candidate-image-2026-10-27/` remains historical with report hashes
`2e02dc0a…`/`c8e6ab18…` and the original ambiguous image fields; it is not the main record.

## Boundaries

- Results are predicted associations/annotation overlap, not experimental validation.
- STP tables CC BY 4.0; CTD public non-profit research permission (ticket #8545, citation and
  date-stamp); PubChem source/terms/citation review complete with residual third-party caveat.
- The candidate is review-only, not approved for publication. No tag/release/visibility change and
  no real-data upload to Git/CI.
