# V0.2.5：幽灵按真实实例结算

## 【当前目标与现状】
把V0.2.4的实例存储真正接入GameEnv，迁移一个计时机制：spirit。稳定身份必须在抽样前存在，沿棋盘、收益事件、计时与销毁传递。不开新UI、不训练模型、不重写全部游戏规则。

## 【发现的问题与原因假设】
旧棋盘只有类型字符串，无法知道两个同类幽灵中哪个出场；计时队列头的更新可能落在未抽中的副本。按实例ID抽样并只更新出现的ID，可以消除这一表示歧义。
测试过程另发现原简化测试夹具把spirit收益设为4，而复用游戏目录值为6。修正新测试的预期以匹配目录，未修改游戏数据库或为凑测试改变结算值。

## 【本轮修改】
- `env/instance_spirit_engine.py`：继承旧环境的候选、租金与资源逻辑，用InstanceStore实现受限范围的抽样、收益、幽灵计时、undertaker暂停与精确销毁。
- `env/game_env.py`：选择instance-spirit-v1后端，仍使用原阶段调度、统一Action/Mask及奖励。删除目标使用真实ID。
- `env/game_state.py`：新增visible_board_ids/visible_board_instances，明确为上次结算前棋盘快照；当前牌组保存结算后状态。
- `agents/heuristic_agent.py`：删除动作按state映射查符号，不再从ID文本解析类型。
- `evaluation/evaluator.py`：manifest增加实际生效目录哈希，避免缩小后的候选池与原目录混淆。

## 【支持范围】
仅coin、pearl、cherry、flower、cat、spirit；物品仅undertaker；无精华；Floor 1研究场景。该组合中前五种只有基础收益，不存在猫吃牛奶等未迁移交互。候选分布基于旧算法和显式缩小的原目录。
不支持的选择、物品、位置动作、类型级成长加成直接拒绝；类型列表或旧计时队列不能无损导入新实例状态。旧完整近似后端与原源码保留不变。

## 【实验设计与评价指标】
1. 成对实例定值回归：幽灵A剩余1次、B剩余4次，只展示B，结果必须为1和3，A不能被销毁。
2. 真抽样回归：牌组超过20个，在固定随机种子下只抽到B，检查抽样ID与更新对象一致。
3. 单个幽灵与旧引擎对照：20个种子，各6次Spin，比较金币收益、牌组、计时与RNG状态。
4. 测试四次收益后精确销毁、undertaker暂停、按ID删除第二个副本、过期目标Mask、事件不重复、未知机制拒绝、读取状态不消耗随机数。
5. Random/Heuristic各1000局检查端到端完整性，不以受限环境成绩证明原版能力。

## 【实现与测试结果】
**266项测试全部通过**；单实例与旧规则对齐，成对计时歧义用例得到正确实例结果。旧完整近似后端的相同100局指标逐行一致，见`v025_legacy_regression.json`。

|受限后端指标|Random|Heuristic|
|---|---:|---:|
|局数|1000|1000|
|平均通过租金|2.309|4.655|
|平均Spin数|17.885|34.437|
|通关局数|0|2|
|截断局数|0|0|
|测得局/秒|148.94|63.38|

候选池/Floor与之前完整近似实验不同，这些数值只用于端到端验收，不做跨环境策略提升结论。日志：`logs/reused/random-20260922T023813883222Z`、`logs/reused/heuristic-20260922T023908813043Z`。

## 【运行命令】
```powershell
python run_tests.py
python main.py --agent heuristic --config configs/instance_spirit_v1.json --seed 3
python evaluate.py --agent random --config configs/instance_spirit_v1.json --games 1000
python evaluate.py --agent heuristic --config configs/instance_spirit_v1.json --games 1000
```

## 【预期结果与下一步】
本轮达到“一个规则从抽样到结算保持真实ID”的门槛；GameState仅在该受限后端声明支持稳定实例。整个旧游戏的身份迁移仍未完成。
下一轮优先迁移一个生成/销毁机制，并让所有新生成符号获得新ID、事件显式关联触发者与产物；再处理转化的身份继承。每增加一种规则都要求边界测试和兼容场景与旧规则对照，不直接打开完整目录或退回按类型结算。
