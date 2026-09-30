## 【当前版本】

V142 High-Confidence Error Attribution & Reroll Audit

## 【本轮目标】

冻结V130，解释差距并决定下一轮。训练更新0，模型、Teacher、Reward、规则、Environment、Dataset均未修改。诊断输出未进入训练Dataset。

## 【冻结基线】

| 策略 | 平均Stage | Wins |
| --- | --- | --- |
| Random | 3.21875 | 0/128 |
| Heuristic | 6.609375 | 19/128 |
| Teacher | 11.609375 | 57/128 |
| BC | 9.6328125 | 4/128 |

instance-magpie-v1；15000–15127；128局。BC−Teacher=−1.9765625，原配对95%CI=[−2.3671875,−1.59375]。沿用V141，未重新估计。种子已消费，不是新holdout。

## 【新增工具】

tools/analyze_bc_errors.py 复用既有诊断方式。V141缺少完整观测和低置信序列，故补放BC轨迹并查询同状态Teacher，没有重跑128局独立Teacher Benchmark。逐局缓存支持恢复；原1009例状态hash、动作、终局、各phase计数全部核对。

## 【测试结果】

515项完整测试通过；最终4项诊断测试通过（其中3项已包含于完整测试）。核心源文件诊断前后hash一致；checkpoint SHA严格加载验证；128局Stage/Win/Spins/Coins/Reward/Decisions/Truncation与V141逐局一致。日志见tests.txt及diagnostic_tests.txt。

## 【错误阶段分布】

rent_stage从0起：Early=0–5（5/6/7转），Mid=6–9（8/9转），Late=10–12（最终10转）；采用真实租金回合长度边界。分母只计多动作决策。

| 阶段 | n | 全体agreement | Symbol agreement | HC error rate | Win/Loss errors |
| --- | --- | --- | --- | --- | --- |
| early | 7482 | 78.37% | 69.20% | 6.88% | 24/491 |
| late | 2214 | 75.20% | 57.82% | 3.12% | 2/67 |
| mid | 7090 | 79.32% | 65.58% | 5.99% | 10/415 |

逐rent_stage结果见JSON.stage；coins、rent pressure、deck size、recent income、confidence、margin、return分桶见continuous_error_bins；所有逐状态字段在error_attribution.csv。

## 【四类主要错误】

箭头定义已核验：BC→Teacher。按错误出现次数加权，非独立episode均值。

| 类型 | n | Stage mean/median | Coins | Deck | Confidence | Margin | Final stage | Win |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bar_of_soap→mouse | 278 | 6.21/7.0 | 371.1 | 25.2 | 0.895 | 2.894 | 9.00 | 0.00% |
| time_machine→undertaker | 150 | 5.80/6.0 | 347.6 | 23.3 | 0.843 | 1.698 | 9.85 | 1.33% |
| bar_of_soap→goldfish | 102 | 2.99/2.0 | 173.6 | 19.1 | 0.886 | 2.537 | 8.37 | 0.98% |
| spirit→mouse | 83 | 6.83/7 | 456.3 | 25.4 | 0.852 | 2.442 | 9.48 | 1.20% |

错误后5/10/20总决策内的多动作一致率、有效窗口数及最终return在JSON.main_errors[].future/mean_episode_return。

## 【Training Support】

只使用train9000–9031，多动作状态3849；Exact Public Match 0/1009；分类{'low-support': 1002, 'contradictory-support': 4, 'high-support': 3}。

分数=直方图Jaccard40%+物品集合15%+阶段15%+牌组大小15%+租金压力15%。候选集合优先；无匹配则回退同phase/候选数，主要涉及removal实例ID。Top10中≥.85至少5例为high；近邻标签占优<80%为contradictory。这是近似异标，不能等同于相同特征冲突。

阈值敏感性(best neighbor)：{'0.8': 194, '0.85': 72, '0.9': 8, '0.95': 0}。

| cohort | n | Mean | Median | <.85 |
| --- | --- | --- | --- | --- |
| high_error | 1009 | 0.804 | 0.802 | 81.07% |
| non_high_error_control | 1009 | 0.793 | 0.800 | 78.00% |

辅助build对照按phase/实际rent_stage、等量系统抽样，候选身份不参与分数。不是完全匹配或随机对照。training_support.csv记录候选/阶段/build/Teacher label支持、最近train seed/step。

## 【Feature Collision】

Exact编码异标组=0。相同有序候选的实际编码token采用one-hot、标量使用冻结train scaler，L2≤.25异标有向近邻=0；检查1082例；最小异标距离=7.046091556549072。

按线性实例层+mean pooling+有序board及candidate pointers的符号表达式，实际train context异标组=0，重复context组=0。

合成测试可构造未观测符号交换计时器但mean context相同；pointer/board观测可恢复区分。该合成探针不是实际错误证据。即使有context异标，有限8次Monte Carlo Teacher对deck顺序的敏感性也可能是原因。Raw无冲突不能替代这些审计。

## 【Candidate Ranking】

高置信错误中Teacher Top1=0（定义所致），Top2=49.06%，Top3=82.26%，Mean Rank=2.782，Last Rank=0.00%。每个case完整候选logit、softmax权重和Teacher gap/rank均在CSV。Softmax为未校准类别权重，不是胜率/存活概率。

冻结模型对原TRAIN的拟合：

| phase | n | agreement |
| --- | --- | --- |
| symbol | 2843 | 72.88% |
| item | 351 | 85.19% |
| remove | 655 | 98.93% |

## 【Error Severity】

| 类型 | freq | cases | Mean ΔStage | Mean ΔReward | 改善例 | 探索性freq×正ΔStage |
| --- | --- | --- | --- | --- | --- | --- |
| bar_of_soap→mouse | 278 | 2 | 1.5 | 222.0 | 2 | 417.0 |
| time_machine→undertaker | 150 | 2 | 2 | 209.0 | 2 | 300 |
| bar_of_soap→goldfish | 102 | 2 | 0 | -70.5 | 0 | 0 |
| spirit→mouse | 83 | 1 | 0 | 95.0 | 0 | 0 |

仅15000–15003各类首例；deepcopy同一初始RNG，BC/Teacher动作后都由BC继续。Δ=Teacher−BC，reward是分支后的累计奖励。不同动作可消耗不同随机数，无法保证未来事件逐一对齐。因此改善只作为outcome-critical线索；指数是优先级探索，非总体无偏/因果严重度。Disagreement不等于严重错误。

## 【Compounding Error】

| 首错后总decision窗 | episode n | 多动作agreement |
| --- | --- | --- |
| 5 | 128 | 52.34% |
| 10 | 128 | 56.38% |
| 20 | 128 | 66.25% |

| 观察点 | n | build support | agreement |
| --- | --- | --- | --- |
| before | 128 | 0.993 | 67.19% |
| first | 128 | 0.987 | 0.00% |
| 5 | 128 | 0.911 | 58.59% |
| 10 | 128 | 0.901 | 58.59% |
| 20 | 128 | 0.884 | 70.31% |

before为首错前最近多动作，没有前例则首错；5/10/20为该step之后最近多动作。首错、首个高置信错误及距终局见episode_diagnostics.csv；胜局距终局不能称距死亡。阶段与幸存混杂，未证明首错→shift→再次错误→失败的因果链。

## 【Win vs Loss】

4胜/124非胜；Exploratory Only，按episode等权。

| cohort | n | Symbol | Item | Remove | 首错Stage | HC/局 | Deck | Pressure | Skip | Removal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | 4 | 61.62% | 87.50% | 94.64% | 0.00 | 9.00 | 21.99 | -0.523 | 14.65% | 1.01% |
| False | 124 | 65.76% | 83.67% | 94.81% | 0.02 | 7.85 | 22.22 | -0.164 | 5.92% | 1.74% |

## 【Reroll Audit】

V141 Teacher9690/0，BC7734/0。RentForecastAgent评分前只保留PICK_SYMBOL/SKIP_SYMBOL；validate_choices明确拒绝REROLL。不存在Reroll EV、penalty或资源估值评分，并非mask降权。原train可用2363，标签0。

前8局筛选Teacher Skip、tokens≥2、coins≥rent、每局最多2例，得到6例。完整State、候选、券、Teacher lexicographic ranks在reroll_audit.csv；Reroll score=null。deepcopy执行均验证symbol阶段与tokens−1及候选更新。例15000/201：[milk,cat,flower]，2券→1券。此筛选不证明Reroll必然更优。

SELECT_INTERACTION：UNRESOLVED / NO OPPORTUNITY。

## 【归因矩阵】

| 类别 | Evidence For | Evidence Against | Confidence |
| --- | --- | --- | --- |
| DATA | 低支持1002例；错误build支持0.804 | 对照支持0.793，错误组并未更低；距离只是代理 | 中：覆盖稀疏；选择性shift未证实 |
| REPRESENTATION | 线性mean pooling可能丢失未观测计时器归属，合成测试验证 | 实际exact/near/context异标碰撞=0/0/0 | 低；实际证据与结构风险分开 |
| MODEL | 原train符号拟合率72.88% | 未消融，不能区分容量、优化预算或目标函数 | 高：未充分拟合；具体机制低 |
| COMPOUNDING | 首错后的窗口和支持变化见下表 | 阶段、幸存和选择偏差混杂，未验证完整因果链 | No Evidence of monotonic decline |
| TEACHER | 评分前排除REROLL；原train可用但无标签；机会重放有效 | BC与Teacher都不重掷，不能单独解释两者Stage差 | 高：Reroll设计缺口 |
| ENVIRONMENT | 未发现本轮导致阶段差的环境/Action Mask错误 | 128局重放一致；Reroll语义检查正常；仅受限近似环境 | No Evidence；原版泛化未验证 |

## 【结论】

Q1：前/中/后期高置信错误515/425/69，后期不是主要高置信错误发生区；符号agreement为69.20%/65.58%/57.82%，前期也并未接近Teacher。首租阶段符号agreement仅49.22%，不能把全部问题解释为后期崩溃。

Q2：1002例为低支持，但冻结模型在原train仍有27.12%符号分歧。Data coverage与未充分拟合共同存在；未做消融，不能认定具体Objective缺陷。

Q3：错误build支持0.804，对照0.793；两组都稀疏，未证明高置信错误选择性集中于更严重OOD状态。

Q4：首错后5/10/20窗口agreement为52.34%/56.38%/66.25%，没有持续下降。build支持随牌组增长下降，但不能证明错误导致该下降；完整compounding因果链未成立。

Q5：Teacher排除Reroll评分，TRAIN2363次机会/0标签。环境6次定向资源与候选语义验证正常。此上游缺口不单独解释BC−Teacher，因为两者都未使用Reroll。

有限分支7例中4例提高最终Stage，其余3例不提高，且某一Teacher替代动作减少reward；disagreement不可直接等同于严重错误。实际encoder/context冲突未发现，只有mean pooling合成探针揭示结构风险。当前Teacher不读取recent_income/effect_state，不能仅凭这些字段未编码就认定模仿输入不足。

## 【V143 决策】

先建立新版本Teacher的Reroll条件价值/资源成本评分与机会测试；冻结旧Teacher和V141基线。随后才选择Data或Model实验。

按用户指定的上游优先级，教师动作支持缺口已被证实；并不声称该缺口解释当前BC相对教师阶段差。优先级Environment→Teacher→Data→Representation→Model→RL。不进入PPO，不宣称修Reroll即可消除当前阶段差。

## 【Artifact】

机器报告：reports/v142_high_confidence_error_attribution.json。逐状态、支持、碰撞、Reroll、有限分支、episode及build对照：logs/v142-diagnostics/*.csv；完整错误观测：episode-<seed>.json.gz；冻结合同：contract.json。仅诊断，未新增Dataset。
