# V140 Repository Audit 与评估不确定性补全

## 【当前版本】

V140 repository audit。代码版本基点为 Git `main` / commit
`701580dd3a7c0097e2940f05fd7f1a560ad39453`；工作区含大量未提交的后续成果，
所以该 commit 不能代表当前可运行版本。

## 【本轮目标】

读取现有工程、验证无动画环境和完整研究链路，建立能力矩阵及修改前基线；
只修复一个不改变策略行为的评估问题：批量评估缺少标准差和 95% 区间。

## 【Repository 状态】

- `rg --files` 可见 720 个文件：reports 250、integrations 196、tests 85、
  `luck_agent` 61、configs 32、tools 30、archive 22。
- Git 状态很脏：当前核心中后期代码、测试、报告和集成文件大量未跟踪；
  任何 manifest 中的 `git_commit` 只能说明旧基点，必须同时依赖源码哈希。
- `logs/` 有 801 个文件、约 461 MB；`outputs/` 有 32 个文件、约 1.34 MB。
- 默认 Python 3.11.9 不含 PyTorch；`.venv-model` 含 PyTorch 2.14.0+cpu。
- `.venv-model` 缺 NumPy，会产生 PyTorch 警告，但当前纯 Torch 测试仍通过。
- README 主线记录到 V0.7.3，真实实验已到 V139/V140；根目录说明没有呈现
  V128–V133 的当前语料/模型状态、V134–V139 的实时助手与工坊接入边界。
- `requirements.txt` 仍准确表达标准库环境；模型依赖放在
  `requirements-model.txt`，但 README 没有给出当前双环境的清晰入口。
- `archive/sandbox_v01` 是废弃草稿，不参与运行。早期 coal BC、spatial BC
  与当前 magpie corpus 模型是不同版本合同，不能互换；它们不是当前默认模型。
- 多个验证/训练工具把输出目录设为 `exist_ok=False`，适合作为一次性实验生成器，
  不适合作为重复审计命令；当前只做只读合同重载，没有覆盖既有证据。

## 【已经存在的实现】

### 无动画环境

`luck_agent/legacy/fast_env.py` 是找回并保留的无动画近似引擎；
`GameEnv.reset/step/legal_actions/action_mask` 在其上建立统一接口，不依赖窗口、
动画或等待。默认 legacy 后端规则范围较大但仅为近似；实例后端逐步提高实例、
计时、转化和邻接精度，但每个后端只开放受限符号/物品集合。

### State 与 Action

`GameState` 已包含经济、租金、牌组实例、物品、重掷/删除资源、决策类型、候选、
近期收入、棋盘、效果状态、历史、终局和实例能力标志。公开状态不含 RNG/种子。
`Action` 使用动作类型与一/二级目标；现有枚举覆盖抓牌、跳过、物品、删除、重掷、
交互、Spin、保留选项和精华。没有单独 `SPECIAL_ACTION`，现阶段沿用现有交互合同。

### 当前真实 Pipeline

```text
FastLandlordEnv / restricted instance engines
  -> GameEnv public GameState
  -> GameEnv.legal_actions / action_mask
  -> Random / Heuristic / Forecast teacher / Candidate model
  -> GameEnv.step
  -> versioned replayable trajectory
  -> episode-level split + manifest/hash checks
  -> candidate encoder + train-only scaler
  -> PyTorch candidate-scoring BC
  -> bound checkpoint
  -> specialized closed-loop rollout and diagnosis
```

最新研究链路为 V128–V133：48 个 `instance-magpie-v1` 教师 Episode、17,889 条
转移、V130 固定 200 更新模型，以及 V131 新种子自由对局。V134 以后聚焦本地
实时决策助手和工坊接入，没有把新实机数据混入 V128 训练语料。

## 【能力矩阵】

| 能力 | Implemented | Tested | Reliable |
|---|---|---|---|
| State Parsing | YES | YES | PARTIAL |
| Symbol Pick | YES | YES | PARTIAL |
| Item Pick | YES | YES | PARTIAL |
| Skip | YES | YES | YES |
| Removal | YES | YES | PARTIAL |
| Reroll | YES | YES | PARTIAL |
| Interaction | PARTIAL | YES | PARTIAL |
| Action Mask | YES | YES | YES |
| Teacher Policy | YES | YES | PARTIAL |
| Dataset Generation | YES | YES | PARTIAL |
| Behavior Cloning | YES | YES | PARTIAL |
| Model Loading | YES | YES | YES |
| Evaluation | YES | YES | PARTIAL |
| Batch Evaluation | YES | YES | YES |
| Logging | YES | YES | PARTIAL |
| Checkpoint | YES | YES | YES |
| Failure Analysis | YES | YES | PARTIAL |
| Game Simulation | PARTIAL | YES | PARTIAL |
| Full Episode | YES | YES | PARTIAL |
| RL Environment | PARTIAL | YES | PARTIAL |

`Reliable=PARTIAL` 的主要原因是原版规则覆盖不完整或只在受限后端验证，不代表
接口本身未实现。Interaction 在环境中有真实动作测试，但当前候选编码器拒绝
`SELECT_INTERACTION`；RL 只有可用的自定义 step 接口和轨迹，没有统一的
Gymnasium 包装、Value/DQN/PPO 训练与基线。

## 【Dataset / Teacher Audit】

V128 当前语料重新读取结果：

| 分区 | Episode | 转移 |
|---|---:|---:|
| train | 32 | 11,755 |
| validation | 8 | 3,149 |
| test | 8 | 2,985 |

- 教师：`forecast_rents`，每候选 8 次试验、30 步 horizon，未来选择排除。
- train/validation/test 种子集合互斥，checkpoint scaler 只绑定 train。
- 精确输入重复 55 条，跨分区重复输入 5 条；没有冲突标签。这些是相同公开
  观测而非同一 Episode 泄漏，但会轻微降低验证样本的独立性，应在扩大语料时
  作为分组去重指标保留。
- 动作覆盖：实际选择过 Spin、Keep、Pick Symbol、Skip Symbol、Pick Item、
  Remove；没有实际选择 Reroll、Skip Item 或 `SELECT_INTERACTION`。
- 所有 4,327 个 `interact` 状态在此语料中都走 KEEP；因此不能由当前 BC
  指标推断模型会处理特殊交互。
- V130 checkpoint 重新加载：200 更新，SHA-256
  `e6bcd874deb2650628810d6cb4afff443cc08db2436608442c60a21e5ab9c64e`。
- V131 的训练模型平均阶段 9.53125、1/32 通关；教师 11.3125、14/32 通关。
  当前模型明显优于未训练网络，但仍未接近教师，不应部署为默认策略。

## 【发现的问题】

三个主要瓶颈：

1. **规则完整性**：默认环境覆盖广但近似；实例规则准确度较高却被拆成多个受限
   后端。还没有一个同时覆盖完整符号/物品/交互并保持实例身份的统一环境。
2. **统一评估入口**：`evaluate.py` 能评估规则策略，却不能通过同一 CLI 加载
   V130 BC；模型评估仍依赖专用脚本，Random/Teacher/BC 的统一协议不足。
3. **数据与版本治理**：最新语料仅 48 局，并缺少重掷和特殊交互标签；Git 基点
   落后且大量文件未跟踪，README 与 seed registry 都落后于真实实验。

本轮没有同时修这三个问题。规则整合会改变核心环境，必须先逐规则回归；统一
模型 CLI 需要先冻结模型/环境映射。先选择评估不确定性作为最小且立即可验证的
修复，因为它不改变任何对局，又是后续所有策略比较的必要条件。

## 【本轮假设】

在 `summarize` 中加入样本标准差、均值正态近似 95% 区间、胜率和租金生存率
Wilson 95% 区间，不会改变任一 Episode、动作或旧汇总字段。

## 【修改文件】

- `luck_agent/evaluation/metrics.py`：保留旧字段，新增 `std`、`mean_95_ci`、
  `win_rate_95_ci`、`rent_survival_95_ci`。
- `tests/test_metrics_uncertainty.py`：覆盖两局样本与单局边界。
- `reports/seed_usage.json`：补登记 V128、V131 与本轮 200000–200999 种子用途；
  不把本轮种子再次称为新 holdout。
- `reports/v140_repository_audit.md`：保存本轮审计证据与能力矩阵。

兼容性：旧汇总键、CSV 格式、环境和 Agent 均未改变。新增 JSON 字段只会影响
假定 summary 键集合完全固定的外部消费者；仓库内测试没有此类依赖。

## 【测试结果】

- 默认 Python：507 tests，Passed 491，Failed 0，Skipped 16（均为可选 PyTorch）。
- `.venv-model`：507 tests，Passed 507，Failed 0，Skipped 0。
- 最新语料：48 entries / 11,755 train samples 合同重载通过。
- V130 checkpoint：绑定数据、规则和统计后重载通过。
- 修改前后 Random/Heuristic 两份 `episodes.csv` SHA-256 分别完全一致。

## 【实验】

环境：默认 legacy 近似无动画环境；种子 200000–200999；每策略 1,000 局；
2 workers；两策略同种子。修改前先运行，修改后原样复现。

## 【实验结果】

| 策略 | 平均阶段 | 阶段 Std | 阶段均值 95% CI | 平均奖励 | 胜率 | 截断 |
|---|---:|---:|---:|---:|---:|---:|
| Random | 3.175 | 1.2490 | [3.0976, 3.2524] | 105.049 | 0/1000 | 0 |
| Heuristic | 5.633 | 1.3683 | [5.5482, 5.7178] | 312.743 | 2/1000 | 0 |

配对阶段差 Heuristic−Random 为 +2.458，正态近似 95% CI
[2.3472, 2.5688]。该结果仅适用于恢复的近似 legacy 环境，不能解释成原版游戏
胜率。修改前后所有逐局字段一致；差异只在新增汇总统计。

## 【结论】

当前项目已经具备真实可运行的无动画环境、统一候选动作、可重放轨迹、按 Episode
分区、候选评分 BC、checkpoint 合同和批量评估，不需要重建。但它仍是多个受限
规则后端组成的研究平台，不是完整原版模拟器；当前 V130 模型也不是发布模型。
本轮假设成立：评估结果获得标准差和区间，策略行为保持逐局不变。

## 【失败案例】

1. 默认近似环境中 Random 0/1000 通关，Heuristic 仅 2/1000；平均阶段提升并不
   等于最终胜率问题已解决。
2. V131 训练模型只有 1/32 通关，教师 14/32，说明离线 81.28% 教师匹配率没有
   转化为相同的长期策略能力。
3. 当前语料没有重掷或特殊交互的已选标签；对应功能不能由 BC 结果宣称可靠。
4. 5 个跨分区重复公开观测没有冲突标签，但后续扩量应报告去重后的验证指标。

## 【下一轮】

只安排两个目标：

1. 给统一评估入口增加只读的 V130 模型加载方式，让 Random、Teacher、BC 在同一
   seed/config/summary 合同下运行；不训练、不改模型。
2. 在该统一入口中按决策类型保存合法动作和失败摘要，优先暴露重掷/交互零覆盖，
   不扩数据、不调整教师。
