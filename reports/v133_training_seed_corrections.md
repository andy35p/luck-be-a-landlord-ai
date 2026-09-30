# V133 — 仅训练种子的模型轨迹纠正标签

固定从既有训练种子排序取前4个9000–9003，冻结V130模型与forecast_rents教师。每个状态执行模型动作，将教师建议另存teacher_action；奖励与next_state全部来自真实执行action。标注前后检查环境RNG不变，没有用教师动作伪造转移。

4局分别368/327/212/286条，共1193条，零截断。所有轨迹逐步精确回放通过，教师标签合法，源数据manifest和模型hash前后一致。多候选决策：符号288次/93次分歧，物品37/4，移除221/9。这是固定4个训练种子的覆盖样例，不与事后最差评估案例的分歧率作总体比较。

产物 logs/v133-magpie-corrections，protocol/manifest绑定原数据指纹、模型指纹、教师参数、train种子及action/teacher_action字段约定。没有验证、测试或120xx评估种子，没有训练更新。

下一步需要显式纠正监督适配器：以teacher_action作为分类标签，只输出state候选特征和标签，不把原reward/next_state误配给教师动作。普通CandidateEncoder.encode会拒绝带teacher_action记录，应保留这一防混用检查。正式混合训练前也需要验证纠正分片哈希和源训练种子归属。
