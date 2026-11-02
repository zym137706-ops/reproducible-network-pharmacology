# v0.1.0 release notes

Status: **published 2026-11-02**. Repository:
<https://github.com/zym137706-ops/reproducible-network-pharmacology>

## Software

- Version: **0.1.0**
- Published build commit / tag target: `de7ac950fd2da5fde231a36755a7a3af37a5dbe0`
- Tag: `v0.1.0`
- Release: <https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/tag/v0.1.0>
- Code license: **MIT**

### Assets

| Asset | Bytes | SHA-256 |
|---|---:|---|
| [`reproducible_network_pharmacology-0.1.0-py3-none-any.whl`](https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/download/v0.1.0/reproducible_network_pharmacology-0.1.0-py3-none-any.whl) | 70,154 | `40a0f21339e70a7a2c0422866573f20077ab3d3ed2f9ff8c6db07c049b78c1fb` |
| [`reproducible_network_pharmacology-0.1.0.tar.gz`](https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/download/v0.1.0/reproducible_network_pharmacology-0.1.0.tar.gz) | 1,131,479 | `1dea9b2075396eaa009b2d0eeb96ea6c99fdbf99b2c83432a1f82fb74b84ab5e` |
| [`rnp-case-v0.1.0-2026-10-21.zip`](https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/download/v0.1.0/rnp-case-v0.1.0-2026-10-21.zip) | 938,555 | `55b65aefe8ff97c08d12b16945db9313931aa65aea947c96bfdf2aab5fe927e4` |
| [`SHA256SUMS.txt`](https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/download/v0.1.0/SHA256SUMS.txt) | 337 | checksum manifest |

### Install and verify (wheel)

Linux/macOS:

```bash
uv venv .venv
uv pip install --python .venv/bin/python ./reproducible_network_pharmacology-0.1.0-py3-none-any.whl
.venv/bin/rnp --version    # 0.1.0
.venv/bin/rnp --help
```

Windows:

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe .\reproducible_network_pharmacology-0.1.0-py3-none-any.whl
.\.venv\Scripts\rnp.exe --version    # 0.1.0
.\.venv\Scripts\rnp.exe --help
```

Verify all manually uploaded assets against `SHA256SUMS.txt` before use.

## Case data and reproduction

- Asset: `rnp-case-v0.1.0-2026-10-21.zip`
- Payload: **35 files + `SHA256SUMS.tsv` = 36 total**
- Download/checksum/reproduction guide:
  <https://github.com/zym137706-ops/reproducible-network-pharmacology/blob/v0.1.0/examples/demo/DATA-ACCESS.md>
- In the **extracted case package**, PubChem source/terms details are at `inputs/PUBCHEM-SOURCE.md`.
- In the **repository**, the PubChem review record is
  <https://github.com/zym137706-ops/reproducible-network-pharmacology/blob/v0.1.0/docs/pubchem-structure-review-2026-10-27.md>.
- Frozen expected counts: 0.10 `T_r=239`, intersection 15, network 23/67, effective background
  234, GO terms 704, significant 0; 0.05 `T_r=267`, intersection 17, network 26/74, effective
  background 262, GO terms 747, significant 2.

The case ZIP contains the eight native STP XLSX tables unmodified, exact submitted structures,
de-identified submission log, 179-gene CTD subset/evidence, HGNC snapshot, universes/foregrounds,
expected counts and cited source records. It contains no private EML, screenshot, full headers,
school/personal email, IP/session data, unredacted logs or local machine data.

## Data licenses and attribution

- **Code:** MIT.
- **STP native XLSX:** CC BY 4.0; preserve original bytes; cite SwissTargetPrediction, prediction date
  2026-10-21 and Daina & Zoete 2024.
- **CTD:** public non-profit research permission, ticket #8545 (2026-10-26); cite CTD and the
  September 2026 data date-stamp; commercial use is separate; do not relicense as MIT/CC0/CC BY.
- **HGNC:** CC0.
- **PubChem:** computed descriptors from the PUG REST property endpoint, retrieved 2026-10-20;
  per-CID record URLs, fields, OEChem/PubChem release references and raw-response hashes are recorded
  in the case package. NCBI places no restrictions by NCBI on molecular data, but third-party
  submitters may retain rights and NCBI cannot grant unrestricted permission. No MIT/CC0/CC BY claim
  is made for PubChem, and the STP/CTD replies do not cover it.
- The mixed-source case package is **not** MIT or CC BY as a whole. Full citations:
  `ATTRIBUTION.md` in the case package and `docs/citations.md` in the repository.

## Post-release

The project link is prepared for CTD notification with the data date-stamp, as requested in ticket
#8545. No new permission request for the already-confirmed CTD/STP scope is needed.

## Not claimed

- No DOI.
- Results are predicted associations/annotation overlap, not experimental validation.
- Windows native R remains unverified; Linux is the verified case platform.
