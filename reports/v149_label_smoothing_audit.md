# V149 Label Smoothing Regularization Audit

## 【当前版本】

V149 Label Smoothing Audit。

## 【本轮目标】

在固定 500 updates 的 V147 强基线上，只改变 label smoothing ε，判断它能否减少错误过度自信，同时稳定改善开发验证集的符号决策泛化。

## 【冻结资产】

- V128 train 9000–9031 与 development validation 10000–10007；test 11000–11007 继续封存。
- 宽度 16、28,785 参数、Adam、LR 0.001、batch 64、clip 1、无 weight decay/dropout/scheduler。
- V128 encoder、teacher、全 train scaler、V146 frequency mapping 与 0.8 高置信错误阈值。
- 历史文件核对 5313 项，变化 0；实验进程未打开 test 分片或 V128 manifest。

## 【预注册合同】

- ε = 0.00 / 0.02 / 0.05 / 0.10，5 个相同种子，共 20 个固定 500-update 运行。
- 正 ε 的平滑质量只分配给当前合法候选；padding 不参与。ε=0 直接调用原 CE。
- 所有横向验证统一使用普通 hard-label CE。
- 晋升要求同时满足：平均 Top1 严格提高、至少 4/5 种子不低、平均 Rank 不差、hard CE 恶化不超过 0.005、平均高置信错误严格下降。多个通过时选最小 ε。
- Online 候选种子预注册为验证 Top1 中位种子；只有离线门槛通过才使用 17000–17031。

## 【测试结果】

V149 定向回归 7/7 通过；完整测试 **568/568 通过，0 失败**。沙箱内首次执行有 5 项 Windows 多进程测试因管道权限报 WinError 5；同一测试集在允许创建进程管道的环境中全部通过。

## 【ε=0 Regression】

5/5 种子的 ε=0 最终权重均与 V147 Fixed500 历史 checkpoint **bitwise 一致**；scaler、Validation Symbol Top1 与 hard CE 也逐值一致。正 ε 训练只在该门槛通过后启动。

## 【Multi-Seed Results】

| ε | Train Symbol | Val Symbol | Standard Val CE | Val Top2 | Mean Rank | HC Wrong | Wrong Conf. |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 81.30% ± 1.13pp | 77.69% ± 1.39pp | 0.5779 ± 0.0111 | 93.94% | 1.2979 ± 0.0152 | 32.6 ± 6.9 | 0.6414 |
| 0.02 | 81.89% ± 1.10pp | 77.43% ± 1.46pp | 0.5838 ± 0.0155 | 93.81% | 1.3029 ± 0.0153 | 27.6 ± 4.0 | 0.6192 |
| 0.05 | 82.38% ± 1.35pp | 77.87% ± 1.83pp | 0.5923 ± 0.0178 | 93.65% | 1.3010 ± 0.0197 | 22.0 ± 4.3 | 0.5988 |
| 0.10 | 82.64% ± 1.14pp | 78.11% ± 1.36pp | 0.6172 ± 0.0149 | 93.78% | 1.2990 ± 0.0131 | 14.2 ± 4.0 | 0.5681 |

## 【Paired Comparison】

| ε vs 0 | Mean ΔVal Top1 | 95% bootstrap CI | Better | Equal | Worse |
|---:|---:|---:|---:|---:|---:|
| 0.02 | -0.262pp | [-1.129pp, +0.604pp] | 2 | 0 | 3 |
| 0.05 | +0.184pp | [-0.709pp, +1.444pp] | 2 | 0 | 3 |
| 0.10 | +0.420pp | [-0.236pp, +1.207pp] | 3 | 0 | 2 |

三个区间都跨 0。ε=0.10 的平均增益最大（+0.420pp），但仅 3/5 种子改善，仍小于种子波动，不能称为稳定提升。

## 【Generalization Gap】

| ε | Train−Val gap | 相对 ε=0 |
|---:|---:|---:|
| 0.00 | 3.611pp | +0.000pp |
| 0.02 | 4.465pp | +0.853pp |
| 0.05 | 4.511pp | +0.900pp |
| 0.10 | 4.528pp | +0.917pp |

Gap 没有压缩；正 ε 的 train fit 反而略高，validation 的变化较小。这里没有“牺牲训练准确率换验证泛化”的证据。

## 【Confidence Calibration】

| ε | HC Wrong | Wrong Confidence | ECE-10 | Brier |
|---:|---:|---:|---:|---:|
| 0.00 | 32.6 | 0.6414 | 0.0257 | 0.3183 |
| 0.02 | 27.6 | 0.6192 | 0.0344 | 0.3185 |
| 0.05 | 22.0 | 0.5988 | 0.0482 | 0.3186 |
| 0.10 | 14.2 | 0.5681 | 0.0828 | 0.3253 |

错误置信度与高置信错误随 ε 单调下降；但正确预测置信度也下降，ECE 从 0.0257 增至 0.0828，表现为整体偏保守，而非校准全面改善。ε=0.10 的 wrong-confidence P95 从约 0.919 降至 0.841；正确预测 P95 也从约 0.989 降至 0.947。

## 【Teacher Rank】

| ε | Mean Rank | Δ vs 0 |
|---:|---:|---:|
| 0.00 | 1.297900 | +0.000000 |
| 0.02 | 1.302887 | +0.004987 |
| 0.05 | 1.301050 | +0.003150 |
| 0.10 | 1.298950 | +0.001050 |

所有正 ε 的平均教师排名都比基线略差。ε=0.10 退化最小，但仍未满足“不恶化”门槛。

## 【Head / Medium / Tail】

| ε | Val Head (n=648) | Val Medium (n=89) | Val Tail (n=25) |
|---:|---:|---:|---:|
| 0.00 | 82.72% | 56.18% | 24.00% |
| 0.02 | 82.47% | 56.85% | 20.00% |
| 0.05 | 82.65% | 58.65% | 22.40% |
| 0.10 | 82.93% | 58.43% | 23.20% |

Medium 在 ε=0.05/0.10 上升约 2.47/2.25pp，但 Tail 低于基线，Head 基本持平。Tail 每种子仅 25 条，以上只作探索性观察；不符合 Frequency-Generalization 分支。

## 【Confusion Audit】

| ε | bar_of_soap→SKIP | goldfish→bar_of_soap |
|---:|---:|---:|
| 0.00 | 18.2 ± 6.1 | 9.0 ± 0.0 |
| 0.02 | 19.8 ± 5.4 | 9.0 ± 0.0 |
| 0.05 | 19.0 ± 6.3 | 8.8 ± 0.4 |
| 0.10 | 17.0 ± 4.6 | 8.8 ± 0.4 |

这些主要混淆没有被一致消除；改善集中在部分 seed，不能单独支持晋升。完整 Top-10 见 `logs/v149-label-smoothing/confusions.json`。

## 【Candidate Gate】

| ε | Top1↑ | ≥4/5 non-lower | Rank不差 | CE≤+0.005 | HC Wrong↓ | Pass |
|---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 0.02 | ✗ | ✗ | ✗ | ✗ | ✓ | **FAIL** |
| 0.05 | ✓ | ✗ | ✗ | ✗ | ✓ | **FAIL** |
| 0.10 | ✓ | ✗ | ✗ | ✗ | ✓ | **FAIL** |

没有 ε 通过全部门槛；不选择 canonical seed，不晋升 checkpoint。

## 【32局 Online Smoke】

**NOT TRIGGERED**。离线门槛失败，预注册在线种子 17000–17031 未消耗。

## 【结论】

Label smoothing 能稳定压低错误置信度，但没有稳定提高 unseen development states 上的决策泛化。ε=0.05/0.10 的平均 Top1 略升，paired CI 仍跨 0，方向只有 2/5 与 3/5；三个正 ε 的教师排名和统一 hard CE 都退化。结果更接近“把分数整体压平”，不满足生产候选条件。

十个问题：

1. **没有**稳定提高 Validation Symbol Top1。
2. **没有有效的最小 ε**；三个候选均失败。
3. **是**，平均 HC Wrong 从 32.6 降至 27.6 / 22.0 / 14.2。
4. **是**，错误置信度从 0.6414 降至 0.6192 / 0.5988 / 0.5681。
5. **是**，所有正 ε 的 Mean Teacher Rank 均轻微恶化。
6. Medium 有探索性改善，Tail 没有改善，不能称为中长尾整体泛化提升。
7. **不是**；Train Accuracy 没下降，反而略升，gap 也扩大。
8. **没有**；所有 paired bootstrap 95% CI 跨 0。
9. **没有**触发 32 局 Online Smoke。
10. V150 应进入 **Weight Decay Audit**。

## 【V150决策】

进入单变量 **Weight Decay Audit**，继续固定 500 updates、同一 5 seeds 和 hard-label 验证指标。不要细调 ε，也不要组合 label smoothing + weight decay；Label Smoothing 支线到此停止。

原始资产：`logs/v149-label-smoothing/`；机器报告：`reports/v149_label_smoothing_audit.json`。开发验证集从 V146 起已被多次观察，不是未触碰 holdout；test 继续 SEALED。
