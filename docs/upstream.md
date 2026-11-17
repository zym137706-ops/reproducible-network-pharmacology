# 上游导入、结构注册与显式选择（设计契约）

状态：2026-10-19 设计稿；2026-11-09 起入口 A 的最小切片有了 JSON Schema 和契约测试（第 8 节），2026-11-10 起有了库 `rnp.structures`，2026-11-11 起有了命令 `rnp ingest compounds`，2026-11-12 起 `rnp ingest stp --compounds` 接入它，2026-11-13 起案例入口 `scripts/case_run.py` 在给了提交日志时经由它们登记和核对结构，案例核查器 `scripts/case_check.py` 在给了提交日志时再从原始输入独立复核提交绑定，2026-11-15 起命令 `rnp compounds select` 记录选择决定，2026-11-16 起 `rnp ingest stp --selection` 只解析已选化合物的导出，`rnp intersect`、`rnp network` 和 `rnp report` 只数已选化合物，2026-11-17 起案例入口 `scripts/case_run.py --selection` 把选择接进案例链、`scripts/case_check.py` 独立复核选择（均未发布，见 8.11、8.12、8.13）。执行顺序见 [总规划](project-plan.zh-CN.md)。
实现时先增加 JSON Schema、跨表约束及正反例，再修改 CLI；不通过文档宣称接口已经可用。

## 1. 输入边界

入口 A：已确认成分清单，可附结构、数据库 ID、实验/文献证据和选择依据。
入口 B：已处理代谢组注释表，可附原上游筛选结果；不接原始质谱数据，不在此版本重建整套代谢组统计。
两类输入都进入同一个注册和选择接口，后续 STP 导入不依赖具体实验软件。

输入注释至少保留 source_record_id、source_file/hash、原始名称、可选 feature_id、样品/组及证据来源。
若有 m/z，明确极性、加合物、电荷、测量值/单位、分子式及质量类型；缺字段记 not_evaluated，不补猜。
差异结果明确 contrast、effect_size/type、pvalue、padj/method、样本/重复和上游方法来源；不把 VIP/差异当成药效证据。

## 2. 注册对象与关系

| 设计对象 | 关键字段 | 约束 |
|---|---|---|
| compound_registry | compound_id, display_name, source_record_refs, identity_status | 名称不是主键；未决候选不假装为确认身份 |
| compound_occurrences | occurrence_id, compound_id, sample/group, feature_id | 同一身份可跨组出现；多个峰不重复计成多个化合物 |
| structure_registry | structure_id, compound_id, original_structure, standardized_structure, stereo_status, tool/rules_version | 原始结构保留；同名异构体不合并；盐/混合物/永久电荷显式处理 |
| structure_transformations | transformation_id, input/output_structure_id, operation, params, software/version, decision_ref | 有向历史，不覆盖原结构；允许不执行某类标准化 |
| prediction_submissions | submission_id, compound_id, submitted_structure_id, species, model/source, job/url/date, export_file/hash, verification_status | 同任务复用有明确身份/物种/模型条件；缺来源不能称为结构已核验 |
| selection_decisions | decision_id, compound_id, structure_id, decision, reason_codes, rules_version, evidence_refs, reviewer/method | include/exclude/needs_review；保留全候选；变更规则形成新决策 |
| ligand_states（对接扩展） | ligand_state_id, structure_id, protonation/tautomer, stereo, preparation_protocol | 不把注册标准化形式当作唯一生理状态；构象用 conformer_id 区分 |

ID 是持久注册 ID；不得由当前行号/排序重建。结构派生键附工具和规则版本；
重算产生新结构时保存关系，不覆盖旧 ID。单凭名称、连接性 InChIKey 前缀或质量不能合并立体异构体。
多个结构候选可以并存；未决身份与已确认结构分开，默认不进入要求确定结构的下游计算。

## 3. 核验、标注、选择分开

1. 核验输入可解析性、名称/结构/数据库记录对应、分子式/质量、立体与鉴定证据。
2. 性质标注输出数值、单位、算法版本和状态；Ro5/警示不是自动的淘汰依据。
3. 可选 ADMET 结果另存预测方法、版本、端点定义、单位及适用范围；未运行不能填阴性。
4. 根据给药途径、暴露、研究问题等预先声明规则，输出显式选择结果及理由。
5. 生成全候选、selected、excluded、needs_review 和审计；任何清单都能追溯至原始行。

原始记录、性质标注和最终纳入是不同产物。人工可以决定排除，但不能无记录删除。
找不到 PubChem/多个匹配/结构非法/未定手性/模型不支持，分别记状态；不自动取搜索第一条。
在线查询可缓存，记录来源、时间、完整响应或适用许可下的响应摘要与哈希；离线复算依赖冻结结果。

## 4. 质量与置信度

理论离子 m/z 的计算包含加合物、离子电荷、多聚体/中性损失及质量约定；
同时记录 ppm 公式、符号和仪器/方法容差。没有必要字段时不计算“通过”。
质量一致只是排错证据，不能鉴定位置异构体/立体异构体。
MSI 等级按已有证据填写，附标准品、RT、MS/MS 等来源；算法不得因质量命中提升等级。
PubChem 名称匹配仅产生候选来源，不新增实验鉴定证据。

## 5. 与现有核心的迁移

当前 name/group/stp_file 输入仍可使用；实现迁移时给出稳定 ID 对照和警告，不静默破坏旧 fixture。
正式模式要求名单与导出绑定；无法匹配的 source_file 隔离并写原因，不创建 unmapped 正式成分。
按文件名回退仅为显式兼容模式；记录未验证范围，并限制进入需要结构证据的环节。
同一成分跨组复用预测文件需用关联表表达，不能因重复 stp_file 复制身份或无条件拒绝合法复用。
去重按具体提交/模型/物种/结构作用域进行；跨任务不直接取最高概率。
Cytoscape 后续以 compound:<id>、gene:<id>、disease:<id> 连接，Label 与 ID 分离；迁移有碰撞与组间复用测试。

## 6. 实现验收

- 同名不同异构体不误合并；不同名称的同一注册实体可显式关联。
- 加合物/同位素/重复 feature 保留来源关系，不虚增化合物数。
- 未定结构、非法 SMILES、永久电荷、盐与混合物有可核查状态。
- 规则变更可重算选择而不重新导入或修改原始证据。
- STP 提交结构与对接结构有映射；转换导致的差异可见，不声称相同模型结果自动适用所有状态。
- 同化合物跨组、同任务复用、未匹配导出及名单中无结果成分均有测试。
- 新 Schema 覆盖每个实际产物，表间外键/唯一性由跨表校验补足；不是只有列名检查。

## 7. 方法依据

[MSI 标准](https://pmc.ncbi.nlm.nih.gov/articles/PMC3772505/)；
[RDKit 标准化接口](https://www.rdkit.org/docs/source/rdkit.Chem.MolStandardize.rdMolStandardize.html)；
[Meeko 配体准备](https://meeko.readthedocs.io/en/develop/lig_prep_basic.html)。

## 8. 入口 A 最小切片的契约（2026-11-09 Schema 和契约测试；2026-11-10 库；2026-11-11 命令 `rnp ingest compounds`；2026-11-12 `ingest stp --compounds`；2026-11-13 案例入口；2026-11-13 案例核查器的绑定复核；2026-11-15 选择决定 `rnp compounds select`；2026-11-16 `ingest stp --selection`；2026-11-17 案例入口的选择）

本节把第 2、3、6 节落到入口 A 的第一个可实现切片。命令 `rnp ingest compounds`（2026-11-11 起，未发布）读写下列产物，
并用库 `rnp.structures`（`src/rnp/structures/`）完成登记、绑定和校验；这些产物有 JSON Schema（`schemas/`）和契约测试
（`tests/unit/test_entry_a_schemas.py`）。表格产物是 TSV：“行 Schema”描述一行（单元格已去首尾空白，空单元格是空字符串），
`properties` 的顺序就是列顺序。

### 8.1 模式与产物

| 产物 | 位置 | 作用 | Schema |
|---|---|---|---|
| 提交日志（输入，可选） | `inputs.submission_log` 指向的 TSV | 研究者记录实际提交给 STP 的结构、物种、日期和导出文件 | `submission_log_row` |
| 结构注册表（持久） | `outputs.dir/registry/structure_registry.tsv`，与 `compound_registry.tsv` 并列 | 每个化合物登记过的结构及其派生标识 | `structure_registry_row` |
| 化合物—结构表（阶段输出） | `results/<run_id>/compound_structures.tsv` | 每条输入化合物行的结果；后续阶段按它取结构和提交状态 | `compound_structures_row` |
| 阶段审计 | `results/<run_id>/compounds_audit.json` | 模式、输入哈希、工具与规则版本、计数、逐行问题 | `compounds_audit` |

两种模式：`compounds.tsv` 有 `smiles` 列是结构模式（`identity_mode: structure`）；没有则是名称模式（`name_only`），
沿用 v0.1 的名称身份，不登记结构，也不能配置提交日志（表级错误）。`compounds.tsv` 不新增列：`smiles` 是研究者确认、
实际提交的结构；`pubchem_cid`、`source` 等只记录，不联网核对；结构的来源写在提交日志的 `structure_source` 列。
填好的提交日志——仓库模板 `examples/demo/inputs/STP-SUBMISSION-LOG.tsv` 的 12 列，或 RA 案例包里已完成日志的
22 列——原样合法，只新增两个可选列 `export_kind`、`result_rows`。

### 8.2 身份规则

- `structure_id`（`STRnnnn`）和 `compound_id` 一样是持久注册 ID，不由行号或排序重建。身份键是（`compound_id`，登记的
  原始 SMILES 字符串）：同一化合物的字符串变了就新建 `structure_id`，旧的标 `superseded` 并指向新的，旧提交仍指向
  旧 ID；改回旧字符串则恢复旧 ID 为 `current`。
- 原始字符串只去首尾空白，不做任何改写：不去盐、不中和、不加或去手性、不合并互变异构体（`standardization` 恒为
  `not_performed`）。SMILES 内不得含空白。
- 立体状态由 RDKit 的 `FindPotentialStereo`（四面体与双键立体合并）判定：`none_present`（没有立体元素）、`defined`
  （全部已指定）、`partially_defined`、`undefined`（全部未指定）；`stereo_elements_specified` 和
  `stereo_elements_total` 记录两个计数。工具与版本写进每条记录；口径可能随版本变化。
- 不同化合物登记了相同的完整 InChIKey：不合并、不拒绝，发 `shared_structure` 警告；连接性块（InChIKey 前 14 位）相同
  而完整键不同：发 `same_connectivity_different_stereo` 警告。绝不凭名称、InChIKey 前缀或质量合并立体异构体。
- 盐或混合物（`fragment_count` 大于 1）和带电结构只发警告（`multi_fragment`、`charged_structure`），不改写。

### 8.3 提交绑定

- 提交日志的每一行以 `stp_file` 对应一条输入化合物行，逐项核对：名称（日志的 `compound` 非空时须与化合物表一致）；
  `pubchem_cid`（两边都非空时须一致）；`submitted_structure` 与登记的 SMILES 字符串逐字相等；`species` 与运行配置
  一致（`Homo_sapiens` 对应 `Homo sapiens`）；导出文件存在；`result_sha256` 非空时等于实算的 SHA-256。任何一项不符
  都是 error，该行被隔离，提交状态为 `rejected`。
- 提交状态：`verified`（全部通过，`export_kind` 为 `native_export`）、`verified_kind_unstated`（全部通过，没有声明
  `export_kind`）、`reconstructed`（全部通过，`export_kind` 为 `reconstructed_from_result_page`，核验状态不高于此）、
  `not_recorded`（结构已登记但没有提交记录，不得称“可追溯至 STP 实际提交结构”）、`rejected`、`not_checked`（结构没有
  登记，日志行未评估）、`not_applicable`（名称模式）。
- 从结果页重建的导出（`reconstructed_from_result_page`）必须在日志里保留不是 `not_saved` 的 `job_id` 和完整行数
  `result_rows`；原生导出的 `result_rows` 可选。日志没有声明 `result_sha256` 不算错误，记 `submission_hash_not_declared`
  警告，实算哈希仍写入 `compound_structures.tsv`。日志里对应不到任何化合物行的行，记 `log_row_without_compound` 警告。
- 读表与清洗：表格按 UTF-8 读取（容忍 BOM），分隔符按表头行判定（制表符不少于逗号时取制表符），空行跳过，短行补空，
  比表头列数多的行是错误。化合物表的 `name`、`group`（缺省 `all`）、`stp_file`、`pubchem_cid` 做空白折叠（不换行空格视为
  空格，连续空白合成一个）；`smiles` 和日志里的每个单元格只去首尾空白。名称、`stp_file`、`pubchem_cid`、`smiles` 的比较都在
  清洗之后进行。这些规则写在这里，是为了让案例核查器（8.10）不引用结构库也能独立复刻本节的绑定。

### 8.4 行状态、阶段状态和问题代码

`compound_structures.tsv` 的 `row_status`：`accepted`（可进入下游）、`quarantined`（隔离，不进入要求确定结构的下游）、
`name_only`（名称模式）。隔离只有两个原因：结构没有登记（`structure_status` 为 `not_registered`），或提交被拒绝。
阶段状态：没有隔离行是 `complete`，有则是 `partial`（退出码 3）。表级问题（缺列、重复键、冲突、结构模式下没有安装
RDKit）整体拒绝，退出码 2，什么都不写。

问题代码是稳定的词表；审计的 `issues` 和表里的 `issue_codes`（排序、去重、分号连接）只使用它们：

| 级别 | 代码 | 含义 |
|---|---|---|
| error | `missing_structure` | 结构模式下 `smiles` 为空 |
| error | `invalid_smiles` | RDKit 无法解析 |
| error | `submission_structure_mismatch` | 日志的 `submitted_structure` 与登记的 SMILES 不相等 |
| error | `submission_hash_mismatch` | 声明的 `result_sha256` 与导出文件的实算哈希不符 |
| error | `submission_species_mismatch` | 日志的物种与运行配置不符 |
| error | `submission_export_missing` | 导出文件不存在 |
| error | `submission_name_mismatch` | 日志的化合物名与化合物表不符 |
| error | `submission_cid_mismatch` | 日志与化合物表的 `pubchem_cid` 不符 |
| warning | `shared_structure` | 另一个化合物登记了相同的完整 InChIKey |
| warning | `same_connectivity_different_stereo` | 连接性块相同而完整键不同 |
| warning | `stereo_undefined` | 立体状态为 `partially_defined` 或 `undefined` |
| warning | `multi_fragment` | 片段数大于 1 |
| warning | `charged_structure` | 净电荷不为 0 |
| warning | `smiles_whitespace_trimmed` | 登记时去掉了首尾空白 |
| warning | `structure_changed` | 化合物的结构字符串变了，已新建 `structure_id` |
| warning | `structure_reactivated` | 化合物改回了旧字符串，旧 `structure_id` 恢复为 `current` |
| warning | `submission_record_missing` | 结构已登记，但没有提交记录 |
| warning | `submission_export_reconstructed` | 导出是从结果页重建的 |
| warning | `submission_hash_not_declared` | 日志没有声明 `result_sha256` |
| warning | `log_row_without_compound` | 日志行对应不到任何化合物行（只出现在审计里） |

### 8.5 由库补足的跨表校验

Schema 表达不了的约束由库实现并测试：

- 注册表：`structure_id` 唯一；每个 `compound_id` 至多一个 `current`；`superseded_by` 指向同一化合物的已登记 ID；
  `connectivity_block` 等于 `inchikey` 的前 14 位；两个立体计数与 `stereo_status` 相符（`defined` 时已指定数等于总数，
  `partially_defined` 时小于总数）；`first_seen_utc` 不晚于 `last_seen_utc`。
- 化合物—结构表：行数和顺序与输入一致；`structure_id` 在注册表里并属于该 `compound_id`，`smiles`、`inchikey`、
  `stereo_status` 与注册表一致；`issue_codes` 排序且不重复。
- 审计：`summary` 的各项计数与表一致；`compound_structures_sha256` 等于表的实际哈希；每个 error 级问题对应一条隔离行。
- 输入：提交日志的 `stp_file` 不重复，化合物表的 `stp_file` 不重复（沿用 v0.1 的拒绝规则）。

### 8.6 本切片不做，以及状态

不做：入口 B、性质标注、联网查询、结构标准化、“提交结构与当前结构不同但研究者显式接受”、跨组出现表、配体态。
状态：设计、Schema 和契约测试已完成（2026-11-09）；库 `rnp.structures` 和命令 `rnp ingest compounds` 已实现、未发布
（2026-11-10、2026-11-11）。命令把阶段输出写进 `<outputs.dir>/<run_id>_compounds/`，`run.schema.json` 有了新键
`inputs.submission_log` 和 `inputs.structure_registry`；结构模式下运行命令需要可选依赖 `chem`（见 8.7）。
`rnp ingest stp --compounds`（下游接入）已实现、未发布（2026-11-12，见 8.8）；案例入口 `scripts/case_run.py` 给了提交日志时经由它们核对结构，已实现、未发布（2026-11-13，见 8.9）；案例核查器 `scripts/case_check.py` 给了提交日志时从原始输入独立复核提交绑定，已实现、未发布（2026-11-13，见 8.10）；选择决定表 `rnp compounds select` 和它在 `rnp ingest stp --selection` 里的接入已实现、未发布（2026-11-15、2026-11-16，见 8.11、8.12）；案例入口对选择的接入也已实现、未发布（2026-11-17，见 8.13）。

### 8.7 命令 `rnp ingest compounds`（2026-11-11；未发布）

`rnp ingest compounds --config run.yaml [--force]`：对 `inputs.compounds` 的每一行登记化合物身份（沿用 v0.1 的名称注册表）；
表里有 `smiles` 列时进入结构模式，登记结构并核对 `inputs.submission_log`。

- **输入：**`inputs.compounds`、`inputs.stp_dir`（给了日志才用来核对导出）、`species`、可选的 `inputs.compound_registry` 和
  `inputs.allow_filename_match`；新增可选的 `inputs.submission_log`（TSV）和 `inputs.structure_registry`（默认
  `<outputs.dir>/registry/structure_registry.tsv`）。名称模式（表里没有 `smiles` 列）下配置这两个新键是表级错误。
- **输出：**阶段目录 `<outputs.dir>/<run_id>_compounds/`（默认 run_id 是 UTC 时间戳加配置哈希前 8 位，再加 `_compounds`）里有
  `compound_structures.tsv`、`compounds_audit.json`、`run_manifest.json`；两个注册表在阶段目录就位之后才写。表和审计里没有时间戳。
- **退出码：**0 完成；3 部分（有隔离行，输出已写）；2 表级或输入错误（什么都不写，注册表也不动），包括结构模式下没有安装 RDKit；
  1 内部错误。
- **RDKit：**结构模式需要可选依赖 `chem`（审计要写 RDKit 版本）；名称模式不需要。
- `rnp ingest stp --compounds DIR` 读这个阶段的输出（见 8.8）；不带 `--compounds` 的 `ingest stp` 与以前完全一样。

### 8.8 命令 `rnp ingest stp --compounds DIR`（2026-11-12；未发布）

`rnp ingest stp --config run.yaml --compounds DIR [--force]`：`DIR` 是 `rnp ingest compounds` 的阶段目录。给了它，
`ingest stp` 在 v0.1 的基础上多做三件事；不给它，`ingest stp` 的产物与以前逐字节相同（名称模式的回归测试锁着这一点）。

- **隔离：**阶段表里 `row_status` 为 `quarantined` 的化合物，它的导出不解析、不进 `targets.tsv`，在 `stp_audit.json`
  里记为 `status: quarantined`、`reason: compound_quarantined`（带 `compound_id` 和 `group`），也出现在审计的 `quarantine`
  里；只要有这样的化合物，阶段就是 `partial`（退出码 3）。所有化合物都被隔离时没有可用的导出，是表级错误（退出码 2）。
- **结构列：**阶段是结构模式时，`compounds_registered.tsv` 末尾多两列 `structure_id`、`structure_status`；名称模式的阶段不加列。
- **记录：**`run_manifest.json` 的 `parents` 多一项 `ingest compounds`（`dir`、`audit`、`audit_sha256`、`stage_status`，
  `status_override` 为 `false`），`args` 多 `compounds`，`inputs` 末尾多阶段的审计和表。`stp_audit.json` 的 Schema 不变
  （仍是 1.1，没有 `parents`，`rnp report` 因此照旧），`notes` 多一条 `compounds_stage_applied`。
- **阶段必须是当前的**，否则表级错误（退出码 2，什么都不写）：目录和审计存在且合 `compounds_audit` Schema；审计记录的
  运行配置哈希等于现在的；表的哈希等于审计里的 `compound_structures_sha256`，且每行合 `compound_structures_row` Schema；
  审计记录的化合物表哈希等于现在 `inputs.compounds` 的；阶段里每行的 `compound_id`、`group`、`name`、`stp_file` 等于现在
  登记出来的；提交已被核对过（`verified`、`verified_kind_unstated`、`reconstructed`）的导出，现在文件的 SHA-256 仍等于阶段
  记录的 `export_sha256`（被隔离的化合物不查）。任何一条不成立，都要重新运行 `rnp ingest compounds`。

### 8.9 案例入口 `scripts/case_run.py`（2026-11-13；未发布）

给了 `--log` 时，案例入口把结构核对交给入口 A 的命令，不再自己逐项比对；不给 `--log` 的行为与以前相同，不运行化合物阶段，
也不需要 RDKit。

- **预检分两层。**文件层（不需要 RDKit，沿用旧消息）：化合物表的必需列、名称和 `stp_file` 不重复、STP 目录的文件集合等于绑定集合、
  日志的必需列、日志行数和 `stp_file` 集合与化合物表一致、两边的 `pubchem_cid` 非空、化合物的 `smiles` 非空、`submission_id` 一致。
  结构层：在系统临时目录里，用与正式运行相同的输入和配置（多一个 `inputs.submission_log`）真跑一遍 `rnp ingest compounds`，再按案例
  策略判定；临时目录用完即删，输出目录不受影响，预检不过时输出目录不创建。
- **案例策略 `case-log-policy-v2` 比命令严格。**命令的 8 个错误代码都致命；3 个警告（`submission_record_missing`、
  `submission_hash_not_declared`、`log_row_without_compound`）在案例里也致命；每个化合物的提交状态必须是 `verified`、
  `verified_kind_unstated`、`reconstructed` 之一；其余警告（`stereo_undefined`、`multi_fragment`、`charged_structure`、
  `shared_structure` 等）只记录。策略给 `compounds_audit` Schema 里的每个问题代码和 `compound_structures_row` Schema 里的每个提交状态
  归类；核心新增代码而策略没有归类时，契约测试失败。
- **链。**每个阈值：`ingest compounds --run-id run`（阶段目录 `<out>/<阈值>/run_compounds`）→ `ingest stp --compounds <阶段目录>` → ……；
  每个阈值最后对阶段目录多做一次 `manifest --check-inputs`。阶段失败记为 `failed_stage: ingest_compounds`。
- **记录。**`case_provenance.json` 的 `inputs.log` 多 `verified_by`、`policy`；`inputs.structures` 记模式、RDKit 版本、提交状态计数和问题代码
  计数；链跑完阶段后 `inputs.compounds_stage` 记每个阈值的目录和审计、表的 SHA-256。`case_provenance` 的 Schema 不变（`inputs` 是自由对象）。
- **比旧版更严：**RDKit 解析不了的 SMILES、含空白的 SMILES、缺 `submitted_date` 列的日志，现在被拒绝。
- **需要 RDKit。**给了 `--log` 的案例需要可选依赖 `chem`；没有时预检以退出码非 0 失败，并原样带出命令的安装提示。

### 8.10 案例核查器的绑定复核 `scripts/case_check.py`（2026-11-13；未发布）

给了提交日志时，案例核查器在原有的集合与统计复核之外，再从原始输入独立复核每个阈值的化合物阶段；不给时一字不变。

- **选项。**`--compound-table`（化合物表）、`--stp-dir`、`--log`、`--species`（运行配置的 `species`，如 `Homo_sapiens`）和
  `--stage LABEL=DIR`（每个 `--run` 一个，标签相同）：要么全给，要么全不给；只给一部分时退出并指名缺哪几个。
  `scripts/case_run.py` 给了 `--log` 时传入它们，核查通过后把 `inputs.log.binding_recheck`（`tool`、`rule`、`result: passed`）
  写进 `case_provenance.json`。
- **独立。**绑定复核只用标准库，不导入 `rnp.structures`、`rnp.analysis` 或 RDKit；读表与清洗规则见 8.3。
- **推导。**对化合物表的每一行（按行序），按 8.3 的规则从日志、导出文件和 `species` 推出提交状态、`export_kind` 和
  `export_sha256`：没有 `smiles` 的行是 `not_checked`，没有日志行的行是 `not_recorded`，有任何不符的行是 `rejected`（原因按
  `compound`、`pubchem_cid`、`submitted_structure`、`species`、`stp_file`、`result_sha256` 的顺序列出）。
- **比对。**每个阈值：阶段表的行数、顺序和每行的 `name`、`group`、`stp_file`、`smiles`、`submission_status`、`export_kind`、
  `export_sha256` 与推导一致；审计里的输入哈希和行数、`files_hashed`、`compound_structures_sha256`、`summary` 的各个计数与推导和
  实算一致；`compounds_registered.tsv` 的 `name`、`group`、`stp_file` 与化合物表一致，`compound_id`、`structure_id`、
  `structure_status` 与阶段表一致，`stp_audit.json` 的 `compounds_registered_sha256` 等于实算；各阈值的阶段表逐字节相同。
  结构层（`structure_id`、`inchikey`）要 RDKit 才能重算，这里只检查格式和不重复。
- **案例策略。**复核自己再执行一遍：每个化合物的推导状态必须是 `verified`、`verified_kind_unstated` 或 `reconstructed`，没有
  缺日志行、没有无化合物的日志行，日志声明了 `result_sha256`；每一行的 `row_status` 是 `accepted`、`structure_status` 是
  `registered`；审计的 `identity_mode` 是 `structure`、`stage_status` 是 `complete`、`summary.errors` 是 0。
- **输出。**每个问题一行，格式 `<阈值>: <文件>: [entry '<名称>' (<stp_file>) ]<字段>: expected <值> from <来源>, found <值>`，
  全部问题一次报出；有问题时退出码非 0，且不写 `independent-check.json`。通过时 `independent-check.json` 多一个键 `bindings`
  （`rule: case-binding-recheck-v1`、化合物表和日志的哈希、行数、各提交状态的计数、比对的列、每个阈值的阶段表哈希）。

### 8.11 选择决定 `rnp compounds select`（2026-11-15；未发布）

`rnp compounds select --config run.yaml --compounds DIR [--force]`：`DIR` 是 `rnp ingest compounds` 的阶段目录。研究者在决定表里为
每个候选化合物写下纳入、排除或待审，命令把全候选和所选名单分开保存。“所选”只表示按研究者的记录决定保留用于分析，不表示活性、药效
或任何验证；命令不看化合物的性质，也不替研究者判断。`rnp ingest stp --selection` 读取它（见 8.12）。

- **输入。**新的可选输入 `inputs.selection`（TSV 或 CSV；`run.schema.json` 有这个键，`rnp validate` 检查文件存在）。每个候选化合物一行，
  列：`compound`（名称）、`group`（缺省 `all`）、`decision`（`include`、`exclude` 或 `needs_review`）、`reason_codes`、`rules_version`、
  `reviewer`、`evidence_refs`；必需列是 `compound`、`decision`、`reason_codes`、`rules_version`、`reviewer`，其余列忽略并记入审计的 `notes`。
  读表规则同 8.3；`compound`、`group`、`rules_version`、`reviewer`、`evidence_refs` 做空白折叠，`decision` 和 `reason_codes` 只去首尾空白。
  按（名称，组）对应化合物：名称用 `name_key`（大小写和标点不敏感）比较，组逐字比较；同一（名称，组）两行是表级错误。`reason_codes` 是
  分号分隔的代码（小写字母开头，字母、数字、下划线；词表由研究者自定），输出时排序、去重；`exclude` 和 `needs_review` 至少要有一个。
  `rules_version`（预先声明的规则的版本名）和 `reviewer`（谁、或什么方法做的决定）每行必填。决定表的路径要在第一次 `rnp ingest compounds`
  之前写进 run.yaml：阶段之间用 run.yaml 原始字节的哈希认亲，之后只改决定表的内容。
- **输出。**阶段目录 `<outputs.dir>/<run_id>_selection/`：`selection_decisions.tsv`（每个候选一行，顺序同化合物表，一个都不丢）、
  `selected_compounds.tsv`（其中 `selection_status` 为 `selected` 的行）、`selection_audit.json`、`run_manifest.json`。表和审计里没有时间戳。
  命令不写任何注册表，不碰化合物阶段目录；改了决定，只重跑这一步。化合物阶段必须是当前的（沿用 8.8 的核对）。
- **推导。**`selection_status` 由化合物阶段的 `row_status` 和决定推出：

  | 化合物阶段 `row_status` | 决定 | `selection_status` | 问题代码 |
  |---|---|---|---|
  | `accepted` 或 `name_only` | `include` | `selected` | — |
  | `accepted` 或 `name_only` | `exclude` | `excluded` | — |
  | `accepted` 或 `name_only` | `needs_review` | `needs_review` | — |
  | `accepted` 或 `name_only` | 没有决定 | `needs_review`（生成的一行，`decision_source` 为 `not_recorded`） | `no_decision_recorded` |
  | `quarantined` | `include` | `quarantined` | `include_blocked_by_quarantine` |
  | `quarantined` | `exclude` | `excluded` | `quarantine_resolved_by_exclusion` |
  | `quarantined` | `needs_review` | `quarantined` | — |
  | `quarantined` | 没有决定 | `quarantined`（生成的一行） | `no_decision_recorded` |

- **决定 ID。**`decision_id` 由决定的内容算出：`DEC-` 加 12 位十六进制，取 `compound_id`、`structure_id`、`decision`、`decision_source`、
  `reason_codes`、`rules_version`、`reviewer`、`evidence_refs` 以 U+001F 连接后的 SHA-256 的前 12 位。同一内容永远同一个 ID，与行序和运行
  次数无关；任何一项变了就是新 ID。没有跨运行的持久决定登记表：历史靠每次运行各自的阶段目录和研究者自己保存的决定表。
- **问题代码**（稳定词表，审计的 `issues` 和表里的 `issue_codes`；都是警告）：`no_decision_recorded`、`include_blocked_by_quarantine`、
  `quarantine_resolved_by_exclusion`（这三个也出现在表的 `issue_codes` 里）；`decision_without_compound`（决定表里对应不到任何候选的行，
  只在审计里）；`no_compound_selected`（没有任何候选被选中，只在审计里）。
- **阶段状态与退出码。**每个候选都是 `selected` 或 `excluded` 时阶段是 `complete`（退出码 0）；有 `needs_review` 或 `quarantined` 时是
  `partial`（退出码 3，输出已写，打印的摘要列出 `unresolved`）；决定表或化合物阶段有表级问题时退出码 2、什么都不写；内部错误 1。没有决定的
  候选是待审，不是纳入。
- **不做。**性质标注和按性质自动判定、联网、跨运行的决定登记表。

### 8.12 命令 `rnp ingest stp --compounds DIR --selection DIR2`（2026-11-16；未发布）

`rnp ingest stp --config run.yaml --compounds DIR --selection DIR2 [--force]`：`DIR2` 是 `rnp compounds select` 的阶段目录，`DIR` 是它所依据的
`rnp ingest compounds` 的阶段目录。只给 `--selection`、不给 `--compounds` 是表级错误（退出码 2，什么都不写）。给了 `--selection`，
`ingest stp` 按每个候选的 `selection_status` 处理它的导出；不给，`ingest stp` 的产物与以前逐字节相同（回归测试锁着这一点）。

- **处理：**

  | `selection_status` | 导出的记录（`stp_audit.json` 的 `files`） | 对阶段状态的影响 |
  |---|---|---|
  | `selected` | 照常解析，进 `targets.tsv` | 无 |
  | `excluded` | `status: not_selected`、`reason: compound_excluded`，不解析 | 无（研究者已决定）；它的导出缺失也不算错误 |
  | `needs_review` | `status: not_selected`、`reason: compound_needs_review`，不解析 | partial（退出码 3） |
  | `quarantined` | `status: quarantined`、`reason: compound_quarantined`，不解析 | partial（退出码 3） |

  选择阶段的状态取代化合物阶段的隔离集合：化合物阶段隔离、但研究者写了 `exclude` 的化合物是 `excluded`，隔离造成的 partial 随之消解。
  一个化合物也没有被选中时没有可用的导出，是表级错误（退出码 2，报错说明“没有任何化合物被选中”）。
- **记录：**`stp_audit.json` 升到 Schema 1.2（只在给了 `--selection` 时；1.1 的审计仍然合法）：文件状态多 `not_selected`，`summary` 多
  `files_not_selected`（紧跟 `files_quarantined`），`files_bound` 不含隔离的和未选择的导出，`quarantine` 只列隔离的；`notes` 在
  `compounds_stage_applied` 之后多一条 `selection_stage_applied`（带各状态的计数）。`compounds_registered.tsv` 末尾多一列
  `selection_status`（结构模式在 `structure_id`、`structure_status` 之后）。`run_manifest.json` 的 `parents` 多一项 `compounds select`，
  `args` 多 `selection`，`inputs` 末尾多选择阶段的审计、全候选表、所选名单和决定表。
- **阶段必须是当前的**，否则表级错误（退出码 2，什么都不写）：目录和审计存在且合 `selection_audit` Schema；审计记录的运行配置哈希等于现在的；
  全候选表和所选名单的哈希等于审计里的，且全候选表每行合 `selection_decisions_row` Schema，候选与化合物阶段的相同、顺序相同；`inputs.selection`
  的决定表文件的哈希等于审计里的；审计记录的化合物阶段审计哈希等于给的 `--compounds` 的。改了决定，只重跑 `rnp compounds select`，再重跑这一步。
- **下游：**`compounds_registered.tsv` 有 `selection_status` 列时，`rnp intersect` 和 `rnp network` 只数、只列 `selected` 的化合物
  （交集审计每组的 `compounds`、`compounds_without_edges` 和组名，网络的 `mol_list.tsv`、`compounds_total`、组目录，以及化合物名与基因符号撞名的检查）：
  被排除的化合物不再出现在“没有边的化合物”里，没有已选化合物的组不再出现。`rnp report` 在 “Compounds registered” 一行之后多一行
  `- Compound selection: N selected, N excluded, N needs review or quarantined`。没有这一列时三个命令的输出与以前逐字节相同。
  待审或隔离使阶段是 partial，往下走需要 `--allow-partial`，和现在隔离的处理一样。
- **案例入口：**`scripts/case_run.py --selection` 和 `scripts/case_check.py` 的选择复核见 8.13。

### 8.13 案例入口的选择：`scripts/case_run.py --selection` 和 `scripts/case_check.py`（2026-11-17；未发布）

`scripts/case_run.py ... --log LOG --selection FILE`：`FILE` 是决定表（格式见 8.11）。选择接在结构模式的化合物阶段后面，所以
`--selection` 必须和 `--log` 一起给，否则是输入错误；文件不存在也是输入错误。决定表的路径在第一次 `rnp ingest compounds` 之前写进两个阈值的
run.yaml（`inputs.selection`）。不给 `--selection`，案例入口的行为和产物与以前相同。

- **预检**在临时目录里对输入的副本真跑 `rnp ingest compounds` 和 `rnp compounds select`，按案例策略（`case-selection-policy-v1`）把关；
  任何一条不成立，整体拒绝、什么都不写，每个问题一行：每个候选都要决定成 `include` 或 `exclude`（没写决定、`needs_review` 都不行）；决定表里不能有
  对不上任何化合物的行；至少纳入一个化合物。选择阶段审计里的问题代码全部算致命（`no_decision_recorded`、`include_blocked_by_quarantine`、
  `quarantine_resolved_by_exclusion`、`decision_without_compound`、`no_compound_selected`）；案例策略不认识的代码是错误，不猜。
- **链：**每个阈值在 `ingest compounds` 之后运行 `rnp compounds select --compounds <阶段> --run-id run`（阶段目录
  `<out>/<阈值>/run_selection/`），`ingest stp` 多给 `--selection <选择阶段>`，选择阶段目录再用一次 `manifest --check-inputs` 核对（在该阈值的
  运行目录和化合物阶段目录之后）；`case_check.py` 多得到 `--selection <决定表>` 和每个阈值一个 `--selection-stage <阈值>=<选择阶段>`。
- **记录：**`case_provenance.json` 的 `inputs.selection`（`provided`、`path`、`sha256`、`rows`、`selected`、`excluded`、`verified_by`、
  `policy`、`recheck`）和 `inputs.selection_stage`（每个阈值：`dir`、`audit_sha256`、`table_sha256`、`list_sha256`）。
- **独立复核** `case_check.py --selection FILE --selection-stage LABEL=DIR`（每个 `--run` 一个，和绑定复核的参数一起给）：只用标准库，不导入选择库；
  从决定表和化合物表按 8.11 的规则自己推导每个化合物的状态和决定 ID，再与选择阶段（全候选表、所选名单、审计）、运行目录的
  `compounds_registered.tsv`（`selection_status` 列）、`stp_audit.json`（Schema 1.2、`files_not_selected`、`selection_stage_applied`）、
  `targets.tsv`（不得有未被选中的化合物的行）和交集审计（每组的化合物数）逐项比对，并要求案例策略成立；两个阈值的选择阶段表必须相同。
  通过的复核记在 `independent-check.json` 的 `selection` 下（`rule: case-selection-recheck-v1`）；有问题则报错、不写文件，每个问题一行。
- **不做：**不改已发布的案例包和 v0.1.0 的案例记录；案例入口不生成决定表。
