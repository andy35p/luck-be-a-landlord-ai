# V121 — 新教师轨迹与编码合同

检查发现旧 CandidateEncoder 固定煤域、SpatialCandidateEncoder 固定金鱼域，词表不能直接复用喜鹊数据。新增独立 MagpieCandidateEncoder，版本 magpie-spatial-candidates-v1，复用已有候选动作、计时器、20格上次棋盘编码逻辑；旧编码器、checkpoint 和默认训练入口不变。新旧 features/batch 版本互相拒绝，针对版本和喜鹊剩余周期测试通过。

使用跨租金教师生成3个完整工程样例，规则身份 instance-magpie-v1 revision 1，记录8次预测、30转、预测种子及排序规则。按固定 salt magpie-forecast-teacher-v1 在生成前选择7000起各分区首个种子：train=7000、test=7004、validation=7018。轨迹分别409、409、368条，共1186条，无截断；全部精确环境回放并通过候选/空间编码和分批拼接。

输出 logs/v121-magpie-smoke，包括原始压缩轨迹、协议、词表、各文件哈希和源码指纹。只有三份轨迹全验证后才写 manifest，状态明确为 replayed_and_encoded_smoke_only。当前这是数据链路样例，不是可用于评价模型泛化的数据规模，也不是最终封存测试集。没有训练、没有混入旧 BC 数据。

限制：尚无新域的正式训练数据读取验收器；当前 collector 内检查头部、轨迹和词表，不应跳过后续 manifest 验证直接接训练。下一步应补读取端的文件哈希、规则/教师合同和分区检查，再考虑受控扩量。
