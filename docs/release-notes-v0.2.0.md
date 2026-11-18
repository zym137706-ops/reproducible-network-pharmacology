# v0.2.0 release notes

Status: **release candidate, not yet published.** This file describes the candidate; the tag, the build
commit and the asset sizes and hashes are added after publication. Repository:
<https://github.com/zym137706-ops/reproducible-network-pharmacology>

## Software

- Version: **0.2.0**
- Build commit / tag target: recorded after publication
- Tag: `v0.2.0`, created only on the researcher's explicit decision
- Code license: **MIT**

### Assets

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `reproducible_network_pharmacology-0.2.0-py3-none-any.whl` | recorded after the build | recorded after the build |
| `reproducible_network_pharmacology-0.2.0.tar.gz` | recorded after the build | recorded after the build |
| `SHA256SUMS.txt` | recorded after the build | recorded after the build |

No case package is attached to v0.2.0: the RA case package stays the v0.1.0 asset
`rnp-case-v0.1.0-2026-10-21.zip`. `SHA256SUMS.txt` covers the wheel and the sdist (UTF-8 without BOM, LF only).

### Install and verify (wheel)

Linux/macOS:

```bash
uv venv .venv
uv pip install --python .venv/bin/python ./reproducible_network_pharmacology-0.2.0-py3-none-any.whl
.venv/bin/rnp --version    # 0.2.0
.venv/bin/rnp --help
```

Windows:

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe .\reproducible_network_pharmacology-0.2.0-py3-none-any.whl
.\.venv\Scripts\rnp.exe --version    # 0.2.0
.\.venv\Scripts\rnp.exe --help
```

Structure mode (`rnp ingest compounds` on a table with a `smiles` column) needs the optional extra `chem`
(RDKit): install the wheel as `"./reproducible_network_pharmacology-0.2.0-py3-none-any.whl[chem]"`. Without it
the command stops with an error that names the extra. The case entry `scripts/case_run.py` and its checker
`scripts/case_check.py` are part of the repository, not of the wheel; use the repository at the tag.

Verify the manually uploaded assets against `SHA256SUMS.txt` before use.

## What is new

This is the first slice of the upstream side (entry A, a confirmed compound list) plus the receptor-side
acquisition command. The v0.1 core pipeline, the R bridge, `renv.lock` and the Skill are unchanged, and runs that
use none of the new options behave as before (`run.schema.json` gained optional inputs only; existing configs
stay valid). Details and exit codes are in the [changelog](../CHANGELOG.md) and [upstream](upstream.md), section 8.

- **Compound and structure identity.** `rnp ingest compounds` registers the compounds and, when the table has a
  `smiles` column, the exact structures submitted to SwissTargetPrediction (RDKit, optional extra `chem`) together
  with the submission log. Ambiguity (shared structures, undefined or differing stereochemistry, several
  fragments, charge) is recorded and never rewritten; a row without a registered structure or with a refused
  submission is quarantined.
- **Submission bindings.** `rnp ingest stp --compounds` binds every STP export to its compound row, the submitted
  structure, the species and the export hash; the export of a quarantined compound is quarantined too.
- **Explicit selection.** `rnp compounds select` records the researcher's decisions (`include`, `exclude`,
  `needs_review`, with reason codes, rules version and reviewer) in `selection_decisions.tsv` for every candidate,
  apart from `selected_compounds.tsv`. `rnp ingest stp --selection` parses only the exports of selected
  compounds, and `rnp intersect`, `rnp network` and `rnp report` then count only those. A candidate without a
  decision is held for review, not selected.
- **Case entry.** `scripts/case_run.py --log` runs the compounds stage and judges the submission log with a case
  policy; `--selection` (needs `--log`) also applies a decision table. `scripts/case_check.py` re-derives the
  submission bindings and the selection from the raw inputs with the standard library only and compares them with
  what the stages wrote. See [case-run](case-run.md).
- **Receptor-side acquisition.** `rnp acquire` freezes the RCSB PDB and UniProt records of chosen
  `PDB_ID:UNIPROT_ACCESSION` pairs into a new directory with an `acquisition_record.json` (retrieval time, HTTP
  status, size, SHA-256, version headers); `--verify` re-checks a frozen directory offline
  ([ADR-0005](adr/0005-structure-acquisition-boundary.md)). It is the only command whose Python code uses the
  network.
- **CI.** The test job installs RDKit and runs a selection end-to-end step on synthetic inputs; the R job runs the
  case entry on synthetic inputs with a submission log and with a selection.

## Evidence

- The RA case entry with `--log` and `--selection`, run on the published v0.1.0 case package with real RDKit and
  R: [case-entry-selection-run-2026-11-17](case-entry-selection-run-2026-11-17.md). The counts equal the frozen
  expected counts when every compound is included; the decision tables used there are verification inputs, not
  scientific selections.
- The compounds stage with the case entry: [case-entry-compounds-stage-run-2026-11-13](case-entry-compounds-stage-run-2026-11-13.md).
- CI: <https://github.com/zym137706-ops/reproducible-network-pharmacology/actions/workflows/ci.yml>. The final
  verification of the build commit is added here after publication.

## Data licenses and attribution

- **Code:** MIT.
- This release adds no data source. The wheel carries code, schemas and R scripts; the sdist is built from the
  tracked files of the repository, which include the CC0 HGNC-derived map of the demo and synthetic test
  fixtures. The package contents are checked before the build.
- **RDKit** (BSD-3-Clause) is an optional dependency installed from PyPI; it is not vendored.
- **RCSB PDB / wwPDB and UniProt:** `rnp acquire` retrieves records at run time into the user's git-ignored
  `data/local/`; nothing retrieved is committed or shipped. Terms and citations: `docs/data-licenses.md`,
  `docs/citations.md`.
- The v0.1.0 case package keeps its mixed-source terms (STP CC BY 4.0, CTD public non-profit permission, HGNC CC0,
  PubChem caveat) and is not part of this release.

## Known limitations

The full list is in [limitations](limitations.md). The ones that matter most for this release:

- Structure mode needs RDKit; a registered structure is what was submitted, not a verified identity.
- STP exports are still submitted by hand, and the submission log is the researcher's record.
- "Selected" means kept by a recorded decision; it says nothing about activity.
- The case entry is stricter than the core: with `--selection` every candidate must be `include` or `exclude`
  and at least one included.
- `rnp acquire` accepts four-character PDB IDs only; entries deposited from 2027-07-21 on have only the
  extended 12-character ID (ADR-0005, Amendment 3).
- Not in this release: the processed-metabolomics entry, name → structure resolution, property annotation,
  candidate-pair tables, the construct check and docking. The Skill was not extended or re-accepted for the new
  commands.

## Not claimed

- No DOI.
- Results are predicted associations and annotation overlap, not experimental validation.
- Windows native R remains unverified; Linux is the verified case platform.
