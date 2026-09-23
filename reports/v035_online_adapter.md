# V0.3.5：在线候选评分闭环

新增 `luck_agent/agents/candidate_agent.py`，复用离线 CandidateEncoder 的特征路径。没有模型训练，不改变环境或现有基线。

## 接口

CandidateEncoder 新增 encode_observation(state, actions)，不需要教师动作或未来状态。离线 encode 在该公共路径之上附加标签、奖励和轨迹元数据。在线和离线特征逐项一致测试通过。

CandidateAgent 接收 scorer(features)，评分器只得到 scalars、deck、items、candidates 和 candidate_mask；不传 seed、step、教师标签、奖励和原始 metadata。单次实时推理没有填充，mask 全为 true；未来批量模型需沿用已有批次填充掩码。

评分器必须返回每个候选一个有限分数，数量错误或 NaN/Inf 直接拒绝。按候选分数 argmax 选择后，返回调用方传入的原始 Action，不从 token 猜测目标。重复候选、结束状态和空候选被拒绝。唯一动作先完成编码检查，随后直接返回，不调用评分器。

可选冻结缩放参数，在构造时校验索引、教师来源与编码版本。只支持显式声明的 instance-coal-v1；由调用方提供当前环境的合法候选，适配器不会重新计算游戏合法性，GameEnv.step 仍进行最终验证。

## 验收

306 项测试通过：唯一动作绕过评分器、评分器字段边界、同类副本精确删除、在线/离线特征一致、非法评分拒绝，以及完整游戏对照。新增 `audit_candidate_agent.py` 使用 first_candidate_scores 确定性测试器，接入 V0.3.3 冻结缩放，运行开发种子 0–99：

- 100 局、10041 次决策，0 截断。
- 每一步状态、奖励、终止标志和 info 均与直接执行第一个合法动作的对照环境一致。
- 每次推理前后的环境 RNG 状态一致。
- 逐局摘要保存在 `v035_online_audit.json`。

这是接线验收：测试器故意选择首候选，不是已验证教师，更不是学习模型。因此不把其通关表现作为算法结论，也不据此声称模型能玩游戏。

```powershell
python run_tests.py
python audit_candidate_agent.py
```

审计文件使用独占创建，复现时需为脚本指定不同输出路径或另存脚本输出，不覆盖已有结果。

下一步可以在既定受限范围内接入最小候选评分模型，先做无训练前向传播与参考 masked NLL 对照，再进行小规模 BC。需持续保留数据覆盖不足、开发集已消费和完整规则未迁移的边界。
