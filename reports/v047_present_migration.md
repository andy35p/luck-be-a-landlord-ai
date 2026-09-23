# V0.4.7：回到环境规则，迁移礼物寿命奖励

停止围绕 BC 混合比例调参，本轮继续复用旧工程，新增显式 instance-present-v1。它在煤炭实例后端基础上增加 present，仍仅 Floor 1、物品 undertaker、无精华。默认环境和旧模型范围不变。

## 恢复规则

旧 fast_env.py 中礼物累计出场 12 次后额外支付 10 金币并销毁；未出场不消耗寿命。新实例实现按真实 ID 更新，最后一次基础收益加上到期奖励归入该实例 payout 事件，随后记录 present_lifetime 销毁。仅保留一个最终收益事件，不另加奖励 shaping。删除礼物不提前支付到期奖励。undertaker 不暂停礼物，time_machine 仍未迁移并明确拒绝。

此处沿用恢复工程的具体数值，不声称已对照原版完整游戏的全部交互。到期奖励不会让未出场副本获益。旧模型及其词表不支持礼物，因此没有将模型直接应用到新环境。

## 验证

323 项测试通过。新增测试覆盖完整 12 次寿命、最后奖励只触发一次、两个不同寿命副本、精确删除且无奖励、undertaker 边界、超过 20 个符号真实抽样只更新出场副本、GameEnv 奖励与结算前快照以及旧版本范围限制。

20 个种子各 14 次 Spin，在单礼物兼容场景逐步对照旧引擎：收益、牌组、计时、销毁记录和 RNG 状态一致。旧 instance-coal-v1 启发式的相同 100 局全部指标与原日志一致，见 v047_coal_regression.json。原 fast_env.py 未修改。

## 批量验收

使用开发种子 0–999，策略保持现有默认评分，未进行优化或训练。

| 指标 | Random | Heuristic |
|---|---:|---:|
| 局数 | 1000 | 1000 |
| 平均通过租金 | 1.927 | 2.120 |
| 平均 Spin 数 | 15.587 | 16.981 |
| 通关局数 | 0 | 10 |
| 截断局数 | 0 | 0 |

候选池变化，不能用这些结果与旧环境直接比较策略强弱。日志：logs/reused/random-20260923T011158683594Z、logs/reused/heuristic-20260923T011200103110Z。

## 基线登记

reports/model_registry.json 记录匹配预算 0% 基线及未通过冻结验证的 25% 候选，含检查点哈希、状态和明确的 instance-coal-v1 范围；两者均标为不支持 present。早期 V0.3.7 模型是历史参考，没有参与 V0.4.6 的冻结比较，不能凭那次结果替它排序。

```powershell
.\.venv-model\Scripts\python.exe run_tests.py
python main.py --agent random --config configs/instance_present_v1.json --seed 3
python evaluate.py --agent random --config configs/instance_present_v1.json --games 1000
python evaluate.py --agent heuristic --config configs/instance_present_v1.json --games 1000
```

下一步可迁移 time_machine 对初始寿命的影响，先明确获得物品前后已有副本与新副本的区别，再扩大交互范围。继续让环境测试先于模型更新。
