# reproducible-network-pharmacology

[![ci](https://github.com/zym137706-ops/reproducible-network-pharmacology/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/zym137706-ops/reproducible-network-pharmacology/actions/workflows/ci.yml)

**Reproducible network-pharmacology workflows — as a command-line tool and an agent skill.**

Turn a folder of prediction exports and a disease gene list into a **traceable, re-runnable**
compound–target–disease analysis. Every run records its inputs, reference-data versions, parameters
and hashes, and every output can be regenerated from a single config file.

> Status: **unreleased v0.1 development** (package version 0.0.1). Ingest, intersection and network
> commands have implementations hardened on 2026-10-19: explicit compound↔export binding, quarantine
> of unbound exports, separate parse-status taxonomy, upstream stage-state enforcement, stable
> compound IDs, code/config identity separation, an offline synthetic demo with hand-computed
> expectations, and the `rnp enrich` + `rnp report` CLIs (explicit background, complete tested-term
> table, hash-checked report rendering). The Skill and the **public scientific case** are still
> pending. Test/release status requires dated execution evidence. See the
> [maintained plan](docs/project-plan.zh-CN.md) and [next implementation slice](docs/next-steps-dsh.md).

---

## Why this exists

Network-pharmacology analyses are usually assembled by hand: click SwissTargetPrediction, download
a spreadsheet, copy gene symbols into Venn diagrams, run enrichment on a website. The result is
hard to reproduce because the things that decide the answer are never written down — the probability
threshold, the gene-symbol mapping, the database release, the exact input files.

This project makes those decisions explicit:

- **Deterministic core.** Parsing, gene-symbol normalization, set intersection, network tables and
  enrichment are code, not manual steps.
- **Provenance by default.** Each run writes `run_manifest.json`: tool version, git commit, input
  hashes, reference-data versions, parameters, timestamps.
- **Explicit failure.** Known data traps raise actionable errors instead of being silently skipped.
- **Agent layer on top, not inside.** The CLI is the source of truth; the skill only orchestrates,
  asks for human decisions and explains results. You can use the CLI without any agent.

## Pipeline

The diagram includes planned capabilities; the command table distinguishes current implementations.

```mermaid
flowchart LR
    A["Confirmed list / metabolomics annotations"] --> B["Structure registry and explicit selection"]
    B --> C["STP exports with submission provenance"]
    C --> D["Ingest and HGNC intersection"]
    E["Disease genes"] --> D
    D --> F["Network and enrichment"]
    D --> G["Optional STRING/PPI topology or modules"]
    F --> H["Reviewed compound-protein pairs"]
    G --> H
    H --> I["Prepared docking, redocking and pose QC"]
    F --> J["Report and provenance"]
    I --> J
```

## Quickstart

```bash
# Python 3.10+ and R 4.3+ (R only needed for enrichment)
uv venv && uv pip install -e ".[dev]"

# 1. check a config against the JSON Schema
uv run rnp validate --config tests/fixtures/run/run.yaml

# 2. bind compounds to exports and parse them into one audited table
#    (writes results/quickstart/ and results/registry/compound_registry.tsv)
uv run rnp ingest stp --config tests/fixtures/run/run.yaml --run-id quickstart

# 3. map genes, intersect with the disease set, and write Cytoscape tables
uv run rnp intersect --config tests/fixtures/run/run.yaml \
  --targets results/quickstart/targets.tsv
uv run rnp network --config tests/fixtures/run/run.yaml \
  --intersect results/quickstart/intersect

# 4. enrich with an explicit background (Rscript required)
uv run rnp enrich --config tests/fixtures/run/run.yaml \
  --intersect results/quickstart/intersect

# 5. render a Markdown report from the verified stage audits
uv run rnp report --config tests/fixtures/run/run.yaml \
  --run-dir results/quickstart

# 6. verify provenance
uv run rnp manifest --run-dir results/quickstart --check-inputs

# 7. offline synthetic demo: 5 scenarios with hand-computed expected tables
uv run python scripts/synthetic_demo.py --out .demo

# 8. tests
uv run pytest -q
```

The self-contained fixture is used for the quickstart and by the test suite. Each command refuses to
overwrite an existing output directory unless `--force` is passed. Downstream commands refuse an
incomplete upstream stage unless `--allow-partial` is passed, and the override is recorded in the
audit. Ingest creates a persistent compound-ID registry; a re-run reuses the same IDs.

The public-data case (`examples/demo/`) is still **not** a completed case: its data and license
checklist is in [docs/public-case-checklist.md](docs/public-case-checklist.md), and STP exports must
be produced by hand (see [examples/demo/inputs/README.md](examples/demo/inputs/README.md)). The
synthetic demo is an engineering test, not a scientific result.

Windows note: make sure `python` resolves to Python 3. A common trap on workstations with
molecular-modeling tools installed is `python` resolving to **MGLTools' Python 2.7**; use `py -3.12`
or `uv run` explicitly. See [docs/limitations.md](docs/limitations.md).

## Commands

| Command | Status | What it does |
|---|---|---|
| `rnp validate` | ✅ v0.0.1 | Validate a run config and every declared input path |
| `rnp ingest stp` | ✅ v0.1 hardened | Bind compounds to exports, parse xlsx/csv (merged title rows, multi-symbol targets, complexes) into `targets.tsv`; quarantine unbound exports; classify file status; stage status |
| `rnp manifest` | ✅ v0.0.1 | Validate a run manifest and detect drift in recorded input hashes |
| `rnp intersect` | ✅ v0.1 | HGNC-normalized intersection; refuses partial upstream by default; exclusions and conflicts in audit tables |
| `rnp network` | ✅ v0.1 | Cytoscape node/edge/MOLlist tables + Venny data; optional R Venn plot (`--venn-plot`); valid empty network for zero hits |
| `rnp enrich` | ✅ v0.1 | ORA via R `clusterProfiler` per group with an **explicit background**; complete tested-term table + significant view; distinct statuses for no-hit vs failure |
| `rnp mcode` | 🚧 later extension | Module enrichment from Cytoscape MCODE exports; independent of hub ranking |
| `rnp report` | ✅ v0.1 | Markdown report from verified stage audits + tables; hash-checked; no claims beyond the evidence |
| `rnp metabolites import` | 🚧 v0.2 | Import processed metabolomics annotations; confirmed compound lists also supported |
| `rnp structures resolve` | 🚧 v0.2.0 | Resolve names / InChIKeys to structures (PubChem cache) |
| `rnp compounds annotate/select` | 🚧 v0.2 design | Properties plus explicit inclusion/exclusion decisions; all original candidates retained |
| `rnp hubs compute` | 🚧 later extension | Centrality/rank aggregation; not a replacement for MCODE |
| `rnp dock prepare/run/qc` | 🚧 v0.3 design | Suitable co-crystal systems and ordinary noncovalent small molecules, controls and pose QC |

## Input contracts

| Input | Format | Required content | Notes |
|---|---|---|---|
| `inputs.compounds` | TSV/CSV | `name`; optional `compound_id`, `group`, `stp_file`, `submission_id`, `smiles`, `source` | Explicit `stp_file` is required unless `inputs.allow_filename_match: true` (a recorded compatibility mode); duplicate names/files are errors |
| `inputs.compound_registry` | TSV (optional) | persistent `compound_id` registry | Defaults to `<outputs.dir>/registry/compound_registry.tsv`; created on first run and reused afterwards |
| `inputs.stp_dir` | directory of `.csv` / `.xlsx` | STP export header somewhere in the first 10 rows | Exports not bound to a compound are quarantined, never turned into edges |
| `inputs.disease_genes` | one symbol per line, or TSV with `gene` | Gene symbols | Unresolved symbols abort the run; source and retrieval date live in the config |
| `inputs.hgnc_map` | HGNC complete-set TSV | `hgnc_id,symbol,status,prev_symbol,alias_symbol,uniprot_ids,entrez_id,locus_group` | Only `Approved` records are indexed; aliases split on `|` |
| `inputs.mcode_dir` | directory of MCODE CSVs | `name` column + cluster/score columns | Column suffixes such as `MCODE::Clusters (1)` are tolerated |

## Known failure modes (and what the tool does)

| Symptom | Likely cause | Tool response |
|---|---|---|
| Header not found | xlsx merged title row / wrong export | Scans first 10 rows; raises `InputError` listing the columns it saw |
| `common name = N/A` | composite / multi-protein target | Kept as a warning; never split into individual genes |
| `common name = "CDK5R1 CDK5"` | multiple symbols in one cell | Flagged `multi_symbol_common_name`, excluded from single-gene main table |
| Probability not numeric / out of 0–1 | localized decimal comma, corrupted export | Row counted as `rows_invalid` (never as below-threshold); file status becomes `partial` or `invalid_rows` |
| Empty result table | structurally valid export with no rows | `no_predictions`; a valid empty result, not a success with edges |
| All valid predictions below threshold | threshold too strict / weak predictions | `below_threshold`; stage still complete, zero edges |
| Export not listed in the compound table | stale or extra file | Quarantined with a reason; excluded from `targets.tsv` |
| Compound bound to a missing export | deletion / rename | Stage `partial`, exit 3, `missing_exports` recorded |
| Downstream sees a partial stage | incomplete ingest | Refused with exit 2 unless `--allow-partial`; override recorded in audit |
| Output directory already exists | repeated run | Refused; pass `--force` to replace (recorded) |
| Gene symbol not in HGNC | retired symbol, alias, species mismatch | Listed in `gene_mapping_conflicts.tsv`; mapped only when unique |
| Symbol resolves to two genes (shared alias) | ambiguous alias | Left unmapped with `ambiguous_symbols` listed; never guessed |
| Compound name equals a gene symbol | node collision in Cytoscape | `rnp network` exits with code 2 instead of silently merging nodes |

## Human-review gates

Review gates are design requirements, not a claim that an interactive gate engine is implemented.
Use already recorded researcher decisions; request only missing or conflicting scientific choices.
Upstream identity/selection and docking controls extend the core gates. See [review-gates](docs/review-gates.md).

## Reproducibility

Implemented in this slice:

1. Compound↔export binding and quarantine, so an unbound file cannot silently become an edge.
2. Stage status (`complete` / `partial` / `empty` / `partial_override`) and parent audit/hash links;
   downstream stages refuse incomplete upstream runs unless an override is recorded.
3. Separate **code identity** (this repository's version/commit) and **config identity** (config path,
   SHA-256, and the config repository's state).
4. Stable `compound_id` via a persistent registry; a rename keeps identity through the export binding.
5. Full-precision probabilities in machine-readable tables; presentation rounding is separate.
6. An offline synthetic demo with hand-computed expectations and failure scenarios.

Still required before calling v0.1 released:

- a generated Python lock file and a controlled R/Bioconductor/annotation environment record;
- a public scientific case (checklist in [docs/public-case-checklist.md](docs/public-case-checklist.md));
- recorded CI results and a wheel-install resource check (workflow is defined; it must run on GitHub).

See [architecture](docs/architecture.md) for current gaps and target contracts.

## Scope and limitations

This project analyzes **predicted** compound–target associations and **computes** enrichment. It
does not predict binding or claim mechanism or efficacy. Docking is an optional later module
(v0.3 design); initial support is limited to suitable co-crystal systems and ordinary noncovalent
small molecules. Redocking recovery, pose plausibility and screening discrimination are separate assessments.
A network edge means “this compound was predicted to hit this target, and this target is annotated
to this disease” — nothing more. See [docs/limitations.md](docs/limitations.md).

Restricted databases (GeneCards, OMIM, KEGG) are **never redistributed**. The tool ships download
instructions and an adapter; users obtain the data under their own license. See
[docs/data-licenses.md](docs/data-licenses.md).

## Roadmap

| Release | Scope | State |
|---|---|---|
| v0.0.1 | Scaffold: package, schemas, CLI, tests, CI, docs | ✅ done |
| **v0.1** | Core hardening (binding/quarantine, stage status, identity, synthetic demo) ✅; `enrich` ✅; `report` ✅; Skill · public case 🚧 | 🚧 current |
| v0.2 | Confirmed lists / metabolomics → structure registry → annotation → explicit selection | planned |
| v0.3 | Minimal docking: reviewed pairs, preparation, controls, redocking and pose QC | planned |
| Later | PPI topology/RRA, MCODE, predicted receptors and historical batch migration | independently scoped |
| v1.0 | Stable contracts, declared compatibility and reproducible cases | evidence-gated |

Ship the verifiable core before extensions. Schema changes require explicit versioned migration;
a roadmap, video or DOI is not evidence that a capability works. Detailed designs:
[upstream](docs/upstream.md), [docking](docs/docking.md), [ADR-0004](docs/adr/0004-staged-upstream-and-docking.md).

## 中文摘要

本项目把网络药理学的「成分 → 靶点 → 疾病 → 通路」分析，从手工点网站变成可校验、可复现的
命令行工具 + Agent 技能层。核心设计：**CLI 是唯一事实来源**（不用 Agent 也能跑），每个子命令
校验输入、显式报错、写审计文件；每次运行生成带哈希与版本信息的 `run_manifest.json`；公开数据
demo 将用可独立核验的预期结果守住数值；受限数据库不再分发。当前是未发布的 v0.1 开发状态
（包版本 0.0.1），新增设计不代表命令已实现。完整中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## License

Code: MIT. Reference data keeps its own license — see [docs/data-licenses.md](docs/data-licenses.md).
