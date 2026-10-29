# v0.1.0 release notes — DRAFT, NOT PUBLISHED

Status: **planned release notes for review**. Do not present these links as downloadable until the
assets are actually uploaded and the URLs verified.

## Software

- Version: **0.1.0**
- Build commit: `a5b9116f4863a050e74a9a40a7d7f155fe7f6258`
- Wheel: `reproducible_network_pharmacology-0.1.0-py3-none-any.whl` (70,154 bytes)
  SHA-256 `40a0f21339e70a7a2c0422866573f20077ab3d3ed2f9ff8c6db07c049b78c1fb`
- Sdist: `reproducible_network_pharmacology-0.1.0.tar.gz` (1,130,191 bytes)
  SHA-256 `b945f31581856e338f0a3a8760796706ab778dd24c92c084fbd2c007fee05d46`
- Code license: MIT.
- Install/check:

```bash
uv venv
uv pip install reproducible_network_pharmacology-0.1.0-py3-none-any.whl
rnp --version        # 0.1.0
rnp --help
```

## Case data asset (selected inclusion; upload pending)

- Asset: `rnp-case-v0.1.0-2026-10-21.zip` (938,555 bytes)
- SHA-256: `55b65aefe8ff97c08d12b16945db9313931aa65aea947c96bfdf2aab5fe927e4`
- Payload: **35 files + `SHA256SUMS.tsv` = 36 total**
- Release URL: **planned / pending upload** — replace this line with the fixed tag/asset URL after
  upload and verify the downloaded file hash.
- Full download/checksum/reproduction commands: `examples/demo/DATA-ACCESS.md`.

## What changed

- v0.1.0 release candidate for the audited `validate → ingest → intersect → network → enrich →
  report → manifest` CLI and thin Skill.
- Explicit background enforcement, failure propagation, effective foreground/background recording,
  independent hypergeometric/BH baseline and per-run provenance.
- Portable case entry with strict submission-log binding, exact submitted structure checks, double
  threshold, manifest checks and independent checker.
- Public RA case candidate: STP tables, CTD direct-evidence subset, HGNC snapshot, PubChem computed
  structures and frozen expected counts, with source-specific terms.

## Data licenses and attribution

- Code MIT.
- STP native XLSX: CC BY 4.0; original bytes unchanged; cite SwissTargetPrediction, prediction date
  2026-10-21 and Daina & Zoete 2024.
- CTD: public non-profit research permission, ticket #8545; cite CTD and the September 2026 data
  date-stamp; commercial use separate; do not relicense as MIT/CC0/CC BY.
- HGNC: CC0.
- PubChem: computed descriptors; NCBI places no restrictions by NCBI, but third-party submitters may
  retain rights and NCBI cannot grant unrestricted permission; no MIT/CC0/CC BY claim. See
  `examples/demo/inputs/PUBCHEM-SOURCE.md`.
- The mixed-source case package is not MIT/CC BY as a whole; full citations in `ATTRIBUTION.md` and
  `docs/citations.md`.

## Post-release checklist

1. Upload the approved wheel, sdist and case ZIP as release assets.
2. Replace the planned URL(s) with the actual fixed tag/asset URLs; verify download and SHA-256.
3. Set `CITATION.cff` `date-released` to the actual release date; do not invent a DOI.
4. Update CASE-FREEZE/DATA-ACCESS status only after publication; keep tests aligned with the real
   state.
5. Notify CTD of the public project link with the data date-stamp; do not send a new permission
   request for the already-confirmed scope.
6. Keep private EMLs, screenshots, full headers, personal email, IP/session data and unredacted logs
   outside Git and release assets.

## Not claimed

- Not yet published, no tag/release, no DOI, no download URL.
- Results are predicted associations/annotation overlap, not experimental validation.
- Windows native R remains unverified; Linux is the verified case platform.
