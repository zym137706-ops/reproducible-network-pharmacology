# R enrichment contract fixture

`enrichment_result.tsv` is the first 100 rows of a real `Rscript R/ora.R` run on
`../input.json`, generated on 2026-10-18 with:

| Component | Version |
|---|---|
| R | 4.5.2 |
| clusterProfiler | 4.18.2 |
| DOSE | 4.4.0 |
| org.Hs.eg.db | 3.22.0 |

It is a **contract snapshot**, not a numeric golden file: Bioconductor releases
change p-values slightly, so the test asserts the schema (columns, ordering,
non-empty `geneID`, `Count == len(geneID)`), not float equality.

Full result was 1726 GO-BP terms for the 25-gene fixture input; only the top 100
are kept to keep the repository small.
