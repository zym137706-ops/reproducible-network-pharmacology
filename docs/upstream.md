# 上游导入、结构注册与显式选择（设计契约）

状态：2026-10-19 设计稿；字段与命令尚未接入运行代码。执行顺序见 [总规划](project-plan.zh-CN.md)。
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
