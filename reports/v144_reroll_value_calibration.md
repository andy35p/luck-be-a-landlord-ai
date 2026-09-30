## 【当前版本】

V144 Reroll Value Calibration

## 【本轮目标】

估计是否可信；Training Updates = 0。没有新增在线 benchmark、训练或阈值调整。

## 【冻结资产】

核验 421 个历史文件：Legacy/V143、V128、V130、V141–143及规则/编码源文件。hash 清单在 logs/v144-reroll-calibration/protected_hashes.json。

## 【新增工具】

tools/calibrate_reroll_value.py：完整机会提取、分量校准、嵌套样本分析、严格前缀案例、独立终局反事实和纯资源干预；每个任务缓存，支持中断后续跑。

## 【测试结果】

完整历史规则及现有接口测试 531 项通过，0 Failed；新增9项V144测试覆盖全机会提取、缺失offer、lex桶、采样前缀、N16重现、signflip、clone/RNG隔离、资源补充抽样及历史hash。见 logs/v144-reroll-calibration/tests.txt。

## 【Opportunity Dataset】

所有 1369 个机会；选择 125，拒绝 1244。拒绝状态的新候选/实际收益留空；不是失败样本。按首个非零分量、正负分别用经验三分位数分桶，不混合不同单位。

## 【Sampling Stability】

{
  "8": {
    "n": 1369,
    "sign_flip_rate": 0.013878743608473338,
    "selected_positive_to_negative": 13,
    "selected_n": 125,
    "hot_ms": 2.525808400287565,
    "cold_plus_hot_ms": 206.7846775018211
  },
  "16": {
    "n": 1369,
    "sign_flip_rate": 0,
    "selected_positive_to_negative": 0,
    "selected_n": 125,
    "hot_ms": 3.2556479181832554,
    "cold_plus_hot_ms": 207.5145170197168
  },
  "32": {
    "n": 1369,
    "sign_flip_rate": 0.006574141709276844,
    "selected_positive_to_negative": 1,
    "selected_n": 125,
    "hot_ms": 5.133476040908354,
    "cold_plus_hot_ms": 209.3923451424419
  },
  "64": {
    "n": 1369,
    "sign_flip_rate": 0.006574141709276844,
    "selected_positive_to_negative": 0,
    "selected_n": 125,
    "hot_ms": 9.026320160707147,
    "cold_plus_hot_ms": 213.2851892622407
  },
  "128": {
    "n": 1369,
    "sign_flip_rate": 0.01095690284879474,
    "selected_positive_to_negative": 4,
    "selected_n": 125,
    "hot_ms": 16.974520891158402,
    "cold_plus_hot_ms": 221.23338999269194
  }
}

N16→N128 正转负是决策不稳定，不是128真值；95%为逐分量正态近似区间，未计入内部8trial预测误差。

## 【Immediate Calibration】

{
  "0": {
    "n": 125,
    "correlation": null,
    "mae": 0.0,
    "rmse": 0.0,
    "bias": 0.0
  },
  "1": {
    "n": 125,
    "correlation": 0.4421235843010036,
    "mae": 0.2563613986384952,
    "rmse": 0.34200311223548974,
    "bias": -0.09158695927128427
  },
  "2": {
    "n": 125,
    "correlation": 0.6309166038886269,
    "mae": 44.765902120539074,
    "rmse": 61.198026171000436,
    "bias": 7.4874293258297255
  },
  "observed_sign_accuracy": 0.704,
  "cost_adjusted_sign_accuracy": 0.536,
  "gross_offer_gain_component_errors": {
    "0": {
      "n": 125,
      "correlation": null,
      "mae": 0,
      "rmse": 0.0,
      "bias": 0
    },
    "1": {
      "n": 125,
      "correlation": 0.43875006706975195,
      "mae": 0.2599375,
      "rmse": 0.3319678248245604,
      "bias": -0.0346875
    },
    "2": {
      "n": 125,
      "correlation": 0.6311903308407438,
      "mae": 44.778375,
      "rmse": 61.238596132259595,
      "bias": 7.942625
    }
  }
}

MAE/RMSE/Bias 按概率/租金/现金独立报告。估计减成本，observed gain未减成本，两种sign accuracy分开。只覆盖selected125；立即新候选分数仍然不是实际长期因果收益。

## 【Counterfactual Calibration】

20个经验分层状态，每个current/reroll分支32条独立终局continuation；后续策略均为冻结V143。另4个既有状态做同动作减少1token的scarce分支各32次，共1408条正式续局，smoke8条另存。使用不同SHA种子，未假装CRN；targeted replay精确核对公开状态和legal actions，deepcopy不修改原RNG。ΔReward是决策后剩余reward，比较在同状态抵消相同历史。

{
  "0": -0.04757359247208635,
  "1": -0.32648918179638525,
  "2": 0.22570974839191674
}

按实际决定分量分别分析：

{
  "0": {
    "n": 3,
    "stage_correlation": 0.9621032142443144,
    "reward_correlation": 0.7088618662283063
  },
  "1": {
    "n": 12,
    "stage_correlation": -0.3759494463680732,
    "reward_correlation": -0.3271111206700009
  },
  "2": {
    "n": 5,
    "stage_correlation": 0.3176808071289755,
    "reward_correlation": 0.18455309440923034
  }
}

逐状态差值与独立样本95%区间见counterfactual_summary.json。非零经验方差使用独立样本t近似，零方差用保守Hoeffding范围（无reward已验证界时N/A）；非同时区间，未校正多重比较。相关性只做描述，不证明proxy可用于排序。

## 【Advantage Buckets】

| Advantage Bucket | Count | Immediate Improve | Sign Stability | CF ΔStage | CF ΔReward |
|---|---:|---:|---:|---:|---:|
| axis0_moderate_negative | 1 | N/A (n=0) | 1.0000 | 0.0000 | -9.4062 |
| axis0_near_zero_negative | 1 | N/A (n=0) | 1.0000 | 0.1250 | 9.8438 |
| axis0_strong_negative | 1 | N/A (n=0) | 1.0000 | 0.0000 | -0.0625 |
| axis1_moderate_negative | 236 | N/A (n=0) | 0.9915 | 0.0625 | 46.2031 |
| axis1_moderate_positive | 41 | 0.6585 (n=41) | 1.0000 | -0.3906 | -77.0000 |
| axis1_near_zero_negative | 593 | N/A (n=0) | 0.9899 | -0.0781 | 4.2969 |
| axis1_near_zero_positive | 41 | 0.6341 (n=41) | 0.9268 | 0.0781 | 138.9375 |
| axis1_strong_negative | 409 | N/A (n=0) | 0.9976 | 0.2188 | -27.2500 |
| axis1_strong_positive | 40 | 0.8500 (n=40) | 1.0000 | -0.0312 | -25.3594 |
| axis2_moderate_negative | 1 | N/A (n=0) | 0.0000 | -0.2500 | -68.5000 |
| axis2_moderate_positive | 1 | 0.0000 (n=1) | 1.0000 | 0.0000 | 11.9375 |
| axis2_near_zero_negative | 1 | N/A (n=0) | 0.0000 | 0.0000 | 23.3438 |
| axis2_near_zero_positive | 1 | 0.0000 (n=1) | 0.0000 | 0.0000 | -12.6562 |
| axis2_strong_negative | 1 | N/A (n=0) | 1.0000 | 0.0000 | 17.4062 |
| axis2_strong_positive | 1 | 1.0000 (n=1) | 1.0000 | N/A | N/A |

CF为桶内所选状态等权均值，不是总体效果；axis不同不能宣称跨桶单调。每桶终局stage/win、std和reroll率在JSON。观察终局指标按机会计权，同episode重复且机会数受存活影响，不能当成独立episode比较。

## 【Better Cases】

- seed16000: ΔStage=+4, first divergence=81; POSSIBLY BENEFICIAL
- seed16003: ΔStage=+4, first divergence=81; POSSIBLY BENEFICIAL
- seed16009: ΔStage=+4, first divergence=81; POSSIBLY BENEFICIAL
- seed16015: ΔStage=+3, first divergence=106; POSSIBLY BENEFICIAL
- seed16024: ΔStage=+4, first divergence=94; POSSIBLY BENEFICIAL
- seed16033: ΔStage=+4, first divergence=147; POSSIBLY BENEFICIAL
- seed16036: ΔStage=+4, first divergence=64; POSSIBLY BENEFICIAL
- seed16054: ΔStage=+3, first divergence=81; RANDOMNESS DOMINATED
- seed16056: ΔStage=+5, first divergence=69; POSSIBLY BENEFICIAL
- seed16061: ΔStage=+4, first divergence=85; POSSIBLY BENEFICIAL

完整两条轨迹、首分歧前state、估值、新候选、后续重掷及outcome在对应目录。只在首分歧前声称严格同轨迹。

## 【Worse Cases】

- seed16007: ΔStage=-2, first divergence=77; RANDOMNESS DOMINATED
- seed16011: ΔStage=-4, first divergence=64; RANDOMNESS DOMINATED
- seed16014: ΔStage=-2, first divergence=110; RANDOMNESS DOMINATED
- seed16019: ΔStage=-3, first divergence=152; RANDOMNESS DOMINATED
- seed16038: ΔStage=-4, first divergence=114; RANDOMNESS DOMINATED
- seed16039: ΔStage=-2, first divergence=77; RANDOMNESS DOMINATED
- seed16040: ΔStage=-4, first divergence=64; RANDOMNESS DOMINATED
- seed16042: ΔStage=-3, first divergence=102; RANDOMNESS DOMINATED
- seed16045: ΔStage=-2, first divergence=69; RANDOMNESS DOMINATED
- seed16051: ΔStage=-2, first divergence=81; RANDOMNESS DOMINATED

完整两条轨迹、首分歧前state、估值、新候选、后续重掷及outcome在对应目录。只在首分歧前声称严格同轨迹。

## 【Resource Cost】

[
  {
    "state_id": "16014-268",
    "tokens": 1,
    "estimated_reservation": [
      0.0,
      0.02389705882352941,
      0.19117647058823528
    ],
    "pure_inventory_stage_value": {
      "delta": 0,
      "ci95": [
        -6.803319508059493,
        6.803319508059493
      ],
      "ci_method": "bounded Hoeffding union interval; zero empirical variance",
      "se": 0.0,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 10,
      "branch_b_mean": 10
    },
    "pure_inventory_reward_value": {
      "delta": 9.125,
      "ci95": [
        -18.154156745433603,
        36.4041567454336
      ],
      "ci_method": "approximate independent t (2.04); no multiplicity adjustment",
      "se": 13.372135659526275,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 44.75,
      "branch_b_mean": 53.875
    },
    "pure_inventory_win_value": {
      "delta": 0,
      "ci95": [
        -0.5233322698507302,
        0.5233322698507302
      ],
      "ci_method": "bounded Hoeffding union interval; zero empirical variance",
      "se": 0.0,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 0,
      "branch_b_mean": 0
    },
    "pure_inventory_next_rent_value": {
      "delta": 0,
      "ci95": [
        -0.5233322698507302,
        0.5233322698507302
      ],
      "ci_method": "bounded Hoeffding union interval; zero empirical variance",
      "se": 0.0,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 1,
      "branch_b_mean": 1
    }
  },
  {
    "state_id": "16008-300",
    "tokens": 2,
    "estimated_reservation": [
      0.0,
      0.007440476190476191,
      0.05952380952380953
    ],
    "pure_inventory_stage_value": {
      "delta": 0,
      "ci95": [
        -6.803319508059493,
        6.803319508059493
      ],
      "ci_method": "bounded Hoeffding union interval; zero empirical variance",
      "se": 0.0,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 11,
      "branch_b_mean": 11
    },
    "pure_inventory_reward_value": {
      "delta": 14.0625,
      "ci95": [
        -18.87292667772119,
        46.99792667772119
      ],
      "ci_method": "approximate independent t (2.04); no multiplicity adjustment",
      "se": 16.144816998882934,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 97.5,
      "branch_b_mean": 111.5625
    },
    "pure_inventory_win_value": {
      "delta": 0,
      "ci95": [
        -0.5233322698507302,
        0.5233322698507302
      ],
      "ci_method": "bounded Hoeffding union interval; zero empirical variance",
      "se": 0.0,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 0,
      "branch_b_mean": 0
    },
    "pure_inventory_next_rent_value": {
      "delta": 0,
      "ci95": [
        -0.5233322698507302,
        0.5233322698507302
      ],
      "ci_method": "bounded Hoeffding union interval; zero empirical variance",
      "se": 0.0,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 1,
      "branch_b_mean": 1
    }
  },
  {
    "state_id": "16027-78",
    "tokens": 1,
    "estimated_reservation": [
      0.0,
      0.09375,
      0.75
    ],
    "pure_inventory_stage_value": {
      "delta": 0.09375,
      "ci95": [
        -0.23790024510867647,
        0.42540024510867647
      ],
      "ci_method": "approximate independent t (2.04); no multiplicity adjustment",
      "se": 0.16257364956307668,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 12.75,
      "branch_b_mean": 12.84375
    },
    "pure_inventory_reward_value": {
      "delta": 41.78125,
      "ci95": [
        -145.61899225471805,
        229.18149225471805
      ],
      "ci_method": "approximate independent t (2.04); no multiplicity adjustment",
      "se": 91.86286385035199,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 942.0,
      "branch_b_mean": 983.78125
    },
    "pure_inventory_win_value": {
      "delta": 0.0,
      "ci95": [
        -0.171365483783223,
        0.171365483783223
      ],
      "ci_method": "approximate independent t (2.04); no multiplicity adjustment",
      "se": 0.08400268812903088,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 0.875,
      "branch_b_mean": 0.875
    },
    "pure_inventory_next_rent_value": {
      "delta": 0,
      "ci95": [
        -0.5233322698507302,
        0.5233322698507302
      ],
      "ci_method": "bounded Hoeffding union interval; zero empirical variance",
      "se": 0.0,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 1,
      "branch_b_mean": 1
    }
  },
  {
    "state_id": "16032-64",
    "tokens": 2,
    "estimated_reservation": [
      0.0,
      0.039724576271186446,
      0.31779661016949157
    ],
    "pure_inventory_stage_value": {
      "delta": 0.21875,
      "ci95": [
        -0.5468495634352584,
        0.9843495634352584
      ],
      "ci_method": "approximate independent t (2.04); no multiplicity adjustment",
      "se": 0.3752939036447345,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 11.625,
      "branch_b_mean": 11.84375
    },
    "pure_inventory_reward_value": {
      "delta": 42.03125,
      "ci95": [
        -114.88083034249394,
        198.94333034249394
      ],
      "ci_method": "approximate independent t (2.04); no multiplicity adjustment",
      "se": 76.91768644239899,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 782.4375,
      "branch_b_mean": 824.46875
    },
    "pure_inventory_win_value": {
      "delta": 0.0625,
      "ci95": [
        -0.19403770237907625,
        0.31903770237907625
      ],
      "ci_method": "approximate independent t (2.04); no multiplicity adjustment",
      "se": 0.12575377567601775,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 0.40625,
      "branch_b_mean": 0.46875
    },
    "pure_inventory_next_rent_value": {
      "delta": 0,
      "ci95": [
        -0.5233322698507302,
        0.5233322698507302
      ],
      "ci_method": "bounded Hoeffding union interval; zero empirical variance",
      "se": 0.0,
      "n_per_branch": [
        32,
        32
      ],
      "branch_a_mean": 1,
      "branch_b_mean": 1
    }
  }
]

纯inventory probe不是reroll效果；按token数量、早/晚期分开，少量状态无法检验系统偏差。实际3+token机会不存在，N/A。cost中租金分量非零会在firstpass相等、rents相等时拒绝任意cash收益：这是词典序结构效应，不能凭此认定成本错误。

{
  "state_ids": [
    "16027-78",
    "16032-64"
  ],
  "continuation_samples": 32,
  "branch": "scarce",
  "reason": "Original resource probes are stages9/10; add earliest stage token1/2 from the existing20 to cover early reservation. No primary CF state/seed count or policy changed.",
  "selector": "minimum rent_stage among existing20 per token count; digest tie-break; no continuation outcome criterion",
  "scope": "Supplementary inventory audit, not significance-driven benchmark expansion"
}

## 【Rent Pressure】

{
  "low": {
    "count": 1217,
    "selected": 114,
    "cf_states": 13
  },
  "medium": {
    "count": 152,
    "selected": 11,
    "cf_states": 7
  },
  "high": {
    "count": 0,
    "selected": 0,
    "cf_states": 0
  }
}

保持V142 signed gap/rent：low≤0，medium(0,1)，high≥1。high无在线机会，拒绝后死亡案例N/A，不用人工fixture替代自然证据。

## 【Build / Synergy】

{
  "better": {
    "candidate_rows": 60,
    "episodes_with_context_bonus": 7
  },
  "worse": {
    "candidate_rows": 60,
    "episodes_with_context_bonus": 4
  }
}

直接复用已有Heuristic score_symbol，记录当前deck与empty deck评分差；这是旧启发式context贡献，不是新Build Score，也不是Teacher长期synergy真值。逐候选见build_context_scores.csv。BUILD/SYNERGY ERROR因果计数N/A，不能由长期失败反推build破坏。

## 【Compute Tradeoff】

catalog预测共享给8/16/32/64/128；hot_ms仅抽offer与汇总，cold_plus_hot_ms（历史字段名）包含首次forecast或cache lookup成本，连续重掷可能命中已有cache，不能视为严格全冷计时。不同N并非重算所有候选。

{
  "mean_samples": 19.70489408327246,
  "allocation": {
    "16": 1300,
    "128": 35,
    "64": 19,
    "32": 15
  },
  "disagreements_vs128": 7
}

自适应仅研究：领先分量SE为0时的置信比可能虚高，未替换policy。

## 【Failure Attribution】

{
  "SAMPLING NOISE": 3,
  "RESOURCE COST ERROR": 0,
  "SHORT-HORIZON VALUE ERROR": 0,
  "BUILD / SYNERGY ERROR": 0,
  "RANDOM OUTCOME": 0,
  "NO CLEAR ERROR": 34
}

仅37个立即未改善offer；sampling flip是候选解释，不能证明该offer由采样噪声造成。RESOURCE COST ERROR / BUILD ERROR未被证实；随机坏offer不等于错误动作。逐例证据与不确定性在failure_attribution.json。

## 【结论】

立即改善88/125=70.4%，受选择偏差，不能回答所有机会的校准。长期只做20状态独立反事实，不能宣称V143更强或无效。N16正转负=4/125；先审查采样可靠性。资源偏差没有充分证据。危险候选包括低有效分量margin、领先分量零样本方差、连续消耗最后token；属于待验证风险，非已证明错误。V143保持冻结作为审计参照，暂不认定可靠的新标签教师。

## 【V145 决策】

D (provisional): limited rollout / long-term value validation; keep V143 frozen, defer BC optimization and new teacher labels。BC train符号fit≈72.9%问题继续保留，本轮未训练；不根据终局结果手调成本。

## 【七项问题与证据边界】

{
  "v145_decision": "D (provisional): limited rollout / long-term value validation; keep V143 frozen, defer BC optimization and new teacher labels",
  "evidence_strength": "Exploratory development audit, not a policy promotion or confirmed causal error",
  "q1_immediate": "Observed gross improvement 88/125 (70.4%); after subtracting the fixed reservation vector, realized positive advantage is 67/125 (53.6%). Active rent-axis buckets improve 63.4%,65.9%,85.0% from near/moderate/strong positive. This supports some local ordering, not calibrated probabilities or all-opportunity accuracy; rejected offers are unobserved.",
  "q2_longterm": "Not established. In 20 stratified states, all final-stage intervals include zero. The active rent coordinate (n=12) has descriptive correlations -0.376 with stage difference and -0.327 with reward difference. Bucket means are not monotonic. One reward interval excludes zero before multiple-comparison correction; it is not confirmatory evidence. Do not infer V143 superiority, no effect, or a proven systematic value error.",
  "q3_samples16": "A baseline budget, not universally reliable near the boundary: 15/1369 signs change at N128; 4/125 selected positives turn negative, including 3 observed non-improving offers. N128 is a larger diagnostic sample, not ground truth. N16 to128 adds about14ms with shared candidate forecasts; adaptive normal-interval research uses19.70 mean samples but still disagrees with128 in7 states. Do not change V143 policy in this audit.",
  "q4_resource_cost": "No demonstrated systematic bias. Four existing states cover late/early token1/2 inventory interventions (32 independent samples each). Early full-versus-scarce stage values are +0.09375 and +0.21875, both intervals include zero; late point values are0. Counts occur in different states, so this does not isolate a scarcity gradient or prove the last token is more valuable. Forecast reservation and full-run stage have different horizons. Tokens3+ N/A.",
  "q5_risk": "Low active-coordinate confidence is an exploratory risk signal: observed failure rates 42.3% (26 states, ratio<=1) versus26.3% (99 states, ratio>1). Boundary sign reversals and lexicographic rent reservation deserve scrutiny. Continuous rerolls/token scarcity/build damage are not established causal failure categories; random bad offers are compatible with beneficial expected actions.",
  "q6_teacher_freeze": "Keep the existing V143 implementation immutable as the audit reference. Evidence is insufficient to certify it as a reliable long-term labeling teacher or to regenerate a dataset. These are different meanings of freeze.",
  "q7_next": "Continue teacher value calibration with a predeclared limited-rollout study designed to distinguish local forecast from long-term action value; include cheap larger-sample controls. Do not hand-tune resource cost from episode outcomes. BC train symbol fit around72.9% remains an independent deferred problem.",
  "why_not_A_B_C_E": "A: no demonstrated long-term calibration. B: 3.2% selected sign reversals do not establish sampling as the main failure. C: inventory intervals and cross-state context do not establish cost bias. E: wide intervals and stratification do not establish negligible causal effect. D is a research priority under uncertainty, not a finding that short-horizon error is proven.",
  "selection_limit": "20 states across15 episodes, 8 selected rerolls and12 rejected opportunities; one singleton cash-positive bucket has no CF sample (N/A). State means are not an unbiased overall policy effect. The separately frozen resource coverage amendment reused existing states and did not alter primary continuations."
}
