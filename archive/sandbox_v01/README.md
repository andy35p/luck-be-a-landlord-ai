# 幸运房东决策研究框架 · Version 0.1

本版本是可运行、可测试的**简化规则研究沙盒**，不是《幸运房东》完整复刻，不能用本项目的通关率代表原版表现。全部数值、名称、租金与交互均为研究用定义，未声称校验过原版。Python 3.11+，仅标准库；当前没有训练网络，不依赖 PyTorch。未来进入 BC 阶段再引入 PyTorch，避免空实现。

## 当前目标与现状

交付一个小而完整的实验闭环：状态 → 合法候选 → 基线决策 → 环境结算 → 轨迹 → 评估 → 单变量实验。支持符号选择/跳过、物品选择/跳过、删牌、重掷、Spin、邻接加成、摧毁和转化。6 种符号、2 种可重复堆叠物品、4 个租金阶段；不支持原版全部符号、生成、精华、事件或 GUI 自动操作。

```text
luck_agent/
  knowledge.py                JSON 数据加载、引用检查、规则哈希
  data/                       symbols/items/interactions/rarity/effects/schema.json
  env/
    state_encoder.py          Symbol、不可变 State、派生特征
    action_space.py            ActionType、统一 Action
    simulator.py               结算与邻接关系
    game_env.py                Config、GameEnv、动作掩码与奖励
  agents/baselines.py          随机、贪心、启发式候选评分
  evaluation/evaluator.py      多种子评估、完整轨迹、失败报告
experiments/configs/           基础与租金压力实验配置
tests/test_framework.py        规则及复现测试
reports/v01.md                 本轮实测分析
logs/                         自动生成，各运行独立目录
```

## State、Action、Episode

`State` 包含符号实例及唯一 ID、上次结算后的棋盘位置、物品、金币、租金、距租金 Spin 数、阶段、Spin 总数、资源、决策阶段、候选、最近 10 次收益、最近 20 条动作、终止与胜利标志。符号属性与关系从版本固定的知识库查询。`board` 是上次布局，不是下一轮预测；Spin 时重新抽样摆放。

Observable：上述公开字段。Derived：数量、熵、集中度、历史均值、预计租金缺口、协同对数。Historical：近期收益和决策。Hidden：私有 RNG 状态、未来布局、未来候选、转化随机结果；不进入策略观察。种子仅写入实验元数据，不传给策略作为状态特征。

`Action(action_type, target, secondary_target, parameter)` 是统一结构。符号/物品选择的 target 是候选位置，删除 target 是实例 ID。所有策略使用同一接口；可变候选分别打分。保留 KEEP_OPTIONS、SELECT_INTERACTION、SPECIAL_ACTION 枚举，但本里程碑没有对应事件，因此不开放这些动作。

Episode 从 3 个初始符号、0 金币、2 次删除和 2 次重掷开始。每次 Spin 抽取至多 6 个符号，无放回随机摆放；每 4 次 Spin 交租，支付失败终止，通过最后阶段胜利终止。非租金 Spin 后选符号；中途成功交租后先选物品再选符号。无资源恢复，没有无成本循环。

形式化：S 是公开状态，A 是掩码允许的动作；P 由随机抽样和知识库效果共同定义；R 默认仅胜利 +1、失败 -1；终止后不允许继续 step。本沙盒公开状态足以表达机制，伪随机生成器内部状态属于环境实现而非策略特征。

## API 与数据库

```python
from luck_agent.env.game_env import GameEnv
from luck_agent.agents.baselines import Agent

env = GameEnv()
state = env.reset(seed=42)
agent = Agent("heuristic", seed=100042)
while not state.terminated:
    candidates = env.candidates()
    mask = env.action_mask(candidates)
    legal = tuple(a for a, valid in zip(candidates, mask) if valid)
    action, probability, score = agent.choose(state, legal)
    state, reward, terminated, truncated, info = env.step(action)
```

非法动作抛 ValueError 且不修改状态。接口采用五元返回值，但尚未声称兼容 Gymnasium spaces。候选顺序只在当前状态有效，不能缓存下一个状态的索引。

`schema.json` 是五份 JSON 组合成一个对象后的 JSON Schema；加载器还检查 ID 唯一性和关系引用。目前内置库受测试覆盖，但加载器不是完整 JSON Schema 验证器。符号节点字段为 id/name/rarity/base_income/tags；关系边为 source/target/relation/amount/probability；物品字段为 effect/targets/amount。未实现的机制不能仅加 JSON 就假定引擎支持。

结算次序：基础收益 → 邻接加成 → 摧毁 → 转化 → 物品。正交邻接、不跨行、不对角。摧毁保留本轮基础收益，每个目标只能被摧毁一次；转化保留实例 ID，新基础收益下轮生效。没有实现生成，故没有假造生成测试。

## 策略与奖励

随机策略在合法候选上均匀采样。贪心策略按符号基础收益及物品当前贡献评分，是即时收益代理，并非精确模拟全部布局的 EV。启发式增加邻接协同代理、种子未来潜力、租金压力与满盘稀释惩罚。分数不冒充学习得到的 Q 值或校准后的存活概率。

本轮贪心和启发式均保守地保留删除及重掷资源；随机策略能够使用这些动作。资源机会成本只有固定代理值，后续需独立实验改进。

`sparse`：终局 ±1；`dense`：再加 income/100 与每通过阶段 0.1；`shaped`：sparse + γΦ(s')−Φ(s)，Φ 为租金储备比例，终态为 0。后者使用决策步折扣，训练时必须保持同一 γ；跨多个菜单动作的时间尺度尚未研究。当前实现三种奖励，并未训练或证明哪一种更好；终态 shaping 抵消有单测。

## 实验与运行

在项目根目录运行，无须 pip 安装：

```powershell
Set-Location 'C:\Users\14489\Documents\ChatGPT\幸运房东'
python -m unittest discover -s tests -v
python -m luck_agent.evaluation.evaluator --config experiments/configs/v01.json
python -m luck_agent.evaluation.evaluator --config experiments/configs/v01_stress.json
```

两份配置都使用开发种子 0–29；测试种子 1000–1019 保留，未运行。策略固定后可使用 `--split test` 作独立评估，不能再依据该集合调参。

每次运行生成 manifest.json、episodes.csv、summary.json、comparisons.json、trajectories.jsonl、failures.json 和 failure_report.md。记录配置、版本、数据库及源代码哈希、Git commit/status、Python 版本、种子和训练步数（0）。当前仓库没有提交时 git_commit 为 null，不能伪造 commit。精确复现还需保存对应源代码；哈希本身不替代源码归档。

指标包括胜率及 Wilson 区间、均值/中位数奖励、剩余金币、存活 Spin、阶段分布、逐阶段通过率、策略熵和资源使用量。资源“效率”需反事实实验，目前明确为 null；TensorBoard 延后至训练阶段。同种子配对并不保证不同策略经历相同随机事件，因为动作会改变 RNG 消耗路径。

失败报告保留死亡前 5 步的状态、合法动作、选择概率、启发式分数、实际折扣回报；estimated_value 为 null。没有可靠价值模型时不自动断言“错误跳过高价值符号”。

## 测试与下一步

12 项测试覆盖基础收益、物品、邻接边界、单次摧毁、转化延迟收益、租金成败、掩码、非法动作、资源耗尽、终态、shaping、公开状态及多种子可复现轨迹。测试保证当前定义内的一致性，不保证原版规则一致性。

先校验原版机制并加回归用例，再研究资源决策和准确 EV。达到环境正确性门槛后才收集示范轨迹、接入 PyTorch BC / Value Network；不在本轮生成 DQN/PPO 空壳。
