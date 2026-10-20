# Public-data demo: freeze state

Status: **blocked, not a completed public case.** The machine-readable freeze is
[`CASE-FREEZE.yaml`](CASE-FREEZE.yaml); the acceptance checklist is
[`docs/public-case-checklist.md`](../../docs/public-case-checklist.md), and candidate sources are in
[`docs/public-case-sources.md`](../../docs/public-case-sources.md).

The recorded scientific decisions are frozen:

- eight public compounds identified by PubChem CID (see `inputs/compounds.tsv`);
- `stp_probability: 0.10` with a separate `0.05` sensitivity run;
- GO BP enrichment, BH correction, explicit background (never the annotated genome);
- disease source CTD, with the exact disease term and retrieval date still to be recorded;
- SwissTargetPrediction exports are submitted **manually** by the researcher; never automated.

## Missing before this can be called a case

1. `inputs/disease_genes.txt` — exact CTD disease term, query, release, retrieval date, license
   evidence, SHA-256 and row count.
2. `inputs/stp/*.csv` — eight manual STP exports, per-compound retrieval/submission log, SHA-256 and
   service-terms evidence.
3. `inputs/hgnc_map.tsv` — complete HGNC release/date, hash and attribution/license evidence.
4. `expected/` — golden outputs only after the inputs are frozen and the full chain runs.
5. Case README with exact sources/queries/dates/licenses and a clear "not verified" statement.

No file above is marked verified or frozen, and no scientific result exists yet. The synthetic
quickstart is not a substitute.

## Where the case computation must run

Only in the verified Linux environment (GitHub Actions `r-contract` with `renv.lock` restore), not on
the Windows host, where a native R exit `0xC0000005` is still an open blocker. The CI run verifies
the machinery, not a public case. Once the missing inputs and license evidence exist, add them under
`inputs/`, record hashes, run the chain, and only then update `CASE-FREEZE.yaml` to `frozen`.
