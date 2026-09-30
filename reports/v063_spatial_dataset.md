# V0.6.3：首份金鱼环境开发语料

已按预先固定的种子 0–199，采集 Random 与默认 Heuristic 各 200 局，共 400 局、60889 步。所有胜负结果均保留，没有按结果挑选。零截断，全部逐步精确重放。

## 数据划分

使用既有按种子散列规则，同一环境种子的两种策略轨迹始终分到同一区间，避免同种子跨训练和验证。

| 分区 | 每种策略的局数 | Random 步数 | Heuristic 步数 |
|---|---:|---:|---:|
| train | 159 | 16170 | 32009 |
| validation | 19 | 1796 | 3408 |
| test | 22 | 2264 | 5242 |
| 总计 | 200 | 20230 | 40659 |

种子已用于开发，test 名称只是数据管线内部划分，不是未曝光的最终测试集。不得用这里的分区结果宣称新种子泛化。Random 数据用于覆盖与离线分析；后续 BC 如使用默认启发式教师，应明确只选择 heuristic，不能把随机执行动作自动当作优质教师标签。

## 校验与读取

采用 goldfish-spatial-candidates-v1 编码。每条样本检查动作、实例与棋盘身份，并进行 64 条批处理验证。正式读取接口 iter_corpus 要求显式分区和策略，核对清单状态、规则修订、词表、协议、索引与轨迹哈希；校验完整种子覆盖和逐局长度。被修改文件、未知策略及错误分区会被拒绝。

仅在所有策略完成重放与编码校验后写出 validated manifest。缺少 manifest 的中断采集目录不能作为完成数据集读取。本轮仍保存完整公开转移，包括 reward 和 next_state；模型 features 接口负责排除未来信息和元数据。

377 项测试通过，正式读取接口还对全部三个分区回读，核对条数及两种策略的种子集合一致。审计为 v063_dataset_audit.json，包含清单哈希及当前有效目录哈希；测试输出为 v063_tests.txt。

## 位置与下一步

数据目录：logs/spatial-dataset-v063。含 protocol.json、vocabulary.json、index.json、manifest.json、两份压缩轨迹及逐局结果。采集协议为 configs/v063_spatial_dataset.json；采集脚本为 collect_spatial_dataset.py；校验读取器为 luck_agent/evaluation/spatial_dataset.py。

示例：

```python
from luck_agent.evaluation.spatial_dataset import iter_corpus
samples = iter_corpus('logs/spatial-dataset-v063', split='train', policies=['heuristic'])
```

本轮未训练模型，也没有替换默认策略。下一步可以仅用 heuristic/train 拟合归一化统计并冻结，然后建立匹配新编码版本的模型输入适配；旧煤炭模型不能直接加载新词表。
