# V0.2.3：删除目标与残留效果状态

## 【当前目标与现状】
继续使用找回的高速引擎，检查GameState里的删除目标与效果状态是否一致；不改游戏UI、不训练模型。本轮还完成上一轮冻结验证的报告落盘和`--policy-config`运行入口，验证过的0.25配置位于`configs/reroll_validated.json`。

## 【发现的问题】
删除golem、bar_of_soap和matryoshka_doll_1–4后，旧引擎没有同步删除对应的第一个计时器。其他部分计时符号已在旧remove方法里清理，不能重复清理。

最小复现：牌组只有golem、golem_ttls=[1]、删除次数1；删除后重新获得golem并Spin。旧实现保留[1]，新符号第一次出场即生成5个矿石。bar_of_soap同样会第一次出场就消失，而不是获得自己的生命周期。

## 【原因假设】
旧引擎用类型列表和并列计时队列表示符号，remove方法漏掉新增的几种计时符号；再次添加时，初始化逻辑看到队列长度已够，不会创建新计时器。

## 【本轮修改】
- `env/rule_engine.py`：新增CorrectedRuleEngine，只在旧remove成功后清理漏掉的计时队列；失败动作不变，未初始化空队列不报错。
- `env/game_env.py`：新增显式rule_version选择，非法版本名拒绝。默认legacy保持旧实验可复现。
- `configs/removal_timers_v1.json`：修复版独立运行配置。
- `evaluation/evaluator.py`：记录完整生效EnvConfig和RerollConfig，支持`--policy-config`，避免仅保存文件中显式字段而遗漏默认值。

## 【实验设计与评价指标】
定值测试分别检验：重获golem不继承旧计时、同类两个符号删除第一个时只移除第一个计时、肥皂清理、四阶段套娃清理、无代币时失败操作不改状态、空队列、GameEnv删除目标与状态同步。
新旧规则各用种子0–99、同一个0.25重掷策略执行100局，逐局比较阶段、Spin、金币、奖励、动作数量、资源消耗和终止字段。目标是复现特定bug并修复，同时检查普通路径有无意外变化，不以胜率上涨判定规则修复正确。

## 【实现与测试结果】
**248项测试全部通过**。旧源码哈希一致性检查仍通过，原工程没有修改。
100局逐局对照差异数为0；修复版平均通过5.62次租金，0截断。普通种子没有触发可见差异，不能据此宣称覆盖所有删除机制；专门的定值测试确认了修复路径。
批量结果：`logs/reused/heuristic_reroll-20260922T021256157657Z/`；对照汇总：`reports/v023_rule_comparison.json`。

## 【运行命令】
```powershell
python run_tests.py
python evaluate.py --agent heuristic_reroll --policy-config configs/reroll_validated.json --config configs/removal_timers_v1.json --games 100
```

## 【预期结果与下一步】
修复后的新golem首轮仍存在，计时从5变4；删除其中一个副本不影响剩余计时。已验证这些条件，保留修复版配置。
当前默认仍为legacy以保留历史实验行为，运行修复版需显式指定配置。V0.2.2冻结验证属于legacy，不宣称在新规则上已再次独立验证。
更大的问题仍是稳定实例身份：类型索引不能保证跨Spin追踪，永久加成按类型保存可能混合同类个体。下一轮应先用最小成对实例场景确定迁移要求，再决定实例模型改造范围，而非直接训练网络。
