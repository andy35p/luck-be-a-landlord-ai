# V123 — 喜鹊模型接口与重载

复用既有空间候选模型结构，只将编码器选择变为类属性；旧模型默认仍为金鱼编码。新增独立 MagpieCandidateModel 与专用张量/保存读取入口，模型版本 magpie-spatial-mlp-v1，检查喜鹊规则身份、词表和编码版本。保存文件明确标记 untrained_interface_probe / raw_scalars_probe_only。

3个工程分区的1186条样例全部前向成功：合法候选分数有限，13802个补齐候选槽位保持负无穷，argmax始终选择合法位置。保存/重载后所有分数逐元素完全一致。旧张量入口拒绝新编码，旧checkpoint读取器拒绝新原型。4项已有空间模型/喜鹊编码相关测试通过。

原型位于 outputs/v123-magpie-prototype/untrained.pt；检查结果 reports/v123_magpie_model_probe.json。使用固定初始化种子123，优化器更新0次。原始标量尚未归一化，当前仅证明维度、mask、词表隔离和重载兼容，不是训练效果或可部署模型。可选NumPy缺失警告仍存在，当前测试未依赖NumPy转换且全部成功。

下一步需要训练分区独立拟合的归一化合同，并将词表/规则/教师/训练数据指纹绑定到正式checkpoint；不能把这个接口原型当作已有BC模型升级。实机策略未更换。
