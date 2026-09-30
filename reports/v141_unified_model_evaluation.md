# V141 Unified Model Evaluation

## 【当前版本】

V141 Unified Model Evaluation。V130 权重、V128 数据、环境规则、Reward、教师和
编码语义均未修改；训练更新数为 0。

## 【本轮目标】

将 V130 candidate-scoring BC 接入公共 `evaluate.py`，让 Random、基础
Heuristic、V130 教师 `forecast_rents` 与 BC 使用同一 `GameEnv`、种子、
合法动作、终止条件、CSV 和指标合同，并保存动作覆盖与 BC 同状态失败诊断。

## 【Repository 状态】

以 V140 审计后的脏工作区继续增量开发，没有重新遍历或重建工程。V140 legacy
基线保留不覆盖；本轮正式比较改用 V130 唯一支持的 `instance-magpie-v1`。

## 【已有实现】

V130 原推理链为：

```text
GameState + legal_actions
  -> normalized public observation
  -> MagpieCandidateEncoder (magpie-spatial-candidates-v1)
  -> V128 train-only scaler (magpie-corpus-zscore-v1)
  -> magpie_tensors
  -> MagpieCandidateModel (magpie-spatial-mlp-v1)
  -> one logit per legal candidate
  -> argmax candidate
```

checkpoint loader 已严格验证 checkpoint/model/encoder 版本、符号和物品词表、
`instance-magpie-v1` 规则身份、教师配置、V128 manifest 和重算 scaler；
`state_dict` 使用 `strict=True`，CPU `map_location`、`eval()` 和 `no_grad()`。

## 【发现的问题】

集成初测发现无诊断 `evaluate()` 的 BC 分支错误访问空诊断教师，已通过薄层条件
修复并加入实际 checkpoint 回归。没有发现特征顺序、维度、候选顺序、mask、
归一化或 action mapping 漂移。

正式结果暴露出策略问题：BC 平均阶段高于基础 Heuristic，但通关数只有 4/128，
低于基础 Heuristic 的 19/128，更远低于教师的 57/128。符号同状态教师一致率
仅 66.26%，并出现 694 次高置信符号分歧。

## 【本轮假设】

现有 V130 agent 可通过只读 adapter 接入公共评估器；统一入口不会改变原动作序列，
并能显示离线教师匹配不足如何对应在线长期差距。

## 【BC Integration Architecture】

`BCPolicyAdapter` 只完成 checkpoint SHA 验证、现有 agent 调用、候选 logits 的
诊断读取与合法候选 argmax。softmax 仅用于解释训练时交叉熵 logits 的 top-1
confidence；实际动作仍由原始 logits argmax 决定。score margin 是前两名原始
logit 差。

公共评估器增加 `BCSpec` 和惰性 PyTorch 导入，非模型环境仍可运行 Random 与
规则 Agent。模型每个 worker 只加载一次，encoder 只构造一次；每一步没有读取
checkpoint、JSON 或 scaler。

## 【Checkpoint Contract】

- Checkpoint：`outputs/v130-magpie-corpus-training/research-200-updates.pt`
- SHA-256：`e6bcd874deb2650628810d6cb4afff443cc08db2436608442c60a21e5ab9c64e`
- 模型：`magpie-spatial-mlp-v1`
- 编码器：`magpie-spatial-candidates-v1`
- 数据：`logs/v128-magpie-shards`
- 更新：200（本轮新增 0）
- 错误 SHA 和错误 rule version 均在推理前拒绝。

## 【修改文件】

- `luck_agent/agents/magpie_agent.py`：抽出与原 `choose` 共用的 `score_actions`；
  argmax 行为不变。
- `luck_agent/agents/bc_policy.py`：新增只读、确定性的薄适配层。
- `luck_agent/evaluation/evaluator.py`：公共 CLI 加入 `--agent bc` 和严格 checkpoint
  参数，所有 Agent 输出同一增量 CSV、coverage 和 failure summary。
- `luck_agent/evaluation/decision_coverage.py`：统计动作机会、选择、非法动作、同状态
  教师一致率、confidence、margin 和高置信错误。
- `compare_baselines.py`：兼容新增 CSV 字符串元数据，保留旧数值字段。
- `configs/v141_unified_evaluation.json`：冻结128局协议。
- `tests/test_bc_unified_evaluation.py`、`tests/test_decision_coverage.py`：模型入口、
  合法性、确定性、错误合同和覆盖状态回归。
- `reports/seed_usage.json`：登记 V141 已消耗种子。

## 【测试结果】

- `.venv-model`：512 tests，512 passed，0 failed，0 skipped。
- V140 Random/Heuristic 各1000局旧数值字段逐局完全一致。
- 改造前后种子13000–13007共2,739动作的 trace SHA-256 均为
  `479496688e36b1e63c74c105453ed0c2cd3a9f0035f6d1d04b6c538cff4ccc08`。
- BC 单/双进程种子14200–14201的 `episodes.csv` SHA-256 均为
  `4577DFAA6C9D241B677F089317CC68317A7A34D067BA1BF197A9BDCFACFEB775`。

## 【Smoke Test】

种子14000–14007，8局、2,587次决策：平均阶段9.875，非法动作0，截断0。
Reroll 有505次可用机会但选择0次；`SELECT_INTERACTION` 没有出现机会。

## 【Decision Coverage】

正式128局 BC：

| 动作 | 有机会的决策 | 选择 | 状态 |
|---|---:|---:|---|
| PICK_SYMBOL | 9,654 | 8,992 | selected |
| SKIP_SYMBOL | 9,654 | 662 | selected |
| PICK_ITEM | 1,229 | 1,229 | selected |
| SKIP_ITEM | 1,229 | 0 | available_never_selected |
| REMOVE_SYMBOL | 5,903 | 156 | selected |
| REROLL | 7,734 | 0 | available_never_selected |
| SELECT_INTERACTION | 0 | 0 | never_available |
| SPIN | 9,782 | 9,782 | selected |
| KEEP_OPTIONS | 19,308 | 19,152 | selected |
| PICK_ESSENCE | 0 | 0 | never_available |

教师有9,690次 Reroll 机会但选择0次；基础 Heuristic 有4,390次机会但选择0次；
Random 在656次机会中选择144次。因此 Reroll 是教师与 BC 的策略覆盖问题。
`SELECT_INTERACTION` 对四种策略均为0次机会，当前只能判定环境轨迹没有产生机会，
不能判定策略拒绝选择。

## 【实验】

- 环境：`instance-magpie-v1`, floor 1。
- 种子：15000–15127。
- 每策略：128完整 Episode，单进程。
- 策略：Random、基础 Heuristic、V130 教师 `forecast_rents`、V130 BC。
- 所有策略使用相同合法动作与终止条件；非法动作和截断均为0。

## 【实验结果】

| Agent | 平均阶段 | Stage Std | Stage 95% CI | 平均奖励 | 通关 | 胜率95% Wilson |
|---|---:|---:|---:|---:|---:|---:|
| Random | 3.2188 | 1.6880 | [2.9263, 3.5112] | 112.69 | 0/128 | [0, 2.91%] |
| Heuristic | 6.6094 | 3.5765 | [5.9898, 7.2290] | 474.91 | 19/128 | [9.71%, 22.02%] |
| Teacher | 11.6094 | 1.6517 | [11.3232, 11.8955] | 975.54 | 57/128 | [36.21%, 53.18%] |
| BC | 9.6328 | 1.6452 | [9.3478, 9.9178] | 669.26 | 4/128 | [1.22%, 7.76%] |

## 【配对比较】

| 配对阶段差 | 均值 | Bootstrap 95% CI | 改善/相同/变差 |
|---|---:|---:|---:|
| BC − Random | +6.4141 | [6.0234, 6.8047] | 127/1/0 |
| BC − Heuristic | +3.0234 | [2.3750, 3.6797] | 98/3/27 |
| BC − Teacher | −1.9766 | [−2.3672, −1.5938] | 20/16/92 |

BC 的平均阶段优于基础 Heuristic，但通关率更低，说明只看阶段均值会掩盖策略
尾部质量；本轮不作模型晋升。

## 【失败摘要】

| Decision Type | 多动作决策 | 教师一致率 | 平均Top-1 confidence | 高置信错误 |
|---|---:|---:|---:|---:|
| symbol | 9,654 | 66.26% | 70.37% | 694 |
| item | 1,229 | 83.48% | 83.84% | 150 |
| remove | 5,903 | 97.07% | 98.97% | 165 |

高置信错误定义为 BC 与同状态教师不一致且 softmax top-1 ≥ 0.8，共1,009次。
最常见错误包括：Bar of Soap 替代 Mouse 278次、Time Machine 替代 Undertaker
150次、Bar of Soap 替代 Goldfish 102次、Spirit 替代 Mouse 83次。完整记录含
state hash、Episode、spin、合法动作、双方选择、confidence、margin 和 eventual
return，位于 BC run 的 `failure_summary.json`。

## 【性能】

| 模式 | Episodes/s |
|---|---:|
| Random | 132.70 |
| Heuristic | 54.35 |
| Teacher | 0.263 |
| BC policy only | 4.530 |
| BC + 同状态教师诊断 | 0.302 |

BC 39,973次模型决策的平均编码+推理延迟为0.794 ms；纯 BC 再运行的逐局字段与
带诊断版本完全一致。2局小批次中双进程比单进程慢，原因是每个 worker 都严格
重算数据 scaler 并加载 checkpoint；当前不建议对小批次启用多进程。

## 【结论】

V141 成功标准已满足：V130 通过公共 `evaluate.py` 严格加载；四种策略共享环境、
种子、合法动作、CSV 和指标；BC 没有非法动作；测试全通过；旧基线行为不变；
coverage 能区分 never available 与 available never selected；128局配对比较和
同状态失败记录已生成。

数据支持决策树 Case A：BC 明显弱于教师，符号教师一致率也低。基础 Heuristic
通关率高于 BC 进一步表明 V130 不能晋升。当前证据不支持 PPO、重新训练或扩数。

## 【Known Limitations】

- 128局是中型开发评估，不是最终1000局结论。
- 只适用于受限 `instance-magpie-v1` 近似环境，不是原版胜率。
- 同状态教师诊断成本高，整局墙钟不能当作纯模型推理速度。
- `SELECT_INTERACTION` 和精华没有出现机会，相关能力仍未被评估。
- 模型环境缺 NumPy，会产生不影响当前纯 Torch 路径的警告。

## 【下一轮】

1. 只做 BC Error Analysis：按 Episode 终局、阶段和错误发生时间分析 Bar of Soap、
   Time Machine 与 Spirit 的高置信错误，验证是否存在表示或分布偏移。
2. 单独审计 Rare Action Coverage：解释教师为何在9,690次机会中从不 Reroll，
   不进入 PPO、不训练、不扩数据。

## 证据位置

- 汇总：`reports/v141_unified_model_evaluation.json`
- 对比：`reports/v141_bc_vs_random.json`、`v141_bc_vs_heuristic.json`、
  `v141_bc_vs_teacher.json`
- 每策略 CSV/summary/coverage：`logs/v141-unified/<agent-timestamp>/`
- Smoke：`logs/v141-smoke/`
- 单/双进程：`logs/v141-multiprocess/`
