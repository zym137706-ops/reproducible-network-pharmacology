# reproducible-network-pharmacology（可复现网络药理学工具包）

**[v0.2.0](https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/tag/v0.2.0)** 已于 2026-11-18 发布。

用 `rnp` 命令行工具把成分清单、SwissTargetPrediction 导出和疾病基因集变成成分–靶点网络、富集表和报告，
运行清单记录输入哈希和参数。可选 Agent 技能调用同一套 CLI，并引导人工审核。

- **快速试跑**可用[合成数据示例](#快速开始)。需要 Python 3.10+，富集请使用 Linux 和 R 4.5.x。
  [环境说明](docs/environment.md)
- **复现 RA 案例**可用[公开数据包与复现指南](examples/demo/DATA-ACCESS.md)。
- **查看 v0.2.0 功能**，包括登记已提交的结构、记录化合物选择决定和获取受体记录。
  [命令表](#已实现--计划中) · [变更记录](CHANGELOG.md)

## 为什么做这个

网络药理学结果难复现，不是因为方法复杂，而是因为决定结论的东西从来没被写下来：概率阈值、基因符号映射规则、数据库版本、精确输入文件。本项目把这些隐性决策显式化：

- **确定性内核**：解析、基因编号归一化、交集、网络表、富集全部由代码完成，可单独重跑。
- **默认溯源**：每次运行产出 `run_manifest.json`（工具版本、git commit、输入哈希、参考库版本、参数、时间）。
- **显式失败**：已知数据陷阱直接报错并给出修复建议，不静默跳过；R 进程非零退出即使留下正常 meta 也视为失败。
- **Agent 只在外层**：CLI 是唯一事实来源，SKILL.md 只负责编排、提问与解释。**不用任何 Agent 也能跑**。

## 快速开始

```bash
# 需要 Python 3.10+；富集功能另需 R 4.5.x（clusterProfiler / org.Hs.eg.db）
uv sync --locked --extra dev
# 结构模式（`rnp ingest compounds` 读含 `smiles` 列的化合物表、`scripts/case_run.py --log`）另需 RDKit：
# 加 `--extra chem`；没装时这些命令会报错并指出该 extra

# 恢复 R 锁，并使用脚本打印的精确绝对库路径
bash scripts/restore_r.sh
export R_LIBS="<上一步打印的 R_LIBS 路径>"

uv run rnp validate --config examples/quickstart/run.yaml
uv run rnp ingest stp --config examples/quickstart/run.yaml --run-id quickstart
uv run rnp intersect --config examples/quickstart/run.yaml --targets results/quickstart/targets.tsv
uv run rnp network --config examples/quickstart/run.yaml --intersect results/quickstart/intersect
uv run rnp enrich --config examples/quickstart/run.yaml --intersect results/quickstart/intersect
uv run rnp report --config examples/quickstart/run.yaml --run-dir results/quickstart
uv run rnp manifest --run-dir results/quickstart --check-inputs
uv run python scripts/synthetic_demo.py --out .demo
uv run pytest -q
```

自包含的 fixture 用于快速开始与测试。公开数据案例已完成本地双阈值计算、独立核查与候选复现，并已作为 v0.1.0 Release 资产发布；完整数据包与复现入口见 [examples/demo/DATA-ACCESS.md](examples/demo/DATA-ACCESS.md)，来源/许可记录见 [docs/public-case-sources.md](docs/public-case-sources.md)。

Windows 注意：确认 `python` 指向 Python 3。装了分子模拟工具的工作站常见 `python` 命中 MGLTools 的 Python 2.7，请用 `py -3.12` 或 `uv run`。

## 已实现 / 计划中

| 命令 | 状态 | 作用 |
|---|---|---|
| `rnp validate` | ✅ | 校验运行配置与所有声明的输入路径 |
| `rnp ingest stp` | ✅ | 解析 STP 的 xlsx/csv 导出（合并标题行、多符号靶点、复合体），产出 `targets.tsv` + 审计文件 |
| `rnp ingest compounds` | ✅ v0.2.0 | 登记化合物身份；化合物表有 `smiles` 列时同时登记结构（RDKit，可选 extra `chem`）和 STP 提交记录，把 `compound_structures.tsv`、`compounds_audit.json` 和清单写进 `<outputs.dir>/<run id>_compounds/`；没有登记到结构或提交记录被拒的行被隔离（退出码 3）；没有 `smiles` 列时为仅名称模式，不需要 RDKit；`rnp ingest stp --compounds DIR` 套用它的决定（被隔离化合物的导出同样被隔离，`compounds_registered.tsv` 多 `structure_id`、`structure_status` 两列）（[docs/upstream.md](docs/upstream.md) 第 8 节） |
| `rnp manifest` | ✅ | 校验已有 `run_manifest.json` 并检测输入哈希漂移 |
| `rnp intersect` | ✅ v0.1 | HGNC 归一化后的疾病交集；排除项与冲突写入审计表 |
| `rnp network` | ✅ v0.1 | Cytoscape 节点/边/MOLlist 表 + Venny 数据；`--venn-plot` 可选出图 |
| `rnp enrich` | ✅ v0.1 | 基于 R `clusterProfiler` 的分组 ORA，**必须显式背景**；完整检验表 + 显著性子表；无命中与服务失败分开 |
| `rnp mcode` | 🚧 后续独立扩展 | MCODE 模块富集；不由 hub/RRA 排名替代 |
| `rnp report` | ✅ v0.1 | 由已校验的阶段审计与表格生成 Markdown 报告；哈希校验；不超出证据作结论 |
| `scripts/case_run.py` | ✅ 本地案例入口 | 面向用户自备输入的可移植预检 + 全 CLI 链；记录源码/配置/容器溯源；给了 `--log` 时经 `rnp ingest compounds` 登记并核对结构（需要 RDKit，extra `chem`）；再给 `--selection`（需要 `--log`）时还套用决定表：每个化合物阶段之后运行 `rnp compounds select`，`ingest stp` 带 `--compounds --selection` |
| `scripts/case_check.py` | ✅ 独立核查 | 从结果表重新推导 T_r/前景并重算超几何/BH；给了提交日志时还从原始输入重新推导每个化合物的提交状态和导出哈希，与化合物阶段对照；给了 `--selection` 时从决定表重新推导每个化合物的选择状态和决定 ID，与选择阶段、登记表、ingest 审计、`targets.tsv` 和交集审计对照 |
| `rnp metabolites import` | 🚧 后续，不在 v0.2.0 | 已处理代谢组注释导入；同时支持已确认成分清单 |
| `rnp structures resolve` | 🚧 后续，不在 v0.2.0 | 把名称/InChIKey 解析为结构（PubChem 缓存） |
| `rnp compounds select` | ✅ v0.2.0 | 记录研究者对候选化合物的选择决定（`include` / `exclude` / `needs_review`，附理由码、规则版本和决定者）：读 `inputs.selection` 和 `rnp ingest compounds` 的阶段目录，把全候选表 `selection_decisions.tsv`、所选名单 `selected_compounds.tsv`、`selection_audit.json` 和清单写进 `<outputs.dir>/<run id>_selection/`；没有决定的候选是待审、不是纳入，有未决候选时阶段是 partial（退出码 3）；不写注册表；`rnp ingest stp --compounds DIR --selection DIR2` 只解析已选化合物的导出，其余记为 `not_selected`（审计 Schema 1.2，`compounds_registered.tsv` 多一列 `selection_status`），`rnp intersect`、`rnp network`、`rnp report` 随之只数已选化合物（[docs/upstream.md](docs/upstream.md) 8.11、8.12） |
| `rnp compounds annotate` | 🚧 后续，不在 v0.2.0 | 性质标注（Ro5、结构警示、可选 ADMET），与选择决定分开 |
| `rnp acquire` | ✅ v0.2.0（[ADR-0005](docs/adr/0005-structure-acquisition-boundary.md)） | 把所选 `PDB_ID:UNIPROT_ACCESSION`（PDB 编号只接受 4 位）的 RCSB/UniProt 记录冻结到新目录，并写出 `acquisition_record.json`（获取时间、HTTP 状态、大小、SHA-256、版本响应头）；`--verify DIR` 离线复核冻结目录；唯一在 Python 代码中联网的命令（`rnp enrich` 的可选 KEGG 富集由 R 联网，不在此列） |
| `rnp dock prepare/run/qc` | 🚧 v0.3 设计 | 合适共晶体系、普通非共价小分子、对照与姿势质控 |

## 输入契约

| 输入 | 格式 | 必需内容 | 说明 |
|---|---|---|---|
| 化合物表 | TSV/CSV | `name`（可选 `smiles`、`source`、`group`、`stp_file`） | 重名直接报错；`group` 拆分多组网络，`stp_file` 指定对应导出，否则按文件名匹配 |
| 选择决定表（`inputs.selection`，可选） | TSV/CSV | `compound`、`decision`（`include` / `exclude` / `needs_review`）、`reason_codes`、`rules_version`、`reviewer`；可选 `group`、`evidence_refs` | 由 `rnp compounds select` 读取，每个候选一行；首次运行 `rnp ingest compounds` 之前就要把路径写进运行配置（各阶段靠配置哈希串在一起）；`exclude` 和 `needs_review` 需要理由码；没有行的候选记为待审 |
| STP 导出目录 | `.csv` / `.xlsx` | 表头须出现在前 10 行内 | xlsx 首行是合并标题、第 2 行才是表头——已处理 |
| 疾病基因集 | 每行一个符号，或含 `gene` 列的 TSV | 基因符号 | 无法解析的符号直接中止；来源与日期写入配置 |
| HGNC 映射表 | HGNC complete-set TSV | `hgnc_id,symbol,status,prev_symbol,alias_symbol,uniprot_ids,entrez_id,locus_group` | 只索引 `Approved`；别名用 `|` 分隔 |
| MCODE 导出目录 | MCODE CSV | `name` 列 + 模块/分数列 | 容忍 `MCODE::Clusters (1)` 这类带后缀列名 |

## 已知失败模式（README 里的"坑清单"）

| 症状 | 常见原因 | 工具反应 |
|---|---|---|
| 找不到表头 | xlsx 合并标题行 / 导出格式不对 | 扫前 10 行；报错时列出看到的列名 |
| `Common name = N/A` | 复合/多蛋白靶点 | 记为警告，绝不拆成单个基因 |
| `Common name = "CDK5R1 CDK5"` | 一格多个符号 | 标 `multi_symbol_common_name`，不进单基因主表 |
| 概率非数值/越界 | 本地化小数逗号、导出损坏 | 该文件失败，审计记录具体行 |
| 结果表为空 | 无靶点过阈值 | 记为 `completed_no_predictions`，不算成功 |
| 符号不在 HGNC | 旧名/别名/物种不符 | 进 `gene_mapping_conflicts.tsv`，唯一映射才转换 |
| 一个符号对应两个基因（共享别名） | 歧义别名 | 不猜，留空并列出 `ambiguous_symbols` |
| 化合物名与基因符号相同 | Cytoscape 节点会合并 | `rnp network` 以退出码 2 中止，不静默合并 |

## 人工审核门

审核门是设计要求，尚未等同于已实现的交互式运行机制。复用已记录的研究者决定，仅对缺失或冲突的科学选择提问；上游身份/筛选和对接控制新增独立审核点。详见 [docs/review-gates.md](docs/review-gates.md)。

## 可复现性

已落地的基础：

1. 化合物↔导出绑定与隔离：未绑定的文件不会悄悄变成边。
2. 阶段状态（`complete` / `partial` / `empty` / `partial_override`）与父级审计/哈希链接；下游阶段拒绝不完整的上游，除非记录了覆盖。
3. 分开记录**代码身份**（本仓库版本/提交）和**配置身份**（配置路径、SHA-256 和配置所在仓库的状态）。
4. 通过持久化注册表得到稳定的 `compound_id`：显式 ID 优先保留并持久化，冲突的重新分配会被拒绝。
5. 机器可读表保留全精度概率，展示用的舍入另行处理。
6. 离线合成 demo，带手算预期值与失败场景。
7. `rnp report` 渲染前重新校验它读取的每个产物和父阶段审计哈希；缺失的阶段显示“未运行”，partial 阶段需要覆盖。
8. Python 依赖由 `uv.lock`（`uv sync --locked`）锁定；R 依赖由 `renv.lock` 锁定，CI 按该锁恢复（每次运行也记录实际版本）。
9. R 进程的非零状态不会被看起来正常的 meta 文件掩盖；引擎实际前景/背景集合连同哈希和计数一并写出。

v0.2.0 的上游切片另外做到：结构歧义只记录、不改写；STP 导出与提交的结构逐行绑定，案例核查器从原始输入独立重推；选择决定与全候选表分开保存，下游只数所选化合物。

详见 [架构与待闭合缺口](docs/architecture.md)、[案例复现记录](docs/public-candidate-reproduction-2026-10-28.md)和 [Skill 验收范围](docs/skill-acceptance.md)。

## 边界

核心处理**预测的**成分—靶点关联与富集，不宣称机制或疗效。v0.3 设计的对接首版限定合适共晶体系和普通非共价小分子；分别报告回对接恢复、姿势合理性和筛选能力，不以分数换算实验亲和力。

GeneCards、OMIM、KEGG 等受限数据库**不再分发**，只提供下载说明与适配器，用户按自身许可获取。详见 [docs/data-licenses.md](docs/data-licenses.md)。

## 路线图

| 版本 | 范围 | 状态 |
|---|---|---|
| v0.0.1 | 骨架：包、schema、CLI、测试、CI、文档 | ✅ 完成 |
| **v0.1.0** | `intersect` · `network` · `enrich`（R）· `report` · 运行溯源 · 公开案例 Release 资产 | **2026-11-02 已发布** |
| **v0.2.0** | 上游第一个切片（入口 A）：已确认化合物清单 → 结构登记 → STP 提交记录绑定 → 显式选择 → 案例入口独立复核；受体侧 `rnp acquire` | [2026-11-18 已发布](https://github.com/zym137706-ops/reproducible-network-pharmacology/releases/tag/v0.2.0) |
| v0.2.x / 后续 | 已处理代谢组注释入口、名称→结构解析、性质标注 | 计划中 |
| v0.3 | 最小对接：候选对、准备、控制、回对接与 pose QC | 计划中 |
| 后续 | PPI 拓扑/RRA、MCODE、预测结构和历史批量迁移 | 独立验收 |
| v1.0 | 稳定契约、兼容性与复现案例 | 按实际证据验收 |

先交付可验证核心，再扩展模块。契约变化需要显式版本迁移；路线图、视频或 DOI 不代替运行证据。
维护与试用记录见[项目规划](docs/project-plan.zh-CN.md)和[组内快速上手指南](docs/group-quickstart-zh.md)。

专项设计：[上游](docs/upstream.md)、[对接](docs/docking.md)、[ADR-0004](docs/adr/0004-staged-upstream-and-docking.md)、[ADR-0005](docs/adr/0005-structure-acquisition-boundary.md)。

## 许可

代码 MIT；参考数据各自沿用原许可，见 [docs/data-licenses.md](docs/data-licenses.md)。
