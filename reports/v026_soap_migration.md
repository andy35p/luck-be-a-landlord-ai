# V0.2.6：肥皂生成与泡泡寿命

继续复用已找回工程的目录、候选、租金和资源流程。新增显式选择的 `instance-soap-v1`，在幽灵实验范围上加入 bar_of_soap 和 bubble；仅 Floor 1、物品 undertaker、无精华。默认完整近似后端和 instance-spirit-v1 的范围不变。

## 实现

肥皂每次出场生成一个具有独立新 ID、寿命为 3 的泡泡；第三次出场仍生成泡泡，随后销毁自身。泡泡在出场获得基础收益之后消耗一次寿命，第三次后销毁。新生成泡泡不属于本轮结算前棋盘，本轮不支付收益也不消耗寿命。未抽中的实例不更新。undertaker 只暂停幽灵寿命。

生成事件包含 source_instance_id 和新实例 instance_id；销毁事件记录准确实例及原因。GameState 的牌组是结算后状态，visible_board_instances 保留结算前快照。原类型计时列表仅由实例状态同步，不能反向覆盖实例寿命。

已知与旧代码差异：旧代码在后置肥皂过期处理中漏增 destroyed_count / destroyed_history；新实验后端把肥皂自然销毁也记录进去。当前支持物品不依赖这些统计，但未来迁移销毁触发机制时需要明确验证此语义。原源码未修改。

## 验证

- 273 项测试通过，包含原工程的保留测试。
- 20 个种子 × 7 次结算：单肥皂场景与旧引擎收益、牌组、泡泡/肥皂计时和 RNG 状态逐步一致；销毁计数采用上述明确修正。
- 覆盖最后一次生成、不同年龄副本、多个父实例归因、按 ID 删除、泡泡完整生命周期、undertaker 边界，以及超过 20 个符号时只更新被抽中的肥皂。
- 旧幽灵版本 Random / Heuristic 各 100 局，全部逐局指标与上一轮保存结果一致，见 `v026_spirit_regression.json`。

## 批量验收

种子 0–999，仅作开发验收，不是未使用的策略验证集。没有进行训练。

| 指标 | Random | Heuristic |
|---|---:|---:|
| 局数 | 1000 | 1000 |
| 平均通过租金 | 2.645 | 4.498 |
| 平均 Spin 数 | 19.984 | 33.561 |
| 通关局数 | 0 | 11 |
| 截断局数 | 0 | 0 |
| 实测局/秒 | 127.31 | 63.61 |

受限候选池已改变，不与旧实验跨环境比较策略优劣，也不代表原版胜率。
日志：`logs/reused/random-20260922T024925448231Z` 和 `logs/reused/heuristic-20260922T024941946928Z`，包含逐局 CSV、汇总和来源清单。

```powershell
python run_tests.py
python main.py --agent heuristic --config configs/instance_soap_v1.json --seed 3
python evaluate.py --agent random --config configs/instance_soap_v1.json --games 1000
python evaluate.py --agent heuristic --config configs/instance_soap_v1.json --games 1000
```

下一步：迁移一种转化机制，明确转化前后 ID 是否延续、计时如何重置以及事件如何关联，然后再扩大规则范围。
