# V0.6.4：仅训练分区的空间输入归一化

核对 V0.6.3 语料已完成并具有 validated 清单后，仅使用 heuristic/train 的 32009 条公开状态拟合统计。Random、validation、test 均不参与均值与尺度计算。本轮没有训练模型或改变默认代理。

## 契约

使用逐样本 Welford 统计、总体方差，零方差尺度设为 1。拟合样本包括单动作状态，与之前的归一化口径一致；不是仅按多选决策拟合。仅变换 coins、current_rent、spins_until_rent、rent_stage、reroll_tokens、removal_tokens、last_spin_income、spin_count 八个标量。

符号与物品 token、动作类型、牌组指针、棋盘、剩余寿命、奖励和标签不变。转换不原地修改样本或统计。归一化文件绑定编码版本、字段顺序、教师策略和源 manifest 哈希，错配拒绝。

iter_spatial_batches 将清单校验、冻结统计和空间批处理连接起来。显式选择分区与策略，仅训练分区允许随机打乱；不丢弃最后不足一个批次的样本。旧煤炭归一化接口不变。

## 实测回读

| 分区 | 样本数 | 批次数（64 条） |
|---|---:|---:|
| train | 32009 | 501 |
| validation | 3408 | 54 |
| test | 5242 | 82 |

训练标量均值与 0、二阶矩与 1 的误差均小于 1e-10；验证与测试只应用同一份统计，不重新居中或拟合。全部标签仍指向有效候选。回读三个分区后，统计文件字节保持不变。

380 项测试通过，覆盖训练专用读取、零方差、非有限值、文件来源变化、错误策略、验证分区禁止打乱及分类数据不受变换影响。

统计文件：logs/spatial-preprocessing-v064/scaler.json；SHA256 为 59f8525b222c1fb8334e71d61cedec4287be4dd0ad580f774057fbfcabe79cd0。审计：v064_scaler_audit.json；测试输出：v064_tests.txt。

下一步是与 goldfish-spatial-candidates-v1 匹配的模型和在线候选评分适配，先验证前向计算、掩码和保存重载，再考虑训练。当前 test 仍是已曝光开发种子的内部划分，不是最终未见评估。
