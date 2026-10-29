# RA case data access and reproduction

Status: **v0.1.0 release candidate; data-inclusion decision selected; not published**. This is the
formal entry for obtaining the case data and reproducing the analysis. The dataset is a **versioned
release asset**, not a set of files committed to Git; the repository contains only code, templates,
rules and public reference tables.

## Case package

- Asset: `rnp-case-v0.1.0-2026-10-21.zip` (938,555 bytes)
- SHA-256: `55b65aefe8ff97c08d12b16945db9313931aa65aea947c96bfdf2aab5fe927e4`
- Contents: **35 payload files + `SHA256SUMS.tsv` = 36 total files**
- Release URL: pending researcher approval and upload. Do not invent a URL or tag before that.

The package contains the eight native STP XLSX tables (unmodified), the exact submitted compound
structures, the de-identified submission log, the 179-gene CTD subset and evidence table, HGNC
snapshot, both universes/foregrounds, expected counts, permissions/citations and a checksum manifest.
Private EMLs, screenshots, full headers, school/personal email, IP/session data and unredacted
private logs are **not** distributed.

## Obtain and verify

```bash
# Download the approved release asset (URL to be supplied with the release).
sha256sum rnp-case-v0.1.0-2026-10-21.zip
# expected: 55b65aefe8ff97c08d12b16945db9313931aa65aea947c96bfdf2aab5fe927e4

unzip rnp-case-v0.1.0-2026-10-21.zip
cd rnp-case-v0.1.0-2026-10-21

python3 - <<'PY'
import csv, hashlib, pathlib
root = pathlib.Path(".")
rows = list(csv.DictReader((root / "SHA256SUMS.tsv").open(encoding="utf-8"), delimiter="\t"))
bad = [r["file"] for r in rows if not (root / r["file"]).is_file()
       or (root / r["file"]).stat().st_size != int(r["bytes"])
       or hashlib.sha256((root / r["file"]).read_bytes()).hexdigest() != r["sha256"]]
print(f"payload={len(rows)} checksum_manifest=1 total={len(rows)+1} bad={bad}")
assert not bad
PY
```

## Run from the repository

Run from a clone of the repository; do not run `scripts/case_run.py` from the data package (the script
is in the repository). The input arguments are explicit absolute paths to the extracted package.

```bash
export REPO=/path/to/reproducible-network-pharmacology
export CASE_DIR=/path/to/rnp-case-v0.1.0-2026-10-21
export OUT=/path/to/new-case-output

cd "$REPO"
uv sync --locked --extra dev
bash scripts/restore_r.sh "$REPO/../case-rlib"
export R_LIBS="$REPO/../case-rlib"
export RNP_RSCRIPT=Rscript

uv run python scripts/case_run.py \
  --compounds "$CASE_DIR/inputs/compounds.tsv" \
  --stp-dir "$CASE_DIR/inputs/stp" \
  --disease-genes "$CASE_DIR/inputs/disease_genes.txt" \
  --hgnc-map "$CASE_DIR/inputs/hgnc_map.tsv" \
  --log "$CASE_DIR/inputs/STP-SUBMISSION-LOG.tsv" \
  --config-template "$CASE_DIR/run-0.10.yaml" \
  --out "$OUT"
```

`case_run.py` runs both thresholds, checks both manifests and invokes `scripts/case_check.py`.
Expected counts are frozen in `expected/EXPECTED.json`; see `VERIFICATION.md`.

## Licenses and attribution

- **STP:** eight native XLSX tables under CC BY 4.0; cite SwissTargetPrediction, prediction date
  **2026-10-21**, and Daina & Zoete 2024; do not modify originals.
- **CTD:** public non-profit research permission, ticket **#8545** (2026-10-26); cite CTD and include
  the data date-stamp (September 2026; retrieval 2026-10-21); commercial use is separate and CTD
  data must not be relicensed as MIT/CC0/CC BY.
- **PubChem:** computed descriptors from PUG REST; NCBI states no restrictions by NCBI, but
  third-party submitter rights cannot be excluded and NCBI cannot grant unrestricted permission.
  No CC license is asserted.
- **HGNC:** CC0.
- **Code:** MIT; the mixed-source data package is not MIT/CC BY as a whole.

Full citation strings: `ATTRIBUTION.md`; repository-level citations:
[`docs/citations.md`](../../docs/citations.md), [`docs/data-licenses.md`](../../docs/data-licenses.md).

## Not included / not claimed

- No prediction is experimental validation; network/enrichment results are predicted-association and
  annotation-overlap evidence.
- No public release, tag, DOI or repository visibility change is implied by this guide.
- After publication, the project link should be reported to CTD as requested in ticket #8545.
