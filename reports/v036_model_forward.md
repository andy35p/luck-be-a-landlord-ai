# V0.3.6：最小候选评分模型前向验收

在独立 `.venv-model` 环境安装 PyTorch 2.14.0+cpu，来源为官方 CPU wheel 索引；版本固定在 requirements-model.txt。原标准库运行环境不变。安装路径参考 https://docs.pytorch.org/get-started/locally/ 。

新增 candidate_model.py：符号、物品和动作类型使用 16 维嵌入；实例表示同时输入永久加成、计时和计时存在标记。牌组/物品按掩码求均值，拼接经济状态作为公共上下文。每个候选拼接类型、符号、物品、所指实例特征，通过共享 64 隐单元网络输出一个分数，共 7489 参数。没有固定全局动作输出层。

填充实例不参与池化，填充候选输出负无穷；删除目标指针读取具体实例。TorchScorer 将单步特征转为单样本张量，复用 CandidateAgent。模型本轮固定在 CPU；没有实现设备迁移、检查点或训练入口。

masked_bc_loss 只对多合法候选行计算 cross entropy，非法标签/非有限合法分数报错，全唯一动作批次返回 None。填充位置与唯一动作行的梯度为零。参考测试执行反向传播检查梯度，但没有优化器更新。

## 验收结果

- 模型环境 308 项测试全部通过；标准库环境 306 项通过、2 项可选模型测试跳过。
- 实际候选训练分区 11348 条样本、178 批全部前向运行。
- 与标准库参考 masked NLL 的最大绝对差为 5.132708627009208e-7，小于阈值 1e-5。
- 检查候选排列等变、单样本与带填充批次输出一致、填充屏蔽与损失梯度边界。
- 固定初始化种子 36，未训练模型通过实时接口运行开发种子 0–9 共 10 局、380 次决策，0 截断；推理不改变环境 RNG。
- 审计前后全部权重逐项相同，optimizer_steps=0。不能将这些结果解释为模型已经学会游戏。

详细结果：v036_model_audit.json。环境未安装 NumPy，PyTorch 导入时会提示可选 NumPy 桥接不可用；本实现仅使用 Python 列表与张量，实际测试和审计均通过。

```powershell
.\.venv-model\Scripts\python.exe run_tests.py
.\.venv-model\Scripts\python.exe audit_candidate_model.py
```

首次设置可用 `python -m venv .venv-model`，再用其 Python 执行 `-m pip install -r requirements-model.txt`。审计文件使用独占创建，复现需更换脚本中的输出路径。

下一步可实施固定预算的小规模 BC 冒烟训练，记录初始化、数据来源、参数、损失和逐阶段准确率，并与未训练模型及教师闭环比较。现有分区仍属开发数据，完整原版规则尚未迁移；尚不能声称独立泛化效果。
