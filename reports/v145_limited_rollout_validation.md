## 【当前版本】

V145 Limited Rollout Long-Horizon Validation

## 【本轮目标】

Training Updates=0；验证有限续局是否值得继续投入，不改在线Teacher或局部公式。

## 【冻结资产】

1937历史文件hash未变；V128/V130/Legacy/V143/V141–V144全冻结。

## 【新增工具】

tools/validate_long_horizon.py：独立clone/RNG、单租金pilot、checkpoint续跑、嵌套K收敛、1/2/3租金与终局比较；仅显式命令运行，无在线调用。

## 【测试结果】

完整543项通过，0 Failed；12项V145新增检查覆盖clone/RNG/seed复现、租金/终局/奖励口径、无重放续跑、聚合/CI/sign、缓存冷热轨迹一致、跨进程复现及历史hash。详见logs/v145-rollout/tests.txt。

## 【State Sampling】

全部1369机会中预冻结40状态：六个主要租金优势分桶各6个、概率/现金稀有分量各2个；包含选择与拒绝，优先不同episode，不按续局结果选状态。pilot12状态先只走1租金，4状态K8/16/32/64收敛，formalK32复用pilot/full cache。

## 【Continuation Convergence】

{
  "K32_vs64_end_sign_agreement": {
    "stage_gain": 0.75,
    "reward_gain": 0.75
  },
  "formal_K": 32,
  "stable_point_sign_gate": true,
  "interpretation": "Point sign stability only; finite nested pilot, no ground truth. FormalK stays frozen32, uncertainty reported."
}

逐状态meanQ/std/SE/CIwidth/sign见convergence.csv。K32预算固定，稳定性不成立时不自动上最大K来追显著。

## 【Local vs Long-Term】

| Horizon | Target | n | Pearson | Spearman | Sign agree | Nonzero agree |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | stage_gain | 36 | N/A | N/A | 0 | N/A |
| 1 | reward_gain | 36 | 0.055 | 0.062 | 0.583 | 0.583 |
| 2 | stage_gain | 36 | N/A | N/A | 0 | N/A |
| 2 | reward_gain | 36 | 0.114 | 0.120 | 0.611 | 0.611 |
| 3 | stage_gain | 36 | 0.006 | -0.050 | 0.028 | 0.333 |
| 3 | reward_gain | 36 | 0.038 | 0.013 | 0.500 | 0.500 |
| end | stage_gain | 36 | -0.178 | -0.058 | 0.472 | 0.531 |
| end | reward_gain | 36 | -0.174 | -0.202 | 0.333 | 0.333 |

上表为active rent轴36状态；概率/现金稀有分量各n2，相关N/A，详细记录在JSON。按axis分开，不混概率/租金/现金，不报告跨单位MAE。Pearson/Spearman与符号关系均为描述性。

## 【Horizon Comparison】

| H vs End | Target | n | Pearson | Spearman | Sign agree | Nonzero agree |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | stage_gain | 40 | N/A | N/A | 0.200 | 0 |
| 1 | reward_gain | 40 | 0.152 | 0.079 | 0.525 | 0.525 |
| 2 | stage_gain | 40 | N/A | N/A | 0.200 | 0 |
| 2 | reward_gain | 40 | 0.194 | 0.211 | 0.600 | 0.600 |
| 3 | stage_gain | 40 | 0.116 | 0.192 | 0.275 | 0.094 |
| 3 | reward_gain | 40 | 0.225 | 0.225 | 0.600 | 0.600 |

三个短horizon与end使用同一条轨迹checkpoint，不能当独立验证；terminal早于目标时吸收终局值。终局是固定V143续局代理，不是ground truth。

## 【Independent Continuation Replication】

| Fold | Target | Predictor | n | Pearson | Spearman | Sign agree |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | stage_gain | local_active_rent_axis | 36 | -0.195 | -0.098 | 0.444 |
| 0 | stage_gain | 1 | 36 | N/A | N/A | 0.167 |
| 0 | stage_gain | 2 | 36 | N/A | N/A | 0.167 |
| 0 | stage_gain | 3 | 36 | 0.016 | -0.014 | 0.222 |
| 0 | stage_gain | end | 36 | -0.103 | -0.026 | 0.472 |
| 0 | reward_gain | local_active_rent_axis | 36 | -0.249 | -0.214 | 0.278 |
| 0 | reward_gain | 1 | 36 | 0.236 | 0.155 | 0.500 |
| 0 | reward_gain | 2 | 36 | 0.259 | 0.127 | 0.500 |
| 0 | reward_gain | 3 | 36 | 0.144 | 0.072 | 0.444 |
| 0 | reward_gain | end | 36 | 0.239 | 0.225 | 0.611 |
| 1 | stage_gain | local_active_rent_axis | 36 | -0.035 | -0.093 | 0.444 |
| 1 | stage_gain | 1 | 36 | N/A | N/A | 0.139 |
| 1 | stage_gain | 2 | 36 | N/A | N/A | 0.139 |
| 1 | stage_gain | 3 | 36 | 0.014 | 0.022 | 0.194 |
| 1 | stage_gain | end | 36 | -0.103 | -0.026 | 0.472 |
| 1 | reward_gain | local_active_rent_axis | 36 | -0.061 | -0.043 | 0.444 |
| 1 | reward_gain | 1 | 36 | 0.061 | 0.003 | 0.472 |
| 1 | reward_gain | 2 | 36 | 0.023 | 0.008 | 0.417 |
| 1 | reward_gain | 3 | 36 | -0.032 | -0.078 | 0.417 |
| 1 | reward_gain | end | 36 | 0.239 | 0.225 | 0.611 |

补充预先冻结的分半分析：0–15预测、16–31终局参考，再交换；同路径相关不是验证。只用active rent轴36状态，不混局部评分单位。分半各16条/branch的终局也含噪声，不是真值。

## 【Sign Confusion】

{
  "1:stage_gain": {
    "ZERO LONG-TERM PROXY": 40
  },
  "1:reward_gain": {
    "FALSE NEGATIVE PROXY": 10,
    "TRUE POSITIVE PROXY": 12,
    "TRUE NEGATIVE PROXY": 11,
    "FALSE POSITIVE PROXY": 7
  },
  "2:stage_gain": {
    "ZERO LONG-TERM PROXY": 40
  },
  "2:reward_gain": {
    "FALSE NEGATIVE PROXY": 10,
    "TRUE POSITIVE PROXY": 13,
    "TRUE NEGATIVE PROXY": 11,
    "FALSE POSITIVE PROXY": 6
  },
  "3:stage_gain": {
    "ZERO LONG-TERM PROXY": 37,
    "TRUE NEGATIVE PROXY": 1,
    "FALSE POSITIVE PROXY": 1,
    "FALSE NEGATIVE PROXY": 1
  },
  "3:reward_gain": {
    "FALSE NEGATIVE PROXY": 12,
    "TRUE POSITIVE PROXY": 11,
    "TRUE NEGATIVE PROXY": 9,
    "FALSE POSITIVE PROXY": 8
  },
  "end:stage_gain": {
    "ZERO LONG-TERM PROXY": 8,
    "TRUE POSITIVE PROXY": 8,
    "FALSE POSITIVE PROXY": 8,
    "TRUE NEGATIVE PROXY": 9,
    "FALSE NEGATIVE PROXY": 7
  },
  "end:reward_gain": {
    "TRUE NEGATIVE PROXY": 8,
    "TRUE POSITIVE PROXY": 6,
    "FALSE POSITIVE PROXY": 13,
    "FALSE NEGATIVE PROXY": 13
  }
}

ZERO单列；false-positive proxy不等于已证明危险动作。逐状态CI及是否排除0见sign_confusion.csv。

## 【Strong Positive Cases】

[
  {
    "state_id": "16011-64",
    "stage_delta": -0.4375,
    "ci95": [
      -1.3206974877791233,
      0.44569748777912344
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16048-69",
    "stage_delta": 0.03125,
    "ci95": [
      -0.11129933356561161,
      0.1737993335656116
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16013-111",
    "stage_delta": -0.46875,
    "ci95": [
      -1.0809684589934039,
      0.14346845899340388
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16022-124",
    "stage_delta": 0.03125,
    "ci95": [
      -0.7452313820649845,
      0.8077313820649845
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16056-69",
    "stage_delta": -0.8125,
    "ci95": [
      -1.6897399325119373,
      0.06473993251193744
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  }
]

Unknown允许保留；没有从结果反推deck pollution、synergy loss或token错误。

## 【False Positive Cases】

[
  {
    "state_id": "16030-127",
    "stage_delta": -0.09375,
    "ci95": [
      -0.3007990387214678,
      0.11329903872146779
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16011-64",
    "stage_delta": -0.4375,
    "ci95": [
      -1.3206974877791233,
      0.44569748777912344
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16001-127",
    "stage_delta": -0.15625,
    "ci95": [
      -0.4411186560674541,
      0.1286186560674541
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16013-111",
    "stage_delta": -0.46875,
    "ci95": [
      -1.0809684589934039,
      0.14346845899340388
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16004-147",
    "stage_delta": -0.09375,
    "ci95": [
      -0.4308889197492295,
      0.2433889197492295
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16053-239",
    "stage_delta": -0.3125,
    "ci95": [
      -0.7127533220026956,
      0.08775332200269564
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16033-147",
    "stage_delta": -0.40625,
    "ci95": [
      -0.9781691217775803,
      0.1656691217775803
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16056-69",
    "stage_delta": -0.8125,
    "ci95": [
      -1.6897399325119373,
      0.06473993251193744
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  }
]

Unknown允许保留；没有从结果反推deck pollution、synergy loss或token错误。

## 【False Negative Cases】

[
  {
    "state_id": "16005-157",
    "stage_delta": 0.0625,
    "ci95": [
      -0.415110610394378,
      0.540110610394378
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16000-161",
    "stage_delta": 0.125,
    "ci95": [
      -0.5135273979268437,
      0.7635273979268437
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16043-69",
    "stage_delta": 0.09375,
    "ci95": [
      -0.043170148320577834,
      0.23067014832057783
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16049-144",
    "stage_delta": 0.375,
    "ci95": [
      -0.2297856025072026,
      0.9797856025072026
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16037-153",
    "stage_delta": 0.34375,
    "ci95": [
      -0.2811846336785694,
      0.9686846336785694
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16060-77",
    "stage_delta": 0.65625,
    "ci95": [
      -0.2553613381561458,
      1.567861338156146
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  },
  {
    "state_id": "16014-190",
    "stage_delta": 0.03125,
    "ci95": [
      -0.5826791670684978,
      0.6451791670684978
    ],
    "reason": "Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes"
  }
]

Unknown允许保留；没有从结果反推deck pollution、synergy loss或token错误。

## 【Token Opportunity Cost】

[
  {
    "tokens": 1,
    "n": 22,
    "stage_delta": -0.024147727272727272,
    "reward_delta": -6.792613636363637,
    "future_opportunity_delta": -11.862215909090908
  },
  {
    "tokens": 2,
    "n": 18,
    "stage_delta": -0.08159722222222222,
    "reward_delta": -3.8194444444444446,
    "future_opportunity_delta": -6.671875
  },
  {
    "tokens": "3+",
    "n": 0,
    "stage_delta": null,
    "reward_delta": null,
    "future_opportunity_delta": null
  }
]

相同pre-action state下使用vs保留token，但同时改变候选，不能把整个行动收益归因于纯成本；不同token数量的状态还存在context混杂。3+无机会则N/A，禁止手调cost。

## 【Compute Cost】

| Horizon | Mean seconds/path | K32 two-branch seconds/state |
| --- | --- | --- |
| 1 | 0.771 | 49.353 |
| 2 | 1.859 | 118.948 |
| 3 | 2.710 | 173.460 |
| end | 5.984 | 382.961 |

seconds为每路径累积实测，K32成本是64条路径计时总量均值，不是并行wall；pilot续跑不重复已完成前缀。K成本详见convergence和正式记录。执行由3调至6worker，仅复用已提交原子cache，种子/样本/政策未变；温缓存与冷缓存动作/RNG相同已测。计时不含clone加载和cache I/O，不把混合worker/cache计时当严格加速实验。

## 【Evidence Strength】

本轮是版本化、可关闭、可复现的代理值验证，无训练/数据集生成/政策优化/在线扩局。有限样本和终局CI必须保留；短horizon与end一致也可能来自共同方差和通关上限。

## 【结论】

以完成数据解释强度；若没有可重复的更强长期信号，按硬停止条件冻结Reroll支线。

## 【V146 决策】

D: honor the Reroll hard stop; freeze V143 and V145 diagnostic tools, prioritize V146 BC Optimization Audit. No rollout teacher, value network or new labels now.。BC训练符号fit≈72.9%是明确且独立的已知瓶颈，本轮未处理。

## 【十项问题与研究停止条件】

{
  "decision": "D: honor the Reroll hard stop; freeze V143 and V145 diagnostic tools, prioritize V146 BC Optimization Audit. No rollout teacher, value network or new labels now.",
  "scope": "Rollout-based Long-Horizon Proxy under fixed forecast_rents_v143 in the restricted approximate simulator; not True Q or a policy-performance benchmark.",
  "q1_local_relation": "Primary rent-axis36 states: local vs end stage Pearson -0.178, Spearman -0.058; reward Pearson -0.174, Spearman -0.202. No strong positive long-horizon relation was established. Rare probability/cash strata n2 each are not used for correlations.",
  "q2_strength": "Weak descriptive association in a stratified development sample, not proof that local value is systematically wrong. Full-return estimation itself is noisy: independent16-sample end halves have stage Pearson -0.103, Spearman -0.026, sign agreement47.2%; reward Pearson0.239, Spearman0.225, sign agreement61.1%.",
  "q3_local_sign_accuracy": "Primary36: stage47.2% including ties,53.1% among32 nonzero reference effects; reward33.3%. All40: stage42.5%, reward35.0%. Stage ties8/40 are neutral rather than false positives/negatives. These are proxy signs, not verified true-action accuracy.",
  "q4_strong_positive": "Rent-axis Strong Positive:3/6 negative stage point effects,2/6 positive,1/6 zero. No local-positive/negative-stage case has a stage interval excluding zero. Strong-positive disagreement is a risk flag, not a demonstrated causal error or basis for threshold changes.",
  "q5_boundary": "Among15 nonzero stage directional disagreements in the primary36, Near-Zero contributes5, Moderate6, Strong4. Near-Zero is not selectively dominant (12/36 sampled states versus5/15 disagreements). All32 nonzero stage cases retain Unknown mechanistic explanation; random variance, continuation interaction and short-term bias are possibilities, not assigned causes.",
  "q6_horizon": "1/2 rent stage effects are all zero across40;3-rent gives little stage variation. Same-path reward end sign agreement is52.5%,60.0%,60.0% at1/2/3 rents, with Spearman0.079,0.211,0.225; none meets90%. Independent-half 2-rent reward correlations0.259 and0.023, signs50.0% and41.7%, are not repeatable evidence of predictive superiority.3-rent is marginally highest same-path reward rank but not a validated best horizon.",
  "q7_samples": "K32 vs64 pilot stage and reward signs agree75% in only4 states; this met the predeclared point-sign check, not certainty. FormalK32 stayed fixed. Independent16-sample end-half agreement is poor and most32-sample intervals include zero. No reliable minimum continuation count was established; do not automatically increaseK until significance.",
  "q8_token_cost": "Token1/2 states show fewer future legal reroll opportunities after reroll (-11.86 and-6.67 mean), but the intervention also changes the offer and subsequent path. Cross-token groups have different contexts. No new isolated inventory contrast or strong scarcity-cost-error evidence; frozen V144 inventory probes remain the direct evidence.3+ has no natural opportunity (N/A); resource cost unchanged.",
  "q9_compute_value": "K32 two-branch cumulative simulation time averages49.4s/1rent,118.9s/2rents,173.5s/3rents,383.0s/end per state. This is summed per-path runtime, not parallel wall time or a controlled cold-speed benchmark. No short horizon supplies a repeatable stronger long-horizon signal sufficient to justify online rollout or distillation.",
  "q10_priority": "Freeze Reroll exploration under the explicit hard stop. The known BC training symbol fit around72.9% is a stronger and more direct bottleneck. V146 should audit fitting, optimization and objective behavior on the frozen corpus before spending more on teacher complexity; V145 performed zero training.",
  "multiple_comparisons": "Unadjusted end stage interval excludes zero in1/40 states and reward in2/40; these do not certify mechanisms or teacher errors after multiple comparisons. Zero empirical variance gets a bounded conservative interval, never [0,0].",
  "asset_and_execution": "40 frozen states from37 episodes,19 selected/21 rejected opportunities;2560 formal paths, with256 additional convergence paths at IDs32..63. Pilot prefixes were resumed rather than rerun. A single execution-only3-to6 worker restart retained atomic results; no seeds, states, K or policy changed. Pilot spin-income bookkeeping was corrected from192 exact saved environment snapshots with zero replay.",
  "mechanistic_attribution": {
    "nonzero_stage_proxy_cases": 32,
    "Unknown": 32,
    "proved_synergy_loss": 0,
    "proved_token_spent_too_early": 0,
    "proved_deck_pollution": 0,
    "proved_short_term_score_bias": 0,
    "proved_random_variance_as_cause": 0,
    "proved_continuation_interaction_as_cause": 0
  }
}
