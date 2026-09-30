## 【当前版本】

V143 Teacher Reroll Value Integration

## 【本轮目标】

Reroll进入同一个长期租金价值比较框架。训练更新0；不改V130、V128、BC/候选Encoder、奖励、环境、租金表、符号或物品规则。未生成新版训练数据。

## 【冻结基线】

旧版本继续由forecast_rents调用；新版为forecast_rents_v143。旧RentForecastAgent源文件及V128/V130/V141/V142产物hash保持不变，V128全部48个shard hash核对通过。

V141历史128局：Teacher平均Stage11.609375、57胜；BC平均Stage9.6328125、4胜。本轮64个新开发seed16000–16063单独比较，不重定义旧基线。

## 【Teacher 旧逻辑】

符号分支只评分Pick/Skip，Reroll被排除；item/removal等由原Heuristic决策。租金预测8 trials、seed20270927、horizon30，按first_rent_paid→rents_paid→cash字典序选择。V143非重掷分支直接继承旧函数。

## 【V143 Reroll Value 设计】

从公开State重建独立采样器，复用PreparedSymbolOffers的真实候选规则分布；不接收GameEnv或实际RNG。每个可能符号只计算一次旧Teacher租金预测，全部采样offer共享候选结果。

Value为三维向量（首次租金通过比例、平均已付租金、平均期末cash）。E[max Value(new offer)]−ResourceCost与当前best在原字典序中比较。优势第一非零分量>0才重掷，threshold=0，完全相等保留旧动作。没有固定正bonus。

成本对比：zero=(0,0,0)，constant=(0,1/8,1 coin)，token_aware=constant×剩余租金阶段比例/max(tokens,1)/(1+max(pressure,0))。沿用V142 signed pressure=(rent−coins)/rent。第1分量成本为0，不让未来券价值扣减当前首次租金生存优先级。

1/8来自旧预测trial分辨率，1 coin为显式预留代理；这些不是经验证的最优资源价。该代理在rent预测相同但cash改善时可能过度抑制重掷，在预测已经无法存活时仍可能计入未来机会成本，列为V144校准重点。预测仍只含固定牌组30转，不含后续选牌策略。

## 【修改文件】

新增luck_agent/agents/rent_reroll_agent.py、tools/evaluate_reroll_teacher.py、tests/test_v143_reroll.py。扩展evaluation/evaluator.py注册新agent并记录版本/配置；旧入口和原Teacher源码不替换。更新seed_usage及ITERATION_STATE。

## 【测试结果】

完整522项通过，0 Failed。覆盖合法/非法、抽样前缀及阶段稀有度、RNG隔离、无未来读取、资源成本、确定性、旧分支兼容、trace及连续重掷更新、cache的经济/目录变更失效、既有BC/checkpoint加载。详细日志logs/v143-reroll/tests.txt。

## 【RNG / Leakage 验证】

Teacher输入只有公开State和目录；候选抽样seed来自公开状态hash与固定独立seed20260929。未复制或读取真实未来RNG。

测试：评分后拒绝Reroll时真实RNG/global RNG不变，与未评分对照逐步结果相同；更换隐藏RNG仍对同一公开State得到同分数。4局shadow每步核对真实RNG；旧Teacher控制全部动作。

Score cache包含有序实例/timer/bonus、物品、coins、rent/remaining spins/stage、forced/terminal/稳定身份状态、预测预算和目录hash。候选分布独立按完整公开State重建；不把MC估计随机结果当作真实下一次offer。

## 【Opportunity Suite】

构造A优秀、B较差/多券、C一般/最后券、D高压力、E低压力、F核心mouse/cheese协同、G零券、H物品phase八类fixture。不是新训练数据，不强制B/D/E必须重掷。A三种成本均拒绝；G/H不进入评分；B–F零成本存在正优势，但cost代理可改变决策。

在同一固定状态上比较N=8/16/32/64嵌套独立采样，最大向量误差vs64为{'8': [0, 0, 5.484375], '16': [0, 0, 3.859375], '32': [0, 0, 4.8984375], '64': [0, 0, 0.0]}。预设容限(.0625,.0625,5 cash)，选最小通过量N=16。16次不是所有状态的精度保证；cash误差随N不必单调，此小套件的rent分量未显示差异。

明细见opportunity_suite.csv、convergence.csv；non_reroll_compatibility.json记录8个固定状态兼容检查。

## 【Shadow Evaluation】

旧Teacher控制4局（16000–16003），共1390决策、276次Reroll机会。43次正优势（15.58%），改变43次建议，非重掷建议变化0。不全拒绝，也不全部重掷。

同276个已缓存状态的成本比较，无额外游戏重跑：

| 成本 | 正优势次数 | 占机会 |
| --- | --- | --- |
| zero | 150 | 54.35% |
| constant | 19 | 6.88% |
| token_aware | 43 | 15.58% |

stage/pressure/token分组及平均优势向量保存在机器报告shadow字段。

## 【Reroll Coverage】

| 策略 | 机会 | 执行 | 每局 |
| --- | --- | --- | --- |
| legacy | 4859 | 0 | 0.000 |
| v143 | 1369 | 125 | 1.953 |

机会数不同是策略耗券和轨迹变化的结果，不能把两者机会率差直接解释为预测准确率。新版按在线压力分组：

| 压力 | 机会 | 重掷 | 比例 |
| --- | --- | --- | --- |
| low | 1217 | 114 | 9.37% |
| medium | 152 | 11 | 7.24% |

low=pressure≤0；medium=0<pressure<1；high=pressure≥1。在线没有high样本，不作高压力泛化结论。

## 【Legacy vs V143】

先32局Smoke，后扩到同方案64局；复用前32局及shadow已执行的旧策略结果，不重复模拟。64局结果：

| 策略 | Mean Stage | Stage Std | Stage 95%CI | Mean Reward | Wins | Wilson 95%CI |
| --- | --- | --- | --- | --- | --- | --- |
| legacy | 11.6719 | 1.6528 | [11.2669, 12.0768] | 1047.94 | 31/64 | [0.3663, 0.6042] |
| v143 | 12.0781 | 1.3130 | [11.7564, 12.3998] | 1072.88 | 36/64 | [0.4409, 0.6771] |

全部零非法/零截断。每一租金存活率及Wilson CI在JSON.summaries.*.rent_survival字段。

## 【配对比较】

V143−Legacy平均Stage差+0.40625，paired bootstrap95%CI [-0.1094, 0.8906]；改善/相同/更差=24/24/16。bootstrap2000次，seed57，单位为配对episode seed。

Reward差+24.9375，CI [-104.9062, 135.0000]；Win比例差+0.0781，CI [-0.0938, 0.2344]。三个区间都包含0，不能证明提升，也不能证明非劣。

## 【Reroll 案例】

全部合法机会保留当前best、预期new best、std/SE/quantiles、cost、score、advantage及最终动作，CSV为shadow_reroll.csv和online_reroll.csv。

最大差异完整决策轨迹索引：

| seed | 旧Stage | 新Stage | ΔStage |
| --- | --- | --- | --- |
| 16056 | 7 | 12 | 5 |
| 16000 | 9 | 13 | 4 |
| 16003 | 9 | 13 | 4 |
| 16009 | 9 | 13 | 4 |
| 16011 | 13 | 9 | -4 |
| 16024 | 9 | 13 | 4 |

Reroll后立即best score改善88/125=70.40%；已覆盖最后一券，不把未来补券状态误当作立即结果。此代理不是因果胜率。

连续重掷run分布{'1': 81, '2': 22}；最多2次，无3+。每一步均重新评分并验证tokens−1，所有执行动作均满足正优势。26/125次的首个决定分量优势不超过一个outer-MC SE，是后续不确定性核查候选，不据此改本轮策略。

## 【性能成本】

| 决策类别 | 平均latency ms |
| --- | --- |
| Legacy所有决策 | 13.781 |
| V143非重掷机会 | 12.265 |
| V143重掷机会 | 236.420 |

最后32个新局的3-worker墙钟吞吐（含缓存行读取/pool/审计/trace）：

| 策略 | 新局数 | wall sec | episodes/sec |
| --- | --- | --- | --- |
| legacy | 32 | 58.64 | 0.546 |
| v143 | 32 | 150.54 | 0.213 |

64局按逐局审计耗时之和的等效吞吐Legacy0.182、新版0.069 eps，不是3-worker墙钟吞吐。新版online含额外旧分支兼容查询和trace写入；前4个Legacy时间由shadow减去实测新推理时间，保留额外I/O。状态分布/并发负载不同，不能当成同状态微基准或直接与旧0.263 eps比较。

优化复用同状态每个symbol/Skip的预测，而非N×重复forecast；bounded cache256个上下文跨重掷复用。未降低旧8 trials/30 horizon正确性合同。

## 【Regression】

旧Teacher、环境/规则/租金、BC与Dataset不变；非重掷策略直接委托旧函数，固定状态检查和online兼容断言通过。单次/连续重掷合法、资源更新正确。stage差既有正也有负；程序兼容通过不等于策略性能提升。seed与参数cache绑定，诊断计数/末券代理从已保存轨迹补全，没有重跑游戏。

## 【结论】

1. Teacher真正考虑Reroll：是，独立采样并计算E[max Value]及资源成本。

2. 实际选择：125次，平均1.953/局。

3. 状态：低/中压力且字典序净优势为正；逐stage/token/candidate明细在CSV，在线高压力无样本。

4. 策略改善：点估计Stage+0.406、Wins31→36，但配对Stage/Reward/Win CI均包含0，证据不足。

5. 重新生成训练数据：暂不支持直接启动；覆盖缺口已在框架上补齐，长期价值与成本代理还需要归因/校准。本轮未生成数据。归类为探索性Case A候选，未满足“性能已提升或非劣”的证明标准；不是Case E。

## 【V144 决策】

V144先做Teacher Reroll误差归因与估计不确定性审计；64局区间含零，暂不生成新数据或训练BC。独立BC Fit Capacity/Optimization问题保留。

优先分析+5与−4阶段案例，outer candidate sampling与inner8-trial预测误差分别核查，审计rent成本在预测等租金/濒死情形是否过度压制cash改善。原BC train symbol fit72.9%独立问题继续保留，教师价值质量尚未确认时不启动新Teacher数据或BC训练。

## 【Artifact】

reports/v143_teacher_reroll_value.json；logs/v143-reroll/{protocol.json,opportunity_suite.csv,convergence.csv,shadow_reroll.csv,online_reroll.csv,changed_decisions.csv,legacy_episodes.csv,v143_episodes.csv,smoke_gate.json,protected_hashes.json,comparison.json,tests.txt}；reroll_episode_traces/*.jsonl.gz保存完整公开决策轨迹。
