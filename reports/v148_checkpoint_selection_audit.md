# V148 Checkpoint Selection & Early-Stopping Contract Audit

## 【当前版本】
V148 Checkpoint Selection Audit

## 【本轮目标】
只用V128原train episodes内部的FIT/SELECTION信息选择checkpoint，再锁定选择，最后用V128 development validation审计泛化；test继续封存。

## 【冻结资产】
历史文件校验5209项，0变化；V128原split/Teacher、V130与V143–V147资产未覆盖。

## 【Leakage Guard】
V148专用读取器不调用会遍历全corpus的旧API；训练阶段只打开train shards。Scaler只由FIT episodes的全部转移拟合，SELECTION/validation均排除；固定游戏规则词表不从样本学习。选择锁SHA为 `bf32ae0b09f54aca7db2d1590811e039b00fea57506b4a5afa8b0744a558b253`，锁前validation未打开。V148实验进程未打开test shard，也未读取包含test outcome的V128 manifest。

## 【Selection Split】
主拆分：24 FIT episodes、8 SELECTION episodes，episode完全隔离；FIT/SELECTION多候选决策2782/1067，其中Symbol 2150/693。另预注册两组24/8拆分，各3个训练seed。三个split hash及episode IDs见split_manifest.json。

## 【预注册合同】
宽16/28,785参数、Adam0.001、batch64、CE、clip1；每条FIT轨迹训练1000更新，保存200/300/400/500/600/750/1000。Primary为state-weighted SELECTION Symbol CE最低，完全相同取更早；Top1选择只作次级诊断。固定比较200/300/500。

## 【测试结果】
完整561项测试通过；新增检查覆盖episode隔离/确定性/hash、FIT-only scaler、validation锁、tie-break、test不加载及历史资产。

## 【Coverage Audit】
主拆分SELECTION与development validation：Symbol决策693/762；head/medium/tail为582/86/25与648/89/25。标签频次/候选频次/rent-stage TV为0.060/0.030/0.048。deck-size/candidate-count TV为0.184/0.096；平均deck 24.22 vs 23.85，存在episode组成偏移但无极端标签偏移。

## 【Checkpoint Choices】

| Seed | CE-selected update | Top1-selected update | Fixed300 Val | Fixed500 Val | CE-selected Val | Selection CE |
|---:|---:|---:|---:|---:|---:|---:|
| 123 | 400 | 400 | 77.17% | 78.61% | 79.13% | 0.5886 |
| 456 | 400 | 750 | 78.22% | 76.38% | 74.41% | 0.5911 |
| 789 | 400 | 300 | 77.03% | 77.43% | 77.43% | 0.5673 |
| 24680 | 300 | 300 | 76.64% | 76.25% | 76.64% | 0.5906 |
| 13579 | 400 | 400 | 72.18% | 76.12% | 75.85% | 0.6075 |

主拆分selected update mean/median/SD/min/max = 380.0/400/44.7/300/400；CE与Top1选择3/5完全相同。三拆分11次选择全部300–500。

## 【CE-selected vs Fixed300/500】

| Policy | Mean Val Top1 | Std | Val CE | Mean Rank | High-conf Wrong | Wrong Confidence | Generalization Gap |
|---|---:|---:|---:|---:|---:|---:|---:|
| ce_selected | 76.69% | 1.76pp | 0.5841 | 1.3024 | 31.0 | 0.629 | +3.96pp |
| fixed300 | 76.25% | 2.35pp | 0.5906 | 1.3094 | 23.2 | 0.601 | +1.76pp |
| fixed500 | 76.96% | 1.06pp | 0.5991 | 1.2982 | 42.6 | 0.658 | +7.78pp |

CE-selected−Fixed300 Top1逐seed：+1.969pp, -3.806pp, +0.394pp, +0.000pp, +3.675pp，平均+0.446pp。CE-selected−Fixed500：+0.525pp, -1.969pp, +0.000pp, +0.394pp, -0.262pp，平均-0.262pp，bootstrap95%CI[-1.129pp, +0.367pp]，better/equal/worse=2/1/2。预注册综合门槛：FAILED。

## 【Selection Regret】
Regret=hindsight最佳预注册validation Top1−对应policy Top1；oracle仅诊断，不用于选择。

| Seed | CE-selected Regret | Fixed300 Regret | Fixed500 Regret | Oracle update |
|---:|---:|---:|---:|---:|
| 123 | 0.00pp | 1.97pp | 0.52pp | 400 |
| 456 | 3.81pp | 0.00pp | 1.84pp | 300 |
| 789 | 0.00pp | 0.39pp | 0.00pp | 400 |
| 24680 | 0.13pp | 0.13pp | 0.52pp | 400 |
| 13579 | 0.39pp | 4.07pp | 0.13pp | 750 |

平均regret：CE-selected 0.866pp，Fixed300 1.312pp，Fixed500 0.604pp；CE选择未降低相对Fixed500的regret。

## 【Teacher Rank】
CE-selected Mean Rank 1.3024，Fixed300 1.3094，Fixed500 1.2982；相对Fixed500恶化+0.0042。Rank2/Rank≥3逐seed明细保存在audit_metrics.csv。

## 【Confidence Errors】
CE-selected高置信错误均值31.0，Fixed500为42.6，减少11.6；错误平均置信度0.629 vs 0.658。这是soft improvement，但不能覆盖Primary Top1/rank门槛失败。

## 【Head / Medium / Tail】
Validation每seed n=648/89/25；tail仅探索性。

| Policy | Head | Medium | Tail |
|---|---:|---:|---:|
| ce_selected | 81.76% | 55.96% | 19.20% |
| fixed300 | 82.04% | 50.11% | 19.20% |
| fixed500 | 81.27% | 60.22% | 24.80% |

## 【Split Limitations】
主拆分只有8个selection episodes；虽然另做两拆分×3seed，split variance仍有限；V128 validation在V146/V147已反复观察，只是本轮选择独立的开发审计，不是新holdout；Validation tail仅25个状态，bucket结果探索性；FIT从32局减为24局，绝对性能不能与V147 full-train直接做唯一因果比较；test shard与嵌入test outcome的V128 manifest在V148实验进程均未打开。两组次级拆分共6次：CE-selected相对Fixed500的Top1平均+0.066pp、CE平均−0.0120；与主拆分Top1−0.262pp不完全一致，说明外部Top1收益仍受split/seed噪声影响。

## 【Online Smoke】
NOT APPLICABLE。V148模型仅用FIT subset训练，是选择合同诊断模型；未refit完整train、未运行在线游戏。

## 【结论】
CE选择器的更新位置很稳定，但没有胜过固定500：主拆分Top1平均低0.262pp，2胜1平2负，外部开发验证regret也高于固定500。它使CE降低0.0149、高置信错误减少11.6个、错误置信度下降，属于soft generalization/calibration信号；Mean Teacher Rank却恶化0.0042，预注册总门槛失败。

## 【V149决策】
不生产化Early Stopping。把固定500作为简单诊断基线，V149进入单变量Regularization Audit，优先针对高置信错误和中长尾泛化；继续封存test，预注册后再决定是否full-train refit或online smoke。

## 十个问题

1. 能。主拆分选择400/400/400/300/400，5/5落在300–600；三拆分11次选择为300一次、400九次、500一次。
2. 主拆分mean380、median400、sample SD44.7、范围300–400；未出现750/1000失控。
3. 没有更好，且仅在预注册0.5pp容忍下达到4/5“不明显差”：CE-selected平均76.69%，固定500为76.96%，差−0.262pp，2胜1平2负。
4. 降低。平均Validation CE从固定500的0.5991降至0.5841，差−0.0149；三拆分次级6次比较平均差−0.0120。
5. 未改善。Mean Rank为1.3024，固定500为1.2982，差+0.0042。
6. 减少。高置信错误31.0对42.6，平均少11.6；错误平均置信度0.629对0.658。
7. 主拆分5个seed中3个选择update完全一致；另外两个相差100和350 updates，说明Top1选择更跳跃。Top1规则仅作诊断。
8. 标签频次、候选频次、stage差异小；Selection相对开发validation的TV分别0.060/0.030/0.048。deck size与全决策candidate-count TV为0.184/0.096，存在中等episode组成偏移。
9. 不足。更新位置稳定、CE/置信错误改善，但Primary Top1、rank与regret未超过简单固定500，预注册门槛失败。
10. Regularization Audit；固定500作为比较基线，不进行Full-Train Refit或Early-Stopping生产化。

完整拆分、锁文件、训练曲线、选择/审计CSV、coverage与原始指标位于logs/v148-checkpoint-selection。
