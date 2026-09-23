# Luck be a Landlord AI Decision Project

> 面向《Luck be a Landlord（幸运房东）》的智能决策与策略学习项目。
> 目标是将游戏中的抓牌、删牌、重掷、物品选择及其他交互决策抽象为可训练、可评估、可复现的 AI 决策环境。

## Recruiter Quick View

这是一个持续开发中的个人 AI / Python 工程项目，重点不是复刻游戏 UI，
而是建立一套可用于策略研究和模型训练的决策系统。

### 当前已实现

- 构建统一的游戏状态 `GameState` 与动作 `Action` 表示
- 实现合法动作 Mask 与 `reset / step` 环境交互接口
- 实现 Random Agent、Heuristic Agent 等基线策略
- 支持批量运行、策略比较与可复现实验
- 对符号、物品及部分实例级交互规则进行建模
- 建立自动化测试与规则回归测试
- 支持决策轨迹记录，为监督学习/策略学习提供数据
- 建立 teacher labels、dataset preprocessing 等数据处理流程
- 已开展 Behavior Cloning（行为克隆）训练与验证实验

### Engineering Pipeline

Game Rules  
→ State / Action Modeling  
→ Legal Action Mask  
→ Environment (`reset / step`)  
→ Baseline Agents  
→ Trajectory Collection  
→ Teacher Dataset  
→ Behavior Cloning  
→ Evaluation / Audit

### Project Status

项目目前仍在持续迭代。

当前重点包括：

1. 扩充和校验游戏规则覆盖范围
2. 提高状态转移与复杂交互规则的准确性
3. 完善训练数据生成与质量检查
4. 继续验证 Behavior Cloning 等策略学习方案
5. 建立更加完整的策略评估体系

> 本仓库会明确区分已经实现、实验中和计划中的功能，避免将尚未完成的模型或实验结果描述为已完成。
# 幸运房东训练环境 · V0.1

以找回的 `landlord_fast_env` 为基础，复用已有规则代码和实机目录；没有重做游戏 UI，没有启动模型训练。当前是**已有近似引擎的统一训练接口**，不代表完整原版规则或原版胜率。

原工程：`C:\Users\14489\Documents\Codex\2026-09-13\w\outputs\landlord_fast_env`。
原任务同时包含 BetterLandlord 无动画/加速补丁、LandlordResearch 采集器、实机日志与规则源码索引。
`luck_agent/legacy/fast_env.py` 保持原文件字节不变；`provenance.json` 记录来源与 SHA-256。运行使用本地快照，不依赖原工程路径，也不修改原工程。

## 第一个里程碑

Python 3.11+，全部使用标准库。在当前工程根目录：

```powershell
Set-Location 'C:\Users\14489\Documents\ChatGPT\幸运房东'
python main.py
python main.py --agent heuristic --seed 42
python run_tests.py
python evaluate.py --agent random --games 10000
python evaluate.py --agent heuristic --games 1000
```

默认 Floor 20，保留旧引擎开局的三个 dud。可用 `--config` 指定配置；JSON 配置避免增加 YAML 依赖。随机 Agent 的 RNG 与游戏 RNG 分离。评估不依赖动画、窗口或睡眠。

```text
luck_agent/
  env/
    game_state.py       GameState / SymbolInstance
    action.py           Action / ActionType
    rule_engine.py      旧引擎入口与目录加载
    game_env.py         阶段调度、动作掩码、奖励、reset/step
  data/                 符号、物品、精华、标签关系及历史覆盖记录
  legacy/               原规则核心、原214项测试、目录快照、来源记录
  agents/
    random_agent.py
    heuristic_agent.py
  evaluation/
    evaluator.py
    metrics.py
configs/default.json
tests/test_env.py
main.py                 单局文本演示
evaluate.py             批量评估
run_tests.py            旧规则与新接口统一测试
tools/import_metadata.py
archive/sandbox_v01/    查找旧工程前的简化草稿；不参与当前运行
```

## GameState 契约

核心字段与你提出的结构一致：经济、牌组、物品、资源、决策类型、候选、近期收益、Spin 数、终止标志。额外保留精华、已展示棋盘、效果计数/倒计时/队列、强制选择标志和近期动作。金币为 float，因为旧规则存在分数收益，不能强行截断为 int。

`GameState` 是脱离引擎的快照：修改其嵌套字典不会修改环境。读取状态、合法动作和掩码不消耗游戏 RNG、不生成候选、不提前预览棋盘。种子、RNG 和未来布局均不进入状态；先执行 SPIN，只有需要位置决策时才显示本轮已抽取布局。

`effect_state` 保存旧引擎公开的倒计时、永久加值和待处理效果，防止只保留数量向量丢失规则状态。它仍含重复字段，未来编码器应按机制建立显式类型；完整 Markov 性还需要逐条机制审核，不能仅凭字段齐全宣布完成。

**实例限制**：旧引擎使用类型列表和分组计时器，没有稳定物理实例 ID。当前 `cat:0` 只在当前快照中有效；删除仅开放该类型第一个实例，与旧引擎语义一致。不伪造跨步实例追踪，也不声称可单独删除具有不同成长属性的任意同类实例。升级实例模型需先做规则等价回归。

## 统一 Action 与 Mask

`Action(action_type, target_id=None, secondary_target_id=None)`；抓牌目标为符号 ID，物品目标为物品 ID，删除为上述快照实例 ID，交互为原引擎交互 ID。候选数量可变，不使用固定第1/2/3张输出。保留第二目标字段；旧引擎交换操作暂使用原生 `swap:a:b` 目标字符串。

扩展 KEEP_OPTIONS 表示当前交互/删牌阶段继续，PICK_ESSENCE 表示精华选择。强制选牌时掩码屏蔽跳过；没有资源时屏蔽重掷/删除；终局或截断后所有动作非法。非法 step 在修改环境前抛 ValueError。

```python
from luck_agent.env.game_env import GameEnv
from luck_agent.agents.random_agent import RandomAgent

env = GameEnv()
state = env.reset(seed=123)
agent = RandomAgent(seed=456)
while not (state.is_terminal or state.is_truncated):
    actions = env.legal_actions()
    mask = env.action_mask(actions)  # 此处均合法；也可以传入包含非法动作的超集
    action = agent.choose(state, actions)
    state, reward, terminated, truncated, info = env.step(action)
```

候选与掩码必须来自同一步状态。未来候选评分、BC、DQN/PPO 可共享该接口，不需要每种决策独立环境。当前是 Gym 风格返回值，尚未实现 Gymnasium spaces。

阶段顺序沿用旧驱动：Spin/位置选择 → 主动交互/救租 → 精华 → 物品触发的符号选择 → 常规符号选择 → 删除 → 待领取物品 → 下一转。位置选择只结算一次；每轮删除窗口沿用旧驱动，只执行一次可选删除。决策上限导致 truncated，不当作死亡。

## 数据和规则的复用边界

目录快照含 168 种符号、114 种物品、113 种精华。`data/*.json` 是从旧目录生成的结构化元数据，效果仍在原引擎中执行。`effects=[]` 搭配 `effect_dsl_status=not_migrated` 表示尚未迁移，不表示符号没有效果；不把描述文字当成可执行规则。

原目录把观测收益平均值优先用于部分符号基础值，可能混入实机加成。元数据同时列出原始 `base_value` 与 `legacy_effective_value`；本轮保留行为，不静默替换。历史覆盖报告可能滞后，不能将其声明数视为实机逐项验证数。

## 奖励和策略

V0.1 严格采用：
`reward = (coins_after - coins_before) + 20 * rents_paid - 100 * death + 500 * win`。
金币净变化**包含交租扣款**；同时在 info 中独立记录 spin_income、coin_delta 与各奖励分量，避免混淆产出和余额。终局奖励只发一次，没有人为协同奖励。暂未训练或比较 reward shaping。

RandomAgent 在合法候选上均匀采样。HeuristicAgent 复用原版项目的公开状态抓牌协同、物品和删牌判断，仅作为诊断基线；没有访问实时引擎。旧位置教师通过 deepcopy 实时 RNG 模拟，存在隐藏随机性泄漏风险，因此当前启发式位置动作保守跳过，暂不复用该函数。主动重掷优化和完整 EV/稀释建模留待 V0.2。

## 实验输出和版本路线

`logs/reused/<agent>-<timestamp>/` 保存逐局 CSV、summary.json 和 manifest.json，含种子、配置、源码/目录哈希、来源、Python 和 Git 状态。尚无 Git 提交时 commit 为 null，不伪造版本。跨机器复现需要保留源码并使用一致 Python 版本；这里验证的是同版本确定性。

阶段指标为**已支付租金次数**。剩余金币必须联合通过阶段解读，失败时尚未支付的租金仍在余额内。随机/启发式使用相同种子时，动作可能改变 RNG 消耗路径，不保证随机事件逐步相同。吞吐量为完整 Python 环境和公开状态构造开销，不包含启动与目录加载。

V0.1：完整对局、合法动作、批量评估及复现性。V0.2：一个变量一个变量改进启发式 EV/资源管理。V0.3：冻结策略做大样本同种子比较与置信区间。V0.4：稳定 `(state, action, reward, next_state)` 轨迹格式。V1.0：环境准确性达到要求后引入 PyTorch/BC/DQN。本轮不训练网络，也不把原工程旧模型成绩当作新接口成绩。

## V0.2：基础值审计与单项重掷实验

基础值审计已检查全部168个符号，当前原始基础值与实际 catalog 值无差异、无缺失，因此没有修改规则或基础值。审计只证明快照一致性，不证明完整原版机制正确。

新增可选 `heuristic_reroll`：保留原启发式所有非重掷判断，用公开状态重建一个独立模拟器，抽样16组候选，比较候选启发式分数。预计提升减去1.96倍标准误后还需超过 `0.5 + 0.5 / 剩余重掷次数` 才使用代币。这是经验分数的机会成本代理，不是金币 EV 或长程价值网络。

估值不会复制实时引擎、seed或RNG；采样随机数由公开状态的稳定哈希派生。测试验证改变实时RNG不影响同一公开状态下的动作。收益、候选池、状态机与原启发式其余项均未修改。

```powershell
python tools/audit_catalog.py
python -m luck_agent.evaluation.compare_reroll
python evaluate.py --agent heuristic_reroll --games 300
python run_tests.py
```

对照配置 `configs/v02_reroll_experiment.json` 预先固定300对开发种子与主指标，输出逐局CSV、配对bootstrap区间、最差5对种子和源码/数据哈希。独立种子20000–20999未参与该开发实验，后续在V0.2.2用于冻结验证；工具不会自动更改默认策略。重掷参数在 `RerollConfig` 中集中定义并写入实验manifest。完整transition轨迹仍留在后续里程碑。

## V0.2.1：保持动作一致的重掷估值加速

性能分析显示主要开销来自16次抽样反复扫描候选池、判断有效稀有度。`env/offer_sampler.py` 在一次估值内预计算候选分组，重复抽样仅复制分组并无放回选择。候选顺序、权重、随机调用顺序与稀有槽副作用保持旧实现语义，实时游戏仍使用原规则核心。

`PreparedSymbolOffers` 只用于独立估值模拟器；当牌组、物品、计数、阶段、队列或目录改变时必须重建。目前每次estimate都重新准备，不跨状态缓存，因此不会把旧物品效果带入新状态。

可用 `RerollHeuristicAgent(catalog, sampler_backend="reference")` 重现旧抽样器，`prepared` 为优化实现。二者采用相同的16次抽样、机会成本与不确定性阈值。这不改变默认的 `heuristic` 策略，也不表示重掷策略变强。

```powershell
python run_tests.py
python -m luck_agent.evaluation.benchmark_reroll
```

基准先在300局中逐决策比较新旧动作与完整估值字典，再交替顺序各测3轮、每轮100局，比较逐局结果哈希与中位耗时。通过门槛为零差异且加速比超过1.1。额外差分测试覆盖候选为空、强制跳过、稀有槽耗尽、稀有度缺失、物品改稀有度、信用卡扩展候选及强制分组/稀有度选择。验证结果不能外推为未经测试的所有未来规则等价；以后修改原候选逻辑时需同步检查抽样器。

## V0.2.2：重掷触发诊断与成本单变量实验

`diagnose_reroll` 在不改变策略的完整对局中记录代币持有、估计分差、保守分差、成本、触发原因和阶段分布，输出逐决策/逐局CSV。原因按顺序互斥分类：均值无正提升 → 均值未超过成本 → 保守提升未超过成本 → 重掷；这是一种解释规则，不是因果分解。

```powershell
python -m luck_agent.evaluation.diagnose_reroll --games 300
python -m luck_agent.evaluation.compare_reroll --config configs/v022_cost_experiment.json
```

诊断种子0–299中，297/300局结束时还持有代币。7642次估值中，5105次被成本阈值挡住、435次被不确定性挡住、2082次均值提升非正、20次实际重掷。仅在已观察状态上把固定成本从0.5降至0.25时，满足触发条件的次数为93；这是状态敏感性分析，不是新策略的对局结果。

因此只测试固定成本0.5→0.25，用另一组开发种子300–599做300对完整对局；抽样16次、不确定性系数1.96、随代币变化的成本项和所有游戏规则保持不变。配置及实际两组RerollConfig写入manifest，默认参数不随实验自动变化。开发差值+0.0733，95%区间[+0.020,+0.133]，达到进入冻结验证的门槛。

`python -m luck_agent.evaluation.validate_reroll` 按 `configs/v022_frozen_validation.json` 冻结参数，在20000–20999上各运行原启发式、原成本0.5、候选成本0.25，共3000局。两次配对比较各用97.5%bootstrap区间控制多重比较；候选需超过两个基线且无截断。该范围自本轮起已消耗，不能继续当作未来调参的未见测试集。重跑只能视为复现，不是新验证。

冻结验证已通过：候选平均通过租金5.725，对比原启发式5.663、旧阈值5.680。校正后区间分别为[+0.026,+0.099]和[+0.011,+0.077]。三组各通关1/1000局，未证明胜率改善。可运行验证过的可选策略配置：

```powershell
python evaluate.py --agent heuristic_reroll --policy-config configs/reroll_validated.json --games 300
```

## V0.2.3：删除后倒计时残留修复

旧引擎删除golem、bar_of_soap或matryoshka_doll_1至4时没有同步清理对应倒计时。新拿到的同类符号可能继承旧生命周期。例如删除只剩1次出场的golem后再添加一个，旧引擎会让新golem首次出场就碎成矿石。

`CorrectedRuleEngine` 以小型继承覆盖修复成功删除时的计时队列清理；原始源码保持不变。`EnvConfig.rule_version` 明确选择`legacy`或`removal-timers-v1`，拼写错误直接拒绝。为了不悄悄改变历史实验，默认配置仍是legacy；**使用下面的独立配置运行修复版**：

```powershell
python evaluate.py --agent heuristic_reroll --policy-config configs/reroll_validated.json --config configs/removal_timers_v1.json --games 100
```

manifest记录生效的完整环境配置和策略参数。修复版的100局冒烟/逐局对照已完成、无截断，248项测试通过；普通对局全部相同，因此修复行为主要由专门的定值回归用例验证。V0.2.2的独立验证成绩仍只属于legacy规则，不能自动归给新规则版本。

这不是完整实例模型迁移：实例ID仍是快照内索引，成长加成和出场计时仍存在按类型归并的近似。后续需逐项核对实例语义，不能凭此次修复宣布完整Markov状态或任意实例删除已实现。

## V0.2.4：实例身份契约与迁移基础

`python -m luck_agent.evaluation.audit_instances` 可复现三类表示损失：一个考古学家成长后加成同时作用于两个副本；棋盘只含`spirit`字符串，无法表达两个不同计时副本中的哪一个出场；删除`coin:0`后剩余`coin:1`被重新编号为`coin:0`。

新增`env/instance_store.py`作为规则迁移基础，**尚未替代实际游戏结算**。它提供局内稳定且不复用的ID、独立加成和出场计时、携带真实ID的无放回抽样、精确删除、保持ID的转化以及不可变快照。只给实际出场ID减计时，未知或重复ID整批拒绝；计时到零返回待处理ID，由未来规则引擎决定销毁、保护或转化。

`SymbolInstance`增加`permanent_bonus`、`remaining_appearances`和`identity_scope`；旧适配器明确使用`None/None/snapshot`。`GameState.supports_stable_instances=False`明确其能力，不能将未知个体属性编码成已知零值。新存储实例使用`episode`范围ID，仅在一局内稳定；跨局数据必须结合episode_id区分。

不能把旧对局中类型列表按顺序配对成“真ID”，因为损失已经发生。下一阶段必须在抽样前分配身份，并将实际ID沿棋盘、触发者、目标、生成/销毁/转化传递；旧启发式也需要通过ID查符号，而不能再从target字符串解析类型。

255项测试通过；相同100局的CSV逐行完全一致，证实本轮新增元信息和基础模块未改变当前对局结果。验证命令：

```powershell
python run_tests.py
python -m luck_agent.evaluation.audit_instances
```

## V0.2.5：首个真实实例结算后端

`instance-spirit-v1`把InstanceStore接入现有GameEnv和动作掩码，幽灵从真实ID抽样、棋盘收益、出场倒计时到销毁事件全程按实例处理。同类第二个实例可以独立删除，幸存者不重编号。

这是**规则迁移实验后端**，复用旧目录、候选算法、租金结算、资源发放、阶段调度和奖励；允许的符号为coin/pearl/cherry/flower/cat/spirit，物品仅undertaker，精华为空，Floor固定1。候选池显式缩小，因此结果不能和原完整近似环境直接比较。其他符号、物品、精华、类型级永久加成和位置交换直接拒绝；不会偷偷回退到旧spin。默认完整近似环境未替换。

```powershell
python main.py --agent heuristic --config configs/instance_spirit_v1.json --seed 3
python evaluate.py --agent random --config configs/instance_spirit_v1.json --games 1000
python evaluate.py --agent heuristic --config configs/instance_spirit_v1.json --games 1000
python run_tests.py
```

此后端的GameState支持`supports_stable_instances=True`，symbols包含真实局内ID与计时。`visible_board_ids`和`visible_board_instances`记录**最近一次Spin结算前**棋盘，可能含刚销毁的实例；当前symbols则是结算后的牌组。step的info.instance_events提供按ID记录的收益和销毁事件，后续菜单动作不会重复发出。旧后端仍标记False，这些ID字段为空。

HeuristicAgent删除评分改为通过当前state的ID→符号映射查值，兼容两类ID，不再解析目标字符串。没有从旧中途类型棋盘或计时队列猜测实例关系；这类状态注入会拒绝，必须从新对局启动。

当前复用目录的spirit基础收益为6；旧独立测试夹具中的4不是该目录值。本次没有改数据：四次出场得到24基础收益，第四次收益后销毁。undertaker保留幽灵并暂停计时，沿用旧引擎在此规则上的语义。

266项测试通过；单幽灵对照覆盖20个种子×6次Spin，收益、牌组、计时与RNG状态和旧引擎一致。另测两幽灵不同计时、真实20格抽样只抽到第二个、精确删除、销毁事件归属和不支持机制拒绝。随机/启发式各1000局无截断，完整近似旧后端的100局指标逐局不变。

### V0.2.6：肥皂与泡泡实例规则

新增 configs/instance_soap_v1.json：复用原工程，按真实 ID 处理肥皂生成、泡泡计时和销毁。两种基线各完成 1000 局，均无截断。完整范围、已知差异和命令见 [实验报告](reports/v026_soap_migration.md)。

### V0.2.7：煤炭转化为钻石

新增 configs/instance_coal_v1.json：煤炭累计出场 20 次后保留 ID 转为钻石，迁移同场钻石协同收益。279 项测试通过，两种策略各完成 1000 局且无截断；启发式平均租金表现低于随机，需要后续轨迹诊断。详见 [实验报告](reports/v027_coal_migration.md)。

### V0.2.8：可重放的状态转移轨迹

运行 `python diagnose_coal.py --games 100` 保存两种基线的压缩 JSONL 轨迹、逐局煤炭统计并精确重放。282 项测试通过；本轮观察到启发式大量选入煤炭却没有成熟，选牌与删除评分存在不一致，尚未改动策略。详见 [诊断报告](reports/v028_coal_diagnosis.md)。

### V0.2.9：煤炭评分单变量验证

运行 `python compare_coal.py` 比较原评分与取消煤炭 +1.2 加分的候选。285 项测试通过；冻结候选在另一组 1000 局中平均通过租金从 2.052 提升至 4.946，配对提升 95% 区间为 [2.736, 3.057]。默认策略保持不变，候选仅在当前受限环境验证。详见 [实验报告](reports/v029_coal_experiment.md)。

### V0.3.0：已验证候选行为采集

运行 `python diagnose_coal.py --games 100 --include-validated` 采集三种策略，轨迹明确记录策略名称和参数。286 项测试通过；本轮 300 局共 27448 步全部精确重放，候选数据尚未用于训练。详见 [采集报告](reports/v030_behavior_collection.md)。

### V0.3.1：整局数据读取与分区

新增 `prepare_dataset.py`，按种子哈希划分数据，同种子的不同策略轨迹保持同分区。290 项测试通过；300 局分为 237/24/39 局，种子无跨分区重叠。现有数据仍是开发数据，未开始训练。详见 [划分报告](reports/v031_dataset_split.md)。

### V0.3.2：可变候选批次

新增 `luck_agent/evaluation/batching.py`，编码实例目标与候选动作，并提供各自的填充掩码。295 项测试通过；27448 步完整读取为 430 批，标签和掩码验收通过。仅支持当前煤炭受限环境，不含模型训练。详见 [批次报告](reports/v032_candidate_batches.md)。

### V0.3.3：数值缩放与批次打乱

新增训练分区专用的 scalar 缩放与有限缓冲区打乱。297 项测试通过；候选的 11348 条训练样本同轮顺序可复现、跨轮顺序变化且不丢不重，验证/测试复用冻结参数。详见 [预处理报告](reports/v033_preprocessing.md)。

### V0.3.4：BC 数据与指标约定

冻结仅对多合法候选决策计算损失的规则，提供标准库参考 masked NLL。301 项测试通过；候选训练集有 4638 步多选决策、6710 步唯一动作，后者不进入决策准确率。没有训练模型。详见 [契约报告](reports/v034_bc_contract.md)。

### V0.3.5：在线候选评分接口

新增 CandidateAgent，复用离线编码、校验评分输出并映射回原始 Action。306 项测试通过；100 局 10041 步闭环对照全部一致，推理不改变环境 RNG。确定性评分器仅用于接口验收，没有训练模型。详见 [在线接口报告](reports/v035_online_adapter.md)。

### V0.3.6：最小模型前向验收

独立 `.venv-model` 环境新增 7489 参数的 PyTorch 候选评分模型。308 项测试通过；11348 条样本的损失与参考实现差异小于 1e-5，未训练模型完成 10 局闭环，权重未更新。详见 [模型验收报告](reports/v036_model_forward.md)。

### V0.3.7：首次 BC 冒烟训练

固定三轮、534 次更新，保存并重载最终模型。开发闭环各 100 局：未训练/训练后/教师平均通过租金为 1.00/5.38/5.39，均无截断；离线符号选择仍有差距。308 项测试通过。详见 [训练报告](reports/v037_bc_smoke.md)。

### V0.3.8：BC 失败诊断

冻结模型，发现 110 次符号分歧中 86 次为教师同分换选、24 次为选取/跳过分歧。最差五局已重放，提出均值池化缺少显式牌组数量的待验证假设。本轮未训练，309 项测试通过。详见 [诊断报告](reports/v038_bc_diagnosis.md)。

### V0.3.9：牌组数量特征对照

固定三轮仅增加数量输入，平均通过租金 5.38→5.22，差值 95% 区间 [-0.62, 0.29]；选取/跳过分歧仍为 24。未获改善证据，保留原模型。310 项测试通过。详见 [对照报告](reports/v039_count_experiment.md)。

### V0.4.0：阈值附近覆盖审计

阈值附近已有训练数据，但原模型在 18–19 个符号时仍错误跳过 28.6%；不足 18 个时自身路径的错误跳过比例升至 19.8%。两模型各 100 局重放一致，本轮未训练，311 项测试通过。详见 [覆盖报告](reports/v040_threshold_coverage.md)。

### V0.4.1：自身轨迹教师标注

仅在训练分区 79 个种子采集原 BC 自身轨迹：13638 步全部精确重放，含 5816 步多选决策、1128 次师生分歧。执行动作与教师标签分开保存，未混入训练，313 项测试通过。详见 [标注报告](reports/v041_teacher_labels.md)。

### V0.4.2–0.4.3：显式监督读取与聚合对照

教师监督读取器分离执行动作和训练标签；冻结 534 次更新的匹配预算实验。原始组/50% 聚合组平均通过租金为 5.01/5.17，差值区间 [-0.25, 0.63]，选取/跳过分歧反而增至 31。315 项测试通过，暂不替换模型。见 [读取报告](reports/v042_teacher_dataset.md) 与 [实验报告](reports/v043_aggregation_experiment.md)。

### V0.4.4：分来源拟合诊断

聚合组在新增状态上错误跳过 600→94，但原始状态上的反向选取错误 48→103。完整有序编码输入未发现标签冲突。冻结模型，仅审计，316 项测试通过。详见 [来源诊断](reports/v044_source_diagnosis.md)。

### V0.4.5：25% 标注比例开发实验

固定预算下平均通过租金 0%/25%/50% 为 5.01/5.64/5.17；25% 对 0% 配对区间 [0.18, 1.13]。317 项测试通过，原始对照精确复现。停止比例搜索，候选待新种子冻结验证。详见 [比例报告](reports/v045_quarter_mix.md)。

### V0.4.6：冻结验证未通过

新种子 40000–40999 各 1000 局：25% 候选平均通过租金 5.176，0% 基线 5.393，差值区间 [-0.367, -0.065]。双方 90 次通关、零截断，不推广候选，停止比例调参。317 项测试通过。详见 [验证报告](reports/v046_frozen_validation.md)。

### V0.4.7：礼物实例规则

新增 instance-present-v1，复用旧工程的 12 次出场后奖励 10 金币并销毁规则。323 项测试通过，两种基线各 1000 局无截断，旧煤炭环境回归不变。旧模型不支持新环境，见 model_registry.json。详见 [迁移报告](reports/v047_present_migration.md)。

### V0.4.8：时间机器初始寿命

新增 instance-time-v1：新获得煤炭/礼物寿命为 15/7 次，已有实例不追溯改变。328 项测试通过，旧后端逐局回归一致，两种基线各 1000 局无截断。详见 [规则报告](reports/v048_time_machine.md)。

### V0.4.9：棋盘位置与实例邻接

复用旧工程 4×5 布局和八方向邻接，将位置连接到真实实例 ID。333 项测试通过，历史 6757 步轨迹精确重放，时间机器后端 100 局指标一致。尚未新增邻接交互或训练。详见 [棋盘报告](reports/v049_board_contract.md)。

