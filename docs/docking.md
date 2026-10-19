# 候选对选择与最小对接闭环（设计契约）

状态：2026-10-19 设计稿；本页不表示 dock 命令已实现。
关联：[总规划](project-plan.zh-CN.md)、[上游身份](upstream.md)、[ADR-0004](adr/0004-staged-upstream-and-docking.md)。

## 1. 首版支持与不适用状态

v0.3 首版：有适合该问题的共晶参照、普通非共价小分子、固定受体准备协议与 Vina。
首版不承诺金属特殊参数、共价配体、大环、肽/蛋白对接或所有预测模型。
特殊体系保留 unsupported/needs_review 原因，不静默按普通小分子协议执行。
允许未来接收 AlphaFold/同源结构，但必须独立验证协议，不能通过扩大物种/来源 enum 冒充支持。

## 2. candidate_pairs.tsv 设计

| 字段组 | 内容 |
|---|---|
| 身份 | pair_id, compound_id, structure_id, target_uniprot, species, isoform/construct |
| 提名依据 | prediction_submission_ref, disease_evidence_refs, network_result_ref, selection_reason |
| 结构与位点 | receptor_id, chain/assembly, pocket_id, site_evidence_refs |
| 控制与决定 | control_ligand_id, protocol_id, eligibility_status, reason_codes, decision_ref |

一对可关联多个受体结构/配体状态；具体任务另由 docking_run_id 绑定。
不默认生成 hub × 全部成分笛卡尔积；所有候选、未选和不适用对保留。
前景/背景、STRING 阈值及排序方法变更须更新提名来源，不覆盖旧选择。
网络排名与对接分数不能合并成未经校准的亲和力或“机制证据分”。

## 3. 结构与准备记录

receptor 记录来源 ID/版本/下载时间/哈希、目标序列与链映射、突变/缺失、
构建体/组装状态、口袋局部质量、实验分辨率等适用指标、替代构象、保留/移除成分和理由。
PDB 共晶来源不自动代表适用；原蛋白与所研究物种/位点必须对应。
水、金属和辅因子按局部作用决定；不能统一去水或补造缺失口袋。

ligand 记录原/标准化结构、准备 pH/状态依据、工具/规则版本、显式氢、立体、3D、
状态与 conformer ID、原子对应和输出哈希。保存可核验 SDF 与 PDBQT 的映射。
注册标准化和对接微状态准备分别进行；不强制把所有化合物中性化。

盒子记录 center_x/y/z、size_x/y/z、Å 单位、位点残基的 chain/编号/insertion code、
计算算法和 padding 定义。验证最大目标配体的容纳、旋转/移动与对照采样，不写死通用尺寸。
对接位点选择可以基于天然配体、文献或口袋检测，但证据类型必须注明。

## 4. 执行与复现

每个任务保存 run ID、pair/receptor/ligand_state/conformer、实际命令、输入/输出 SHA256、
Vina 二进制版本/哈希、准备工具/环境、评分函数、盒子、seed、CPU、
exhaustiveness、num_modes、energy_range、开始/结束时间、退出状态、stdout/stderr。
额外参数和受体柔性设置必须原样记录；CPU 不是有效性证据，seed 也不是唯一复现条件。
受控环境验证重复执行；跨平台/版本比较用事先声明的容差和姿势指标，不保证逐字一致。
重复 seed 与状态数、采样预算、汇总规则事先固定，不根据低分事后挑选。
已有输出拒绝覆盖或写新的不可变运行目录；续跑仅恢复明确未完成任务。

## 5. 回对接与 pose QC

由独立生成的初始配体构象开始；天然配体坐标仅用作位点/参照，不能作为容易恢复原姿势的捷径。
参照明确原子与键级、质子化/互变异构一致性、重原子与对称性映射；需要对齐时按受体对齐。
不将配体单独拟合到参照后把拟合 RMSD 称为口袋内姿势恢复。

至少报告 top1_heavy_atom_rmsd、best_sampled_heavy_atom_rmsd、k、参考结构、
映射/对齐方法、seed 与采样预算。2 Å 为项目预声明的常用判据；不能用 best-of-many 冒充 top-1。
QC 保存工具版本和解析后的配置、每姿势化学/几何/立体/碰撞检查；
未执行、解析失败、不适用和检查未通过分开，不以空检查集合产生“全通过”。
PoseBusters 模式/阈值以实际锁定版本为准；记录 SDF 与受体输入，不能只检查 PDBQT 文件存在。

回对接和 QC 失败写出诊断候选（原子映射、准备、受体、位点、采样、评分），不直接归因为盒子。
失败任务可以有诊断输出，但不能进入标为已校准的候选排名。
回对接仅检验该设置的姿势恢复；已知活性/非活性或匹配 decoy 基准另评估筛选区分能力。
小 demo 的单体系通过不升级成跨靶点验证。

## 6. 预测/同源结构后续规则

综合口袋局部 pLDDT、PAE、结构域/组装状态、位点与已知配体证据；
不得机械删掉低于 70 的残基以生成新口袋。高分局部区域也不保证侧链/口袋状态适合配体。
无天然参照记 redocking_not_applicable；若有相关实验结构可设计 cross/template-docking 控制，
但不能把转移的模板配体称为本受体原位回对接。
同源模型记录模板、序列映射、覆盖、插缺与质量指标；来源三分法不作普遍高/中可信度标签。

## 7. 比较与解释

同受体、准备、评分、搜索协议下作探索性比较；不同靶点不直接总排，分数不换算为实测亲和力。
不同微状态/受体构象的汇总策略和搜索预算先声明，避免“状态多所以更容易得到最低分”。
多 seed 的分数范围/姿势聚类描述搜索稳定性，不能当独立生物学重复或置信区间。
距离接触不等于相互作用能；pose QC 通过不等于实验结合或药效证据。

## 8. 验收、CI 与历史迁移

轻量 CI：合成输入的契约/身份、盒子几何、原子映射、日志解析、状态传播、拒绝覆盖和失败例。
可选集成：显式触发小型真实 Vina 任务，固定合法可获取的输入及二进制；
记录实际运行预算，不称 workflow_dispatch 为自动夜间调度。
历史盘点先检查 config、脚本、命令和日志；config 缺 seed 不足以证明运行缺 seed。
旧目录、二进制、配置和结果只读留存并记录哈希；先迁移一例再扩批。
历史再现比较与新增对照校准分开；不声称旧结果是独立验证。

## 9. 依据

[Vina FAQ](https://autodock-vina.readthedocs.io/en/latest/faq.html)；
[Meeko](https://meeko.readthedocs.io/en/develop/lig_prep_basic.html)；
[PoseBusters](https://github.com/maabuu/posebusters)；
[AlphaFold 局部置信度](https://www.ebi.ac.uk/training/online/courses/alphafold/inputs-and-outputs/evaluating-alphafolds-predicted-structures-using-confidence-scores/plddt-understanding-local-confidence/)。
