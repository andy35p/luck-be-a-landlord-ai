# Luck be a Landlord AI Decision Project

面向《Luck be a Landlord（幸运房东）》的智能决策、策略学习与可复现实验项目。

本项目不复刻游戏 UI，而是把抓取符号、选择物品、删除、重掷和交互决策统一为可训练的 `State → Legal Actions → Policy → Action` 接口。当前重点是高速环境、数据质量、行为克隆（BC）与严格的离线评估；Steam 创意工坊决策助手仍处于接入验证阶段，尚未发布。

> 当前研究版本：**V149** · Python **3.11+** · 完整研究工作区测试：**568 passed**

## 项目概览

| 能力 | 当前状态 |
| --- | --- |
| `GameState` / `Action` / Action Mask | 已实现，所有 Agent 共用统一契约 |
| 无动画高速环境 | 已实现 `reset / step`、租金结算和确定性随机种子 |
| 规则与内容数据 | 已结构化符号、物品和实例级交互；仍不是原游戏的完整规则复刻 |
| 基线策略 | Random、Heuristic、Forecast 及其诊断变体 |
| 批量评估 | 支持多局、多进程、配对种子、指标导出 |
| 轨迹与训练数据 | 支持采集、预处理、哈希、数据切分和防污染检查 |
| PyTorch 行为克隆 | 已训练、保存、重载并接入统一评估入口 |
| 在线观察与工坊接入 | 已有适配器与官方上传器骨架；真实回调和只读状态接口仍待解决 |

工程主线：

```text
symbols/items/interactions
          ↓
      Rule Engine
          ↓
       GameEnv ─────→ GameState
          ↑               ↓
        Action ← Agent + Legal Action Mask
                          ↓
        Trajectory → Dataset → BC Training → Evaluation
```

## 为什么这样设计

动作不是固定的“选第 1/2/3 张”，而是带目标的统一结构：

```python
Action(
    action_type=ActionType.PICK_SYMBOL,
    target_id="cat",
    secondary_target_id=None,
)
```

同一接口可表达符号选择、物品选择、跳过、删除、重掷、交互和旋转。模型因此可以在当前合法候选集合上比较 `Q(s, a)`，而不必维护一个不断扩张的全局动作分类表。这套契约也是后续 BC、DQN、PPO、Transformer 或 GNN 的共同基础。

## 快速开始

在 PowerShell 中：

```powershell
git clone https://github.com/andy35p/luck-be-a-landlord-ai.git
Set-Location luck-be-a-landlord-ai

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python main.py --agent random --seed 7
python evaluate.py --agent heuristic --games 1000 --seed-start 10000
python run_tests.py
```

基础环境和启发式策略只使用 Python 标准库。模型训练与推理使用独立依赖：

```powershell
py -3.11 -m venv .venv-model
.\.venv-model\Scripts\Activate.ps1
python -m pip install -r requirements-model.txt
```

训练数据、模型权重和原始日志默认不提交到 Git。运行 BC 评估时，需要显式提供本地 checkpoint、其 SHA-256 以及对应 dataset 目录，防止误用权重或数据版本。

### Python API

```python
from luck_agent.agents.random_agent import RandomAgent
from luck_agent.env.game_env import GameEnv

env = GameEnv()
agent = RandomAgent(seed=7)
state = env.reset(seed=7)

while not (state.is_terminal or state.is_truncated):
    legal_actions = env.legal_actions()
    action = agent.choose(state, legal_actions)
    state, reward, terminated, truncated, info = env.step(action)
```

## Agent 与评估入口

`evaluate.py` 当前提供以下策略：

- `random`
- `heuristic`
- `heuristic_reroll`
- `heuristic_rent_guard`
- `heuristic_magpie_cycle`
- `forecast`
- `forecast_rents`
- `forecast_rents_v143`
- `bc`

示例：

```powershell
python evaluate.py --agent random --games 10000 --seed-start 20000 --workers 4
python evaluate.py --agent heuristic --games 10000 --seed-start 20000 --workers 4
```

使用相同种子区间可进行配对比较，减少局面差异带来的方差。输出包括平均租金阶段、旋转次数、金币、各租金存活率、胜率、非法动作和截断情况。

## 当前研究结果

### 统一策略评估（V141）

在 `instance-magpie-v1` 的 128 个配对局面中：

| Agent | 平均阶段 | 胜局 |
| --- | ---: | ---: |
| Random | 3.219 | 0 |
| Heuristic | 6.609 | 19 |
| Teacher | 11.609 | 57 |
| BC | 9.633 | 4 |

所有策略均为 0 非法动作、0 截断。BC 与 Teacher 的配对阶段差为 `-1.977`，95% CI 为 `[-2.367, -1.594]`。这说明模型已学到明显优于基础策略的行为，但仍存在稳定的教师差距。

### 训练诊断（V146–V149）

- V146–V147：200 updates 明显欠拟合；固定 500 updates 是当前简单基线。
- V148：Early Stopping 没有形成可靠收益，未进入生产配置。
- V149：Label Smoothing 降低了高置信错误数量和错误置信度，但没有稳定提高验证准确率，且损害部分 hard-case 指标，因此不采用。
- 下一项单变量实验为 **V150 Weight Decay Audit**。

V149 的验证集在此前实验中已被多次观察，因此只能用于开发诊断，不能作为独立最终测试结论。测试集继续保持封存。

详细证据：

- [V141 统一模型评估](reports/v141_unified_model_evaluation.md)
- [V147 多种子泛化](reports/v147_multiseed_generalization.md)
- [V148 Checkpoint Selection 审计](reports/v148_checkpoint_selection_audit.md)
- [V149 Label Smoothing 审计](reports/v149_label_smoothing_audit.md)

## 可复现性与数据治理

项目将实验可复现性作为功能，而不是事后补充：

- 环境、Agent、采样与评估均支持显式种子。
- 对比实验优先使用相同种子的配对设计。
- 数据集切分、教师标签和模型文件记录哈希与来源。
- 训练、开发验证和封存测试职责分离。
- 对重复样本、跨 split 泄漏和历史权重误用进行检查。
- 研究结论与原始指标写入版本化报告。

GitHub 仓库不包含本地训练语料、checkpoint 和大体积日志。因此，README 中的 568 项通过结果指完整研究工作区；需要本地受控资产的审计不会仅凭一次全新 clone 自动复现。

## 工坊决策助手状态

当前已有：

- 实时观察状态的适配层原型；
- 字段随真实操作变化的验证工具；
- 官方上传器要求下的最小包结构和静态校验；
- `SELECTME.LBAL` 及脚本骨架。

当前还缺少可依赖的官方候选项回调、完整只读游戏状态接口和非侵入式建议展示通道。因此仓库中的工坊包是**接入探针**，不是可上架成品，也不会通过模拟输入代替受支持的游戏接口。

相关文档：

- [V139 官方上传器骨架](reports/v139_official_uploader_skeleton.md)
- [工坊接入差距](reports/v135_workshop_integration_gap.md)
- [原生工坊路径调研](reports/v137_native_workshop_path.md)

## 目录结构

```text
luck_agent/
├── env/             # 状态、动作、棋盘、规则引擎、环境与快照
├── agents/          # Random、Heuristic、Forecast、BC 与诊断策略
├── evaluation/      # 批量评估、轨迹、数据集、预处理与指标
├── training/        # PyTorch 训练和实验配置
├── integrations/    # 实机观察适配器与工坊接入探针
└── data/            # 符号、物品、交互和规则数据

configs/             # 环境、策略和实验配置
tests/               # 单元、回归、数据治理和实验审计
reports/             # 版本化研究报告与当前迭代状态
main.py              # 单局演示入口
evaluate.py          # 统一批量评估入口
run_tests.py         # 测试入口
```

完整仓库审计见 [V140 Repository Audit](reports/v140_repository_audit.md)，最新工作状态见 [Iteration State](reports/ITERATION_STATE.md)。

## 下一步

1. 完成 V150 Weight Decay 单变量、多种子审计。
2. 扩充原游戏规则覆盖，并保持规则数据、引擎和回归测试同步。
3. 在新的独立数据上重新评估模型泛化，避免继续消费现有验证集。
4. 固化训练数据、checkpoint、特征编码和评估配置的版本契约。
5. 取得受支持的游戏状态与候选项接口后，完成工坊端到端实机验证。

## 项目定位

这是一个研究与工程作品集项目，重点是决策抽象、规则模拟、实验设计、模型诊断和可复现性。它不是《Luck be a Landlord》的官方项目，与游戏开发者或发行方没有隶属关系。


