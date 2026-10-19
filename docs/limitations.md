# Limitations

Updated 2026-10-19. Implemented behavior and planned safeguards are distinguished below.
The accepted extension scope is documented in [ADR-0004](adr/0004-staged-upstream-and-docking.md).

This project is deliberately narrow. The most important limitations are listed here and in the
report template, so that a result cannot be read as more than it is.

## What the output means

- A network edge means: *the compound was predicted to hit this target, and the target is
  annotated to this disease.* It does **not** mean binding, activation/inhibition, direction of
  effect, tissue exposure, or efficacy.
- Over-representation answers: *are these genes annotated to this term more often than expected
  given the background?* It does not establish causality or mechanism.
- No output is experimental validation. Every report must say so.

## Analytic choices that change the answer

- **Probability threshold** (default recorded per run). Changing it changes the target set, the
  intersection and every downstream term. A sensitivity run is recommended.
- **Species and identifier type.** Human-only analysis by default; cross-species mapping is a
  separate decision, not a silent default.
- **Background/universe.** Using the whole annotated genome, the disease gene set, or the detected
  gene list gives different p-values. Current R input permits an omitted universe; a background
  mapping error can leave it NULL. Explicit actual-universe recording and failure handling remain
  release blockers, not completed safeguards.
- **Gene-set redundancy.** GO terms are nested; a "top 20" table often shows one biological theme
  twenty times. Collapse or annotate redundancy before interpreting.
- **Gene-symbol drift.** Retired symbols and aliases change results across database releases; the
  HGNC snapshot is recorded in the config.

## Data-source biases

- GeneCards, OMIM and CTD differ in coverage and in how literature is curated; a disease gene list
  built from one source is not a neutral truth.
- KEGG pathways carry their own curation bias and license restrictions; the repository does not
  redistribute KEGG data.
- Predicted targets from SwissTargetPrediction depend on the model version and on the submitted
  structure. A re-run months later may produce a different table; cache and date the export.

## Software limitations

- Enrichment depends on R and Bioconductor versions. The bridge records `clusterProfiler`,
  `DOSE` and OrgDb versions. Current tests check the result contract rather than numerical truth;
  independent synthetic hypergeometric/BH tests are required alongside live annotation checks.
- KEGG enrichment needs network access; offline runs use GO.
- The parser accepts the export formats observed in practice, not every possible spreadsheet.
  Unrecognised structures fail loudly with the columns it saw.
- Windows workstations may resolve `python` to Python 2.7 (MGLTools); the error is confusing but
  environmental, not a bug in this package.

## What this repository does not do

- no online prediction or website automation;
- no docking in v0.1; v0.3 design initially supports suitable co-crystal systems and ordinary
  noncovalent small molecules, with controls and pose QC;
- no ADMET modelling, QSAR, or generative design;
- no clinical or experimental claims;
- no redistribution of restricted reference databases.

## Upstream and docking interpretation (planned extensions)

- Processed metabolomics annotations and confirmed compound lists have different identity evidence.
  Accurate mass/formula agreement does not resolve isomers; MSI levels require actual evidence.
- Standardization is a documented representation policy, not proof of biological protonation state.
  Unknown stereochemistry and candidate identities remain unresolved unless supported.
- Ro5/alerts and optional ADMET outputs are annotations; explicit, versioned selection preserves
  all original candidates and reasons. Differences/abundance alone do not establish activity.
- High pLDDT does not prove a suitable binding pocket; predicted structures need local confidence,
  PAE, receptor-state and site evidence. Do not delete low-scoring regions mechanically.
- Redocking recovery, physical plausibility and activity discrimination are different checks.
  Top-1 and best-sampled RMSD must not be conflated. No native reference means not applicable.
- Same-receptor scores are exploratory comparisons under a consistent protocol, not measured
  affinity. Different targets/chemistries/protocols are not directly rankable by raw score.
- Fixed seeds help controlled repeatability only with the other inputs/parameters held fixed.
  Cross-version/platform equivalence needs measured tolerances; repeated seeds are not biological replicates.
- Historical inventory counts and previous test reports are not current validation evidence.
  Recheck commands/scripts/logs before concluding a runtime parameter was absent.
