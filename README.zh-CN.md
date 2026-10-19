# reproducible-network-pharmacology（可复现网络药理学工具包）

**把网络药理学分析从"手工点网站"变成"可校验、可复现、带人工审核节点"的命令行工具与 Agent 技能。**

输入：化合物清单 + SwissTargetPrediction 导出 + 疾病基因集。
输出：可追溯的交集表、Cytoscape 网络表、富集结果、报告，以及一份记录输入哈希、参考库版本、参数与工具版本的运行清单。

> 当前状态：**未发布的 v0.1 开发中**（包版本 0.0.1）。2026-10-19 已加固导入/交集/网络，并接通 `rnp enrich`
> （显式背景、完整检验表、状态分离）与离线合成 demo；报告、Skill 与公开科学案例仍待接通。测试状态以实际执行记录为准。
> 维护入口：[完整规划 v3](docs/project-plan.zh-CN.md)；[下一步任务](docs/next-steps-dsh.md)。

## 为什么做这个

网络药理学结果难复现，不是因为方法复杂，而是因为决定结论的东西从来没被写下来：概率阈值、基因符号映射规则、数据库版本、精确输入文件。本项目把这些隐性决策显式化：

- **确定性内核**：解析、基因编号归一化、交集、网络表、富集全部由代码完成，可单独重跑。
- **默认溯源**：每次运行产出 `run_manifest.json`（工具版本、git commit、输入哈希、参考库版本、参数、时间）。
- **显式失败**：已知数据陷阱直接报错并给出修复建议，不静默跳过。
- **Agent 只在外层**：CLI 是唯一事实来源，SKILL.md 只负责编排、提问与解释。**不用任何 Agent 也能跑**。

## 快速开始

```bash
# 需要 Python 3.10+；富集功能另需 R 4.3+（clusterProfiler / org.Hs.eg.db）
uv venv && uv pip install -e ".[dev]"

uv run rnp validate --config tests/fixtures/run/run.yaml
uv run rnp ingest stp --config tests/fixtures/run/run.yaml --run-id quickstart
uv run rnp intersect --config tests/fixtures/run/run.yaml --targets results/quickstart/targets.tsv
uv run rnp network --config tests/fixtures/run/run.yaml --intersect results/quickstart/intersect
uv run rnp enrich --config tests/fixtures/run/run.yaml --intersect results/quickstart/intersect
uv run rnp manifest --run-dir results/quickstart --check-inputs
uv run python scripts/synthetic_demo.py --out .demo
uv run pytest -q
```

自包含的 fixture 用于快速开始与测试。公开数据 demo（`examples/demo/`）排在第 2 周；其 STP 导出需手工提交，原因见 [examples/demo/inputs/README.md](examples/demo/inputs/README.md)。

Windows 注意：确认 `python` 指向 Python 3。装了分子模拟工具的工作站常见 `python` 命中 MGLTools 的 Python 2.7，请用 `py -3.12` 或 `uv run`。

## 已实现 / 计划中

| 命令 | 状态 | 作用 |
|---|---|---|
| `rnp validate` | ✅ | 校验运行配置与所有声明的输入路径 |
| `rnp ingest stp` | ✅ | 解析 STP 的 xlsx/csv 导出（合并标题行、多符号靶点、复合体），产出 `targets.tsv` + 审计文件 |
| `rnp manifest` | ✅ | 校验已有 `run_manifest.json` 并检测输入哈希漂移 |
| `rnp intersect` | ✅ v0.1 | HGNC 归一化后的疾病交集；排除项与冲突写入审计表 |
| `rnp network` | ✅ v0.1 | Cytoscape 节点/边/MOLlist 表 + Venny 数据；`--venn-plot` 可选出图 |
| `rnp enrich` | ✅ v0.1 | 基于 R `clusterProfiler` 的分组 ORA，**必须显式背景**；完整检验表 + 显著性子表；无命中与服务失败分开 |
| `rnp mcode` | 🚧 后续独立扩展 | MCODE 模块富集；不由 hub/RRA 排名替代 |
| `rnp report` | 🚧 v0.1 | 由结果与清单生成报告 |
| `rnp metabolites import` | 🚧 v0.2 设计 | 已处理代谢组注释导入；同时支持已确认成分清单 |
| `rnp structures resolve` | 🚧 v0.2 设计 | 结构注册、来源核验与转换历史 |
| `rnp compounds annotate/select` | 🚧 v0.2 设计 | 性质标注与显式选择；保留全部候选 |
| `rnp dock prepare/run/qc` | 🚧 v0.3 设计 | 合适共晶体系、普通非共价小分子、对照与姿势质控 |

## 输入契约

| 输入 | 格式 | 必需内容 | 说明 |
|---|---|---|---|
| 化合物表 | TSV/CSV | `name`（可选 `smiles`、`source`、`group`、`stp_file`） | 重名直接报错；`group` 拆分多组网络，`stp_file` 指定对应导出，否则按文件名匹配 |
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

已有基础包括 Schema、确定性排序、输入哈希和单元/契约测试。发布前仍需闭合：

1. 实际生成并验证 Python 锁文件和受控的 R/Bioconductor/注释环境。
2. 将参考文件及父产物绑定到哈希，不能只填写版本文字。
3. 定义阶段状态与溯源关系，默认阻止 incomplete/partial 进入正式下游。
4. 完成可独立核算的合成 demo 和超几何/BH 数值基准。
5. 在源码目录以外验证 wheel 安装后的 schemas/R 资源。
6. 记录实际测试通过、失败、跳过及支持平台，不沿用旧报告。

详见 [架构与待闭合缺口](docs/architecture.md)。

## 边界

核心处理**预测的**成分—靶点关联与富集，不宣称机制或疗效。v0.3 设计的对接首版限定合适共晶体系和普通非共价小分子；分别报告回对接恢复、姿势合理性和筛选能力，不以分数换算实验亲和力。

GeneCards、OMIM、KEGG 等受限数据库**不再分发**，只提供下载说明与适配器，用户按自身许可获取。详见 [docs/data-licenses.md](docs/data-licenses.md)。

## 路线图

| 版本 | 范围 | 状态 |
|---|---|---|
| v0.0.1 | 骨架：包、schema、CLI、测试、CI、文档 | ✅ 完成 |
| **v0.1** | `intersect` · `network` · `enrich`（R）· `report` · 运行溯源 · 公开 demo | 🚧 进行中 |
| v0.2 | 已确认清单/代谢组注释 → 结构注册 → 性质标注 → 显式选择 | 计划中 |
| v0.3 | 最小对接：候选对、准备、控制、回对接与 pose QC | 计划中 |
| 后续 | PPI 拓扑/RRA、MCODE、预测结构和历史批量迁移 | 独立验收 |
| v1.0 | 稳定契约、兼容性与复现案例 | 按实际证据验收 |

先交付可验证核心，再扩展模块。契约变化需要显式版本迁移；路线图、视频或 DOI 不代替运行证据。
专项设计：[上游](docs/upstream.md)、[对接](docs/docking.md)、[ADR-0004](docs/adr/0004-staged-upstream-and-docking.md)。

## 许可

代码 MIT；参考数据各自沿用原许可，见 [docs/data-licenses.md](docs/data-licenses.md)。
