# Conditional enrichment background rule (pre-declared)

This rule was fixed before any enrichment result was seen. It does not use significance to choose a
background.

For each STP probability threshold `r` in {0.10, 0.05}:

1. Run ingest at threshold `r`; use the resulting `targets.tsv` **before** disease intersection.
2. Normalise every target symbol via the frozen HGNC map. Keep unique Approved symbols.
3. Exclude composite/multi-symbol target rows (they cannot be a single normalised target) and count
   them. Record unmapped/conflict counts.
4. `T_r` = the resulting set of unique targets.
5. Background = `T_r`.
6. Foreground = `T_r ∩ D`, where `D` is the normalised CTD disease gene set (Arthritis,
   Rheumatoid; MeSH D001172; direct marker/mechanism or therapeutic evidence only).
7. Generate and freeze `universe-0.10.txt` and `universe-0.05.txt` separately, with input hashes and
   mapping-loss metadata.

This is **conditional enrichment within predicted targets**, not enrichment against the whole
annotated genome. After GO annotation, `rnp enrich` records the effective background and annotation
mapping loss; those are not replaced to improve significance.

Generator: `scripts/build_case_background.py` (tested with a frozen synthetic rule fixture).
The actual `T_r` files cannot be generated until the eight manual STP exports exist.
