# V0.3.2：候选动作编码与批次读取

新增 `luck_agent/evaluation/batching.py`，仅使用标准库，不安装 PyTorch、不训练模型。复用现有状态、统一动作和轨迹索引，不改游戏规则或策略。

## 编码契约

版本为 coal-candidates-v1，仅支持 instance-coal-v1 的已迁移范围。词表来自该后端的固定候选目录，按名称排序，0 保留给填充；实际词表保存在 `v032_batch_checks.json`。

- 状态数值：coins、current_rent、spins_until_rent、rent_stage、reroll_tokens、removal_tokens、last_spin_income、spin_count，当前保留原始尺度。
- 每个牌组实例：[符号 token、永久加成、剩余出场数或 0、是否存在计时]。无计时与剩余 0 不混同。
- 已有物品：物品 token 列表。
- 每个候选动作：[ActionType+1、目标符号 token、目标物品 token、目标实例在牌组中的位置+1]。删除动作通过实例 ID 查找位置；同类副本可区分。
- 监督标签：当前候选列表中的选择位置，不是固定全局动作类别。候选顺序改变时标签随之改变。

批次对牌组、物品、候选分别填充，分别返回 deck_mask、items_mask、candidates_mask。masked_argmax 只比较有效候选，拒绝全无效掩码。reward、terminated、truncated 单独保留；策略、seed、step、原始动作与实例 ID 留在 metadata，不进入输入特征。未来状态不进入编码。

当前只编码这个受限范围中支持的动作；第二目标、精华或其他未迁移交互直接拒绝。没有声称是完整游戏的无损状态编码：近期收益序列、历史、棋盘及通用 effect_state 未纳入此初版。原始轨迹仍完整保留，后续规则扩展必须更新编码版本。

## 读取与验收

iter_batches 要求显式指定分区和策略列表，校验来源清单哈希、轨迹哈希、策略参数、环境、索引中的分区归属及局长度。按文件/局顺序读取，不随机打乱，不丢最后一个小批次。必须消费完整迭代器才能完成尾部的缺局检查；这是读取工具，不是独立的认证格式。

295 项测试通过：精确删除指针、填充屏蔽、候选置换、未来信息与 seed 不进入特征、未支持的第二目标拒绝。另对三种策略的全部分区做实际读取验收，batch_size=64：

| 分区 | 转移数 | 批次数 | 种子数 |
|---|---:|---:|---:|
| train | 21643 | 339 | 79 |
| validation | 2558 | 40 | 8 |
| test | 3247 | 51 | 13 |

合计 27448 步、430 批，全部标签位于有效候选。335428 个填充位置经过赋高分的掩码检查，没有被选中。机器可读结果见 `v032_batch_checks.json`。

## 使用示例

```python
from luck_agent.evaluation.batching import iter_batches

for batch in iter_batches(
    "logs/coal_diagnosis/20260922T031250024070Z/split_index_v1.json",
    split="train",
    policies=["heuristic_coal_v029"],
    batch_size=64,
):
    # Python 数值列表，可在未来模型入口转换为张量。
    candidates = batch["candidates"]
    mask = batch["candidates_mask"]
    labels = batch["label"]
```

三种策略混合读取仅用于本轮覆盖验收，不代表将随机策略作为专家标签。数据仍属于开发数据；候选缺少删除、重抽示范的局限仍在。下一步可完善数值缩放与批次打乱契约，并明确 BC 数据选择和评估标准，再开始模型实验。
