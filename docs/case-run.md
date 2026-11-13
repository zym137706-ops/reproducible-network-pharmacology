# Portable case run and independent check

`scripts/case_run.py` is the portable orchestrator for a real case; `scripts/case_check.py` is an
independent checker. Both accept user-provided paths and contain no host-specific `<repo>` path.
Every analysis step remains the `rnp` CLI.

## Inputs (user-supplied, never auto-downloaded)

- `--compounds`: TSV with `name`, `pubchem_cid`, `smiles`, `stp_file` (and other binding fields)
- `--stp-dir`: the native STP exports named exactly by `stp_file`; no fuzzy matching
- `--disease-genes`: one HGNC symbol per line
- `--hgnc-map`: frozen HGNC table with the columns expected by `rnp`
- `--log`: optional completed submission log; if provided, each row is bound by `stp_file`, and
  `rnp ingest compounds` registers the structures and checks every row (the submitted structure
  against the compound's `smiles`, the compound name, CID, species and result SHA-256) before anything
  runs. This needs RDKit (the optional extra `chem`: `uv sync --extra chem`). Missing columns,
  duplicate/missing/unbound rows, a `smiles` that RDKit cannot parse, or mismatched structures fail.
  If no log is provided, `log.provided=false`; the run is **not** labelled as a verified submission
  log, needs no RDKit and runs no compounds stage.
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
0.10/0.05 and records `case_provenance.json`. With `--log` it also runs `rnp ingest compounds` on a
copy of the inputs in a temporary directory (removed afterwards) and refuses the case unless every
submission is checked; nothing of that run is kept in the output directory. It does not call the
network or submit STP data.

## Full chain

Use the same explicit inputs as preflight (replace the example paths with the extracted case package):

```bash
uv run python scripts/case_run.py \
  --compounds /path/to/compounds.tsv \
  --stp-dir /path/to/stp \
  --disease-genes /path/to/disease_genes.txt \
  --hgnc-map /path/to/hgnc_map.tsv \
  --log /path/to/STP-SUBMISSION-LOG.tsv \
  --config-template /path/to/run-0.10.yaml \
  --out /path/to/new-case-output
```

The exact release-asset paths and environment setup are documented in
[`examples/demo/DATA-ACCESS.md`](../examples/demo/DATA-ACCESS.md). The command is the same as
preflight without `--preflight-only`; it is not a shorthand for omitted arguments.

Order: `validate → ingest compounds` (with `--log` only) `→ ingest stp → build_case_background.py →
intersect → network → enrich → report → manifest --check-inputs` for each threshold (with `--log`,
`ingest stp` gets `--compounds <stage>` and the stage directory is checked with a second
`manifest --check-inputs`), then **`case_check.py` once across both runs**. The
overall `case_provenance.json` becomes `complete` only after the analysis, both manifest checks and
the independent checker succeed. A child/checker failure exits non-zero and persists `status=failed`,
`failed_stage`, `failed_command` and the real `child_exit_code`, with the earlier commands retained.
Configs are written before ingest and are not modified afterwards.

## Structures and the submission log

With `--log`, each threshold gets a compounds stage next to its run: `<out>/<threshold>/run_compounds/`
holds `compound_structures.tsv` (structure id, InChIKey and submission status of every compound),
`compounds_audit.json` and `run_manifest.json`, and `ingest stp --compounds` ties every STP export to
the structure that was submitted for it. The case policy `case-log-policy-v2` is stricter than the
command: every compound needs a registered structure and a checked submission (`verified`,
`verified_kind_unstated` or `reconstructed`), and a missing log row, a log row without a compound or a
log without `result_sha256` is an error, although the command only warns. Warnings about the structure
itself (`stereo_undefined`, `multi_fragment`, `charged_structure`, `shared_structure`) are recorded, not
refused. `case_provenance.json` records `inputs.log.policy`, `inputs.structures` (mode, RDKit version,
status and issue counts) and `inputs.compounds_stage` (per threshold: the directory and the SHA-256 of
the audit and of the table).

A recorded run of this chain on the v0.1.0 case package is in
[`case-entry-compounds-stage-run-2026-11-13.md`](case-entry-compounds-stage-run-2026-11-13.md).

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
RNP_CONTAINER_IMAGE_PLATFORM, RNP_CONTAINER_IMAGE_MANIFEST_DIGEST,
RNP_CONTAINER_IMAGE_CONFIG_DIGEST, RNP_CONTAINER_PYTHON,
RNP_R_VERSION, RNP_R_LIB, RNP_RENV_LOCK_SHA256, RNP_UV_LOCK_SHA256
```

Use the values actually observed on the host:
- `RNP_CONTAINER_IMAGE_ID`: the local image ID (for example `docker image inspect --format '{{.Id}}'`);
- `RNP_CONTAINER_IMAGE_DIGEST`: the RepoDigest/index digest supplied by the registry;
- `RNP_CONTAINER_IMAGE_PLATFORM`: the actual run platform, e.g. `linux/amd64`;
- `RNP_CONTAINER_IMAGE_MANIFEST_DIGEST`: the platform manifest digest, when separately known;
- `RNP_CONTAINER_IMAGE_CONFIG_DIGEST`: the platform manifest's config digest, when separately known.

Do not concatenate strings to invent a digest. If the local Docker store reports the index digest
as `.Id`, record that observed value and label the registry-derived platform/config digests
separately; do not claim the registry value was an old container's measured `.Image`.

`case_provenance.json` records these plus the checkout's `git` commit/dirty state. Source hashing uses
the versioned `case-source-hash-v2` rule: sha256 over sorted repo-relative POSIX paths + NUL + raw
bytes + NUL, covering `src/rnp`, `R`, `schemas`, the three case entrypoint scripts and `uv.lock` /
`renv.lock`. Caches, `.venv`, build/output directories and `data` are excluded. Core, entrypoint, lock
and combined hashes are recorded separately; this is explicitly **case-relevant source, not a full
repository/package hash**. A new cache file does not change the hash; a controlled source edit does.
The same values are attached to each `run_manifest.json` as `container` and
`code.source_attestation` (including the hash scope). If `.git` is unavailable, the code commit stays
`null`; do not fabricate it. The host-declared source hash/origin is explicitly labelled, not
presented as a container Git check.

## Boundaries

- No automatic STP submission, no network download, no synthetic substitute for a real input.
- Do not use `swiss-target-prediction-batch` or another browser/Agent batch-submission skill for the
  official case. Those runs are separate exploratory snapshots: store them in a new ignored
  `data/local/case/stp-reproduction-<date>/` directory, never under the frozen `stp/` input or its
  submission log, and never let them overwrite the manual exports. Compare first; adopting a new
  snapshot is a scientific decision and needs a new log/hashes and both-threshold rerun.
- No restricted input or detailed result is committed or uploaded; keep them under `data/local/` or
  another ignored/external directory.
- The public-case permission gate is separate; a successful local run is not public clearance.
