# Image-provenance errata and launch-attestation policy — 2026-10-28

## What was wrong

The historical run output `C:/DSH/rnp-public-candidate-image-2026-10-27/` recorded:

```json
"image": "bioconductor/bioconductor_docker:RELEASE_3_22",
"image_id": "sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a",
"image_digest": "bioconductor/bioconductor_docker@sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a"
```

The same registry index digest (`e341…`) was written into both `image_id` and `image_digest`. That
does not distinguish a local image identity, a registry index, a platform manifest and a config
digest. The old container was started with `--rm`, so its `.Image` value cannot now be recovered.

**The old `case_provenance.json` and report hashes are preserved unchanged.** This file is an
errata/attestation, not a rewrite of the historical record. The old report hashes remain:
0.10 `2e02dc0a…`, 0.05 `c8e6ab18…`.

## Verified image facts

### Registry (provided by the independent Docker Registry check, not an old-container measurement)

- Image tag/reference: `bioconductor/bioconductor_docker:RELEASE_3_22`
- OCI multi-platform index digest:
  `sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a`
- `linux/amd64` manifest digest:
  `sha256:67ab741591c5cd068f8993ca5f0371794c300da9cc5e0b3b2c1c90c9058e4c6f`
- `linux/amd64` config digest:
  `sha256:7da6175410ad783fab92656b46c247ce6b72473e485e4aca0c176703fb381c63`

These values identify the registry objects; they are not claimed as the old container's measured
`.Image`.

### Local Docker inspect on 2026-10-28

- `docker image inspect bioconductor/bioconductor_docker:RELEASE_3_22 .Id`:
  `sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a`
- `.RepoDigests[0]`:
  `bioconductor/bioconductor_docker@sha256:e34177896c1579f66d48b756e4229b58237499183a089da084af72d7aba1d40a`
- `.Os` / `.Architecture`: `linux` / `amd64`
- This Docker image store reports the index digest as `.Id`; the registry config digest `7da6…` is
  separately recorded and is not substituted for `.Id`.
- Old container `.Image`: **not recoverable** (container removed with `--rm`).

## Final launch attestation

A new final candidate run was started without `--rm`, and the container was inspected before removal.
The attestation records the actual container `.Image`, local image `.Id`, platform, registry
manifest/config digests and the run's provenance/report paths. The old run remains historical; the
new run is the main verification record in `docs/public-candidate-reproduction-2026-10-28.md` and the
candidate `VERIFICATION.md`.

## Rule

Do not backfill old provenance. Use separate named fields:

- `image`: tag/reference supplied by the runner;
- `image_id`: local image/container identity actually observed;
- `image_digest`: RepoDigest/index digest supplied by the runner/registry;
- `image_platform`: actual platform, e.g. `linux/amd64`;
- `image_manifest_digest`: platform manifest digest, when known;
- `image_config_digest`: platform config digest, when known.

If a value is unknown, leave it null and say which source would be needed; never concatenate or infer
a digest from unrelated strings.
