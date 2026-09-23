# V0.4.8：时间机器的实例初始寿命

新增显式 instance-time-v1，在礼物版本范围上加入物品 time_machine。继续复用恢复工程；不改默认后端、旧版本候选池或旧模型。

## 旧代码语义与实现

恢复工程在 choose(symbol) 时决定煤炭和礼物的初始计时。物品获取代码不修改已有队列，因此新版本沿用：

- 未持有时间机器时获得：煤炭 20 次、礼物 12 次。
- 持有时间机器时新获得：煤炭 15 次、礼物 7 次。
- 获得物品前已有实例，包括已经部分倒计时的实例，剩余次数不变。
- 多个时间机器不叠加，旧规则按“是否拥有”判断。
- 幽灵、泡泡、肥皂寿命不受影响。其他尚未迁移符号依旧不开放。

公共实例基类新增 initial_lifetime 钩子和 supported_items 范围，原默认实现保持原行为。独立时间机器子类仅覆盖煤炭/礼物的初始寿命。reset 清除物品效果；实例状态始终是计时权威来源。

这是恢复工程的明确行为，不声称已验证原版所有时间机器交互。煤炭成熟仍原 ID 转为钻石，礼物成熟仍奖励 10 后销毁。

## 验证

328 项测试通过，新增：获取前后新旧副本、部分消耗计时不重置、重复物品不叠加、其他寿命不变、重置、缩短后的完整生命周期、GameEnv 物品动作和旧版本拒绝边界。

与旧引擎对照：10 个种子 × 煤炭/礼物 × 先有物品/后得物品 × 22 次结算，收益、牌组、计时和 RNG 状态逐步一致。旧煤炭与礼物版本启发式各 100 局全部字段与历史 CSV 一致，见 v048_legacy_regression.json。保留的旧 fast_env.py 未改。

## 批量验收

开发种子 0–999，现有默认 Random / Heuristic 各 1000 局，无训练或评分调整。

| 指标 | Random | Heuristic |
|---|---:|---:|
| 平均通过租金 | 1.930 | 2.118 |
| 平均 Spin 数 | 15.598 | 16.880 |
| 通关局数 | 0 | 8 |
| 截断局数 | 0 | 0 |

日志：logs/reused/random-20260923T012154115746Z、logs/reused/heuristic-20260923T012155478925Z。候选物品池改变，结果仅作端到端验收，不用来推断时间机器提高或降低胜率。旧 BC 编码器和检查点仍限定煤炭版本，未应用到新环境。

```powershell
.\.venv-model\Scripts\python.exe run_tests.py
python main.py --agent random --config configs/instance_time_v1.json --seed 3
python evaluate.py --agent random --config configs/instance_time_v1.json --games 1000
python evaluate.py --agent heuristic --config configs/instance_time_v1.json --games 1000
```

下一步可检查一种消耗相邻符号的交互，先建立棋盘位置及邻接的明确契约，再迁移销毁目标与成长奖励；不要把旧引擎的类型列表直接当作完整空间状态。
