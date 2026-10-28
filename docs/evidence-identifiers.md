# Evidence identifiers and path mapping

Public records may refer to local evidence by identifier instead of exposing a machine-specific
absolute path. The identifiers below are stable labels; the original attachments stay local and are
not distributed.

| Identifier | What it labels | Distribution |
|---|---|---|
| `EVID-STP-2026-10-23` | Original STP reply screenshot/EML and headers; SHA-256 values remain in the permission summary | local only |
| `EVID-CTD-2026-10-26` | Original CTD ticket #8545 EML/headers; SHA-256 remains in the permission summary | local only |
| `EVID-HANDOFF-2026-10-21` | Local handoff inputs for the RA case: compounds, completed submission log and file checks; hashes remain in `CASE-FREEZE.yaml` | local only |
| `EVID-LOCAL-RUN-2026-10-21` | Local dual-threshold results and independent-check output | local only |
| `EVID-CLEAN-RUN-2026-10-21` | Clean-clone provenance/report from the earlier case run | local only |
| `EVID-LAUNCH-2026-10-27` | Historical image-ambiguous launch output; retained, not backfilled | local only |
| `EVID-LAUNCH-2026-10-28` | Final launch output with image/attestation evidence | local only |
| `EVID-CLEAN-CHECKOUT-49c86ee` | Clean clone used for the final candidate reproduction | local only |
| `CASE-PKG-2026-10-21` | Versioned case package `rnp-case-v0.1.0-2026-10-21.zip` (35 payload files + checksum manifest) | release asset pending approval |

Dates, scope, hashes, counts, commands and citations are preserved in the public summary documents;
only the local path is replaced. A placeholder such as `<repo>` or `<local>` means the original path
was intentionally not published.

Public acquisition/reproduction entry: `examples/demo/DATA-ACCESS.md`.
