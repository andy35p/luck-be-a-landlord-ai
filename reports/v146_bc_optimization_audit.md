# V146 BC Optimization Audit

## 【当前版本】
V146 BC Optimization Audit

## 【本轮目标】
确定V130训练集符号拟合72.9%的主要原因；本轮训练仅用冻结train，validation仅诊断，test指标封存。

## 【冻结资产】
5026个历史文件在实验末SHA校验不变；V128数据/分区/Teacher、V130模型、环境/规则/奖励、V143–V145均冻结。

## 【V130训练合同】
Dataset manifest SHA256 `19da8692ae3942c8c220561d627241f8662ce2d515ca9ef61aaf92f7fbe222c6`；train32局/val8局，原始训练11755转移，3849多候选决策。8维scalars、4维candidate、20×5 board，训练分区11755样本拟合z-score；模型宽16，参数28785。
PyTorch默认初始化、seed123、Adam(lr=0.001,weight_decay=0)、batch64、无scheduler/early stopping、candidate CE、全局梯度裁剪1；不重复轮换随机顺序200更新，约3.33次多候选样本曝光。最终固定更新checkpoint，不按validation挑选。

## 【Metric Recompute】
冻结V130完整train Symbol Fit **2072/2843=72.88%**；validation **578/762=75.85%**。完整样本train3849/val1111；覆盖32/8分片，源数据hash验证。
Symbol train/val Top2 92.37%/91.21%；mean rank 1.357/1.345；CE 0.6819/0.6401；高置信错75/19。
Decision Type逐项如下（仅多候选）：

| Split | Type | Correct/n | Top1 | Top2 | CE | Mean Teacher Rank | High-confidence Wrong |
|---|---|---:|---:|---:|---:|---:|---:|
| train | item | 299/351 | 85.19% | 100.00% | 0.4019 | 1.148 | 24 |
| train | remove | 648/655 | 98.93% | 100.00% | 0.0426 | 1.011 | 3 |
| train | symbol | 2072/2843 | 72.88% | 92.37% | 0.6819 | 1.357 | 75 |
| validation | item | 70/93 | 75.27% | 100.00% | 0.5456 | 1.247 | 12 |
| validation | remove | 255/256 | 99.61% | 100.00% | 0.0214 | 1.004 | 1 |
| validation | symbol | 578/762 | 75.85% | 91.21% | 0.6401 | 1.345 | 19 |

## 【Tiny-set Overfit】
从原train符号状态按固定SHA顺序嵌套取32/128/512，禁止augmentation；实际最终float32/bool模型输入的异标冲突均0。32在200更新、128在300、512在500更新达到100%且CE≤0.05。由此排除“32个训练状态都学不住”；不能据此证明完整状态表示无信息损失。

## 【Training Curve】
第200更新全部权重与V130 bitwise一致；逐100更新记录train/val loss、fit、rank、梯度、学习率与参数更新幅度。训练曲线见 `logs/v146-bc-audit/budget_scaling/seed123/training_curve.json`。

## 【Budget Scaling】
| Experiment | Params | Updates | Train Symbol Fit | Val Symbol Fit | Teacher Top2 (val) | Runtime s |
|---|---:|---:|---:|---:|---:|---:|
| budget_scaling/seed123 | 28785 | 200 | 72.88% | 75.85% | 91.21% | 3.76 |
| budget_scaling/seed123 | 28785 | 500 | 80.27% | 76.64% | 94.09% | 8.80 |
| budget_scaling/seed123 | 28785 | 1000 | 89.94% | 76.90% | 93.96% | 16.94 |
| budget_scaling/seed123 | 28785 | 2000 | 98.70% | 73.75% | 91.21% | 32.15 |
| interference/seed456-multi | 28785 | 200 | 73.02% | 75.20% | 92.13% | 8.07 |
| interference/seed456-multi | 28785 | 500 | 82.87% | 79.13% | 94.49% | 18.69 |
| interference/seed456-symbol | 28785 | 200 | 74.78% | 74.54% | 92.65% | 3.72 |
| interference/seed456-symbol | 28785 | 500 | 83.71% | 78.48% | 94.23% | 8.68 |
| interference/seed789-multi | 28785 | 200 | 74.25% | 76.51% | 92.52% | 7.96 |
| interference/seed789-multi | 28785 | 500 | 81.43% | 79.27% | 94.23% | 18.75 |
| interference/seed789-symbol | 28785 | 200 | 77.38% | 77.56% | 94.09% | 4.82 |
| interference/seed789-symbol | 28785 | 500 | 85.16% | 78.35% | 93.70% | 10.00 |
| symbol_only/seed123 | 28785 | 200 | 76.19% | 79.13% | 93.57% | 1.78 |
| symbol_only/seed123 | 28785 | 500 | 84.63% | 79.27% | 94.49% | 4.61 |
| symbol_only/seed123 | 28785 | 1000 | 95.32% | 75.72% | 92.65% | 8.49 |
| symbol_only/seed123 | 28785 | 1477 | 98.24% | 75.85% | 92.52% | 12.32 |
| symbol_only/seed123 | 28785 | 2000 | 99.37% | 73.10% | 92.13% | 16.32 |
| tiny_overfit/128 | 28785 | 200 | 99.22% | N/A | N/A | 1.41 |
| tiny_overfit/128 | 28785 | 300 | 100.00% | N/A | N/A | 2.05 |
| tiny_overfit/32 | 28785 | 200 | 100.00% | N/A | N/A | 1.60 |
| tiny_overfit/512 | 28785 | 200 | 94.73% | N/A | N/A | 1.55 |
| tiny_overfit/512 | 28785 | 500 | 100.00% | N/A | N/A | 4.29 |

200→2000更新：train符号72.88→98.70%，validation 75.85→73.75%；val CE在500最低0.5702，2000为0.9939。训练预算不足解释原训练拟合，简单延长预算不改善验证。

## 【Capacity】
预设门槛要求2000更新train符号仍<95%且1000→2000增益<2pp；实测98.70%，故不进行宽度/深度搜索。当前容量不是已证实的训练集瓶颈，不能推论绝无容量问题。

## 【Multi-task Interference】
相同编码器/宽16/seed123的Symbol-only：200/500/1000/2000更新train符号76.19/84.63/95.32/99.37%，val79.13/79.27/75.72/73.10%。按主实验2000更新的symbol曝光匹配1477更新时，train98.24%、val75.85%；主实验2000更新train98.70%、val73.75%。优化序列和非符号上下文不同，不能据此认定多任务干扰；未触发验证显著更优的候选门槛。

补充固定500更新、seed123/456/789的配对诊断：multi-task验证Symbol Fit分别76.64/79.13/79.27%，symbol-only为79.27/78.48/78.35%；symbol-only减multi-task为+2.62/−0.66/−0.92个百分点，平均+0.35个百分点。单种子优势未复现，且训练时符号曝光数不同。

## 【Frequency / Imbalance】
按训练teacher目标出现频次排序后按目标种类三等分；head/medium/tail的train符号fit为81.47%/36.14%/18.56%，样本数2342/404/97；validation为82.56%/44.94%/12.00%，样本数648/89/25。低频确实集中错误，但分桶与决策难度混杂，非因果。candidate频次与teacher选中频次分开保存。

## 【Candidate Size】
全部train2843/val762符号决策的合法action数均为4+；2/3候选桶N/A。恰好4个action的train480例fit70.63%、val120例fit70.83%；5个action的train2363例fit73.34%、val642例fit76.79%，第五项为可用REROLL。候选规模与资源可用性混杂，不能由此推断数目效应。

## 【Teacher Ranking】
train符号错误771个，其中teacher rank2为554、rank≥3为217；rank2且错分margin≤0.5为273。最多的teacher目标错误为SKIP107、goldfish90、bar_of_soap79；模型误选为SKIP204、bar_of_soap160、spirit103。在线V142错误分布不可直接替代训练错误。

## 【Gradient Diagnostics】
主实验2000更新六个模块的全局梯度norm均非零，未见梯度断链；embedding中不变元素来自padding/未出现action token，head两层全部参数改变。逐模块min/max/mean、更新比、参数变化见训练曲线和result.json。scaler仅由train拟合，无zero-variance字段；train scalar最大|z|为coins6.14，val最大|z|为last_spin_income4.00，未发现足以支持改normalization的证据。

## 【实验结果】
完整549项测试通过；训练模型均为实验资产，无生产默认模型替换、无新teacher标签、无test指标。完整checkpoint、配置/seed、dataset/git hash、曲线/运行时/模型指标位于logs/v146-bc-audit。

## 【主要瓶颈归因】

| Error Category | Evidence | Evidence Against | Confidence |
|---|---|---|---|
| TRAINING BUDGET | 200→2000更新train Symbol 72.88→98.70%；tiny32/128/512全拟合 | val Symbol 75.85→73.75%，单纯加更新不能作为发布方案 | 高：解释训练拟合 |
| GENERALIZATION / IMBALANCE | 500以后val CE反弹；head/tail训练fit81.47/18.56%，val82.56/12.00% | 低频难度和频次混杂；仅8局val，无法证明因果 | 中高：泛化限制，中：频次因素 |
| MULTI-TASK INTERFERENCE | seed123的Symbol-only500比multi500 val高2.62pp | 另两seed差−0.66/−0.92pp；同更新曝光不匹配 | 低/未证实 |
| CAPACITY | 当前宽16在2000更新train Symbol98.70%，tiny512全拟合 | 未运行更宽模型；不能排除对泛化或复杂规则的作用 | 低：当前训练拟合非容量瓶颈 |
| OPTIMIZATION / IMPLEMENTATION BUG | 200更新权重bitwise复现；六模块梯度均非零 | 不能排除未测试编码语义问题 | 低：无直接bug证据 |
| REPRESENTATION / DATA NOISE | 真实最终模型tensor训练3849样本均唯一/无异标冲突 | 唯一输入不能排除缺特征或教师目标本身复杂 | 低/未证实 |
| LOSS / RANKING | 训练初始错误554/771为Teacher rank2 | train CE下降且Top1持续升；val分化属泛化；rank2不等于loss有错 | 低：不触发E7 |
| SCALER / REGULARIZATION | train-only zscore11755状态；无零方差；weight_decay0无dropout/scheduler | 只看scalar极值不能证明所有归一化选择最优 | 低：无异常证据 |

## 【是否产生候选模型】
有冻结实验checkpoint，但没有通过固定验证门槛的V146候选模型；V130保持基线，未改生产默认。Symbol-only单种子优势在另外两种子反转；未作在线对局。

## 【在线评估】
未触发明显验证改善/teacher rank改善/高置信错误下降门槛；0在线对局，保持V141合同用于将来的候选。

## 【结论】
证据排序：①原200更新仅约3.33次多候选样本曝光，训练预算不足导致72.9%训练拟合（强）；②继续训练后验证不升且CE显著恶化，泛化/样本分布是模型晋升的主要限制（强描述性，8局验证有限）；③低频Teacher目标错误集中（中，难度混杂）。实现断梯度/输入异标冲突/当前容量不足均缺支持。不能把98.7%训练拟合视为可发布改进。

## 【V147决策】
优先固定验证分区且保持test封存，做训练预算与泛化控制的多种子研究（例如仅训练分区内按episode交叉验证/早停协议先冻结），不盲目扩容量或改ranking loss。先说明频次与分布差异，再以事先锁定的选择规则选一个候选；满足显著验证改善才做32局smoke，之后128局V141合同。Reroll支线继续冻结。

## 十个问题

1. 是。V130原train32局2843个多候选Symbol决策，2072正确=72.8808%；val8局578/762=75.8530%；32/8分片完整覆盖。
2. 能。32/128/512固定train状态分别在200/300/500更新达到100%且CE≤0.05；最终tensor输入异标冲突0。
3. 对训练集拟合而言明显不足：200更新仅3.33次全多候选样本曝光，200→2000训练Symbol提升25.82个百分点；不是验证性能的充分解。
4. 同宽16和超参，500/1000/2000更新train Symbol 80.27%/89.94%/98.70%。
5. 没有同步明显改善：val Symbol 75.85%→76.64%→76.90%→73.75%；val CE在500为0.5702，2000恶化至0.9939。
6. 不是已证实的训练拟合瓶颈：宽16在2000更新train98.70%，512 tiny状态500更新100%；预设容量实验门槛未触发。
7. 未证实。500更新Symbol-only减multi-task val在种子123/456/789为+2.62/−0.66/−0.92个百分点，均值+0.35个百分点；曝光不同。
8. 低频更差：按teacher目标频次分桶train head/medium/tail为81.47/36.14/18.56%，但head也有434个错误；不能归因为单一频次因素。
9. V130 train Symbol teacher平均rank1.357，Top2召回92.37%；771错中554为rank2、217为rank3+。val平均rank1.345、Top2 91.21%。
10. V147优先预算与泛化控制的固定协议、多种子验证；当前不扩容量、不换目标函数、不修未经证实的实现bug，先处理验证退化及低频分布，过离线门槛后再在线smoke。

详细分子分母、每条score/rank/margin、分片覆盖、频次、收敛曲线与梯度见伴随JSON及logs/v146-bc-audit；上述统计均为当前受限仿真环境的离线诊断。
