# V0.3.3：训练分区缩放与可复现打乱

新增 `luck_agent/evaluation/preprocessing.py` 和 `prepare_preprocessing.py`，扩展批次入口支持显式 scaler、shuffle_seed、epoch 和 shuffle_buffer。默认仍返回原尺度、原顺序。未引入 PyTorch，也未训练模型。

## 数值契约

使用 Welford 在线算法，只遍历明确选择策略的 train 分区，计算 8 个 scalar_fields 的均值和总体标准差。缩放为 (x-mean)/scale；方差不超过 1e-12 时 scale=1，避免除零。无裁剪，不改变奖励。

词表 token、动作类型、实例位置、计时存在标记、掩码、标签和 metadata 不参与拟合。牌组中的永久加成和剩余出场数目前仍保留原尺度；这不是对全部数值字段做统一标准化。后续扩展须保持编码版本与模型输入约定一致。

缩放文件记录字段顺序、编码版本、索引 SHA256、策略集合、fit_split=train 和样本数。使用时核对这些来源信息，拒绝换策略或换索引直接复用。验证/测试使用同一份冻结参数，入口不提供验证/测试拟合选项。数值非有限或 scale 非正会报错。

## 打乱契约

按 seed、epoch 和固定版本字符串初始化独立 Random，不消耗环境 RNG。使用 1024 条样本的缓冲区替换抽样，最后随机排空。它是有限缓冲区打乱，不是全数据均匀随机排列；不改变样本内容或分区。只允许 train 打乱，验证/测试保持原顺序。batch_size=64，保留尾部小批次。

## 实际验收

使用已有数据中的 heuristic_coal_v029；这是开发行为数据，不是新的独立验证种子。

| 分区/轮次 | 样本数 | 批次数 |
|---|---:|---:|
| train / epoch 0 | 11348 | 178 |
| train / epoch 1 | 11348 | 178 |
| validation | 1311 | 21 |
| test | 1607 | 26 |

epoch 0 重复读取顺序完全一致；epoch 1 顺序不同。所有读取逐项比较 (policy, seed, step) 集合与索引，样本恰好一次、无缺失、无重复，所有监督标签仍指向有效候选。297 项测试通过，覆盖在线统计、常数列、训练分区限定、来源不匹配拒绝、输入不变及打乱复现与覆盖。

冻结产物：`logs/preprocessing_v033/scaler.json` 和 `audit.json`。训练样本数 11348。对验证/测试的处理仅为管线验收，没有参数搜索或模型拟合。

```powershell
python run_tests.py
python prepare_preprocessing.py --index logs/coal_diagnosis/20260922T031250024070Z/split_index_v1.json --output logs/preprocessing_v033
```

复现时使用新的输出目录，避免覆盖既有产物。

```python
import json
from pathlib import Path
from luck_agent.evaluation.batching import iter_batches

scaler = json.loads(Path("logs/preprocessing_v033/scaler.json").read_text())
for batch in iter_batches(
    "logs/coal_diagnosis/20260922T031250024070Z/split_index_v1.json",
    split="train", policies=["heuristic_coal_v029"], batch_size=64,
    scaler=scaler, shuffle_seed=42, epoch=0, shuffle_buffer=1024,
):
    pass
```

下一步先冻结 BC 的样本范围、损失掩码与评估标准，区分只有一个合法动作的步骤和真正多选决策，防止大量无需选择的步骤掩盖决策质量。完整游戏的实例规则尚未全部迁移，不能将当前数据视为原版专家数据。
