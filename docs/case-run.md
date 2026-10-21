# Portable case run and independent check

`scripts/case_run.py` is the portable orchestrator for a real case; `scripts/case_check.py` is an
independent checker. Both accept user-provided paths and contain no host-specific `C:\DSH` path.
Every analysis step remains the `rnp` CLI.

## Inputs (user-supplied, never auto-downloaded)

- `--compounds`: TSV with `name`, `pubchem_cid`, `smiles`, `stp_file` (and other binding fields)
- `--stp-dir`: the native STP exports named exactly by `stp_file`; no fuzzy matching
- `--disease-genes`: one HGNC symbol per line
- `--hgnc-map`: frozen HGNC table with the columns expected by `rnp`
- `--log`: optional completed submission log; if provided, every result SHA-256, structure, species
  and file binding is checked before anything runs
- `--out`: a **new or empty** output directory; the runner refuses to overwrite it
- `--config-template`: defaults to `examples/demo/run.yaml`; case-specific decisions are reused

## Preflight (writes nothing except the chosen output/configs)

```bash
uv run python scripts/case_run.py \
  --compounds /path/to/compounds.tsv \
  --stp-dir /path/to/stp \
  --disease-genes /path/to/disease_genes.txt \
  --hgnc-map /path/to/hgnc_map.tsv \
  --log /path/to/STP-SUBMISSION-LOG.tsv \
  --out /path/to/new-case-output \
  --preflight-only
```

This verifies explicit bindings, every file hash, disease/HGNC presence, writes fixed configs for
0.10/0.05 and records `case_provenance.json`. It does not call the network or submit STP data.

## Full chain

```bash
uv run python scripts/case_run.py ...same inputs... --out /path/to/new-case-output
```

Order: `validate → ingest → build_case_background.py → intersect → network → enrich → report →
manifest --check-inputs` for each threshold. Any non-zero child exit stops the run. Configs are
written before ingest and are not modified afterwards.

## Independent check

```bash
uv run python scripts/case_check.py \
  --run 0.10=/path/to/out/0.10/run \
  --run 0.05=/path/to/out/0.05/run \
  --background-dir /path/to/out/backgrounds \
  --disease-genes /path/to/disease_genes.txt \
  --hgnc-map /path/to/hgnc_map.tsv \
  --out /path/to/out/independent-check.json
```

It re-derives `T_r`/foreground from targets + HGNC + disease, checks intersection/network invariants,
and independently recomputes every hypergeometric p-value and BH correction; it does not call the
functions that produced the result and does not accept copied summary counts as expected values.

## Container provenance

When run in a Linux container, the caller supplies the observed values (never inferred or invented):

```text
RNP_CONTAINER_IMAGE, RNP_CONTAINER_IMAGE_ID, RNP_CONTAINER_IMAGE_DIGEST,
RNP_CONTAINER_PYTHON, RNP_R_VERSION, RNP_R_LIB,
RNP_RENV_LOCK_SHA256, RNP_UV_LOCK_SHA256
```

`case_provenance.json` records these plus the checkout's `git` commit/dirty state and a source-content
hash. The same values are attached to each `run_manifest.json` as `container` and
`code.source_attestation`. If `.git` is unavailable, the code commit stays `null`; do not fabricate it.
The host-declared source hash/origin is explicitly labelled, not presented as a container Git check.

## Boundaries

- No automatic STP submission, no network download, no synthetic substitute for a real input.
- No restricted input or detailed result is committed or uploaded; keep them under `data/local/` or
  another ignored/external directory.
- The public-case permission gate is separate; a successful local run is not public clearance.
