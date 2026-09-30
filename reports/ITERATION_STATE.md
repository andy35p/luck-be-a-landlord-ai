# 自主迭代续接（2026-09-26）

用户要求自主推进，每个有用里程碑简报，无需逐步确认，以当前五小时账户额度为约束。不为耗尽额度重复无效任务；不自动充值或使用重置信用。最近读取额度为五小时已用 98%，不是项目独占额度。

## 已完成

- 生产 collector 0.5 保持原安装。V084 完整 90 秒观察正常结束。
- V085 验证选牌、旋转及租金失败；V086 验证 166→16 扣租 150、次数 3→4、下一期 [225,7]、黄辣椒入库。原存档均已恢复，自检通过。
- V087：10 个最小实机快照、6 项离线回归。受控与自然数据区分，不作为训练数据。
- V088：固定白名单打包、隔离目录启动、全量 417 项测试通过。
- V089：离线覆盖审计发现 11 个自然决策全拒绝（物品+库存+候选），2 项新增测试通过。
- V090：包内容校验、启动前检查，2 项新增校验测试通过；最新包 outputs/live-assistant-v090.zip，隔离启动通过。无外部发布。

## 下一批优先工作

更新 V091：已增加 manage_live_install.py，5 项假目录安装/回滚测试通过；真实目录只读预检通过，未修改真实安装。最新包 outputs/live-assistant-v091.zip（24 文件+manifest）。后续不必重复实现基础安装器；优先补并发/中断防护及实际包验收，再继续工坊可行性与规则覆盖。

更新 V092：已补同目录安装/回滚文件锁互斥及未完成 prepared 凭据阻止重装，安装器 7 项测试通过。最新包 outputs/live-assistant-v092.zip；后续优先增加中断事务只读诊断/确定性恢复，再做实际包验收。真实安装仍未改动。

更新 V093：inspect/recover 已支持安装切换三个边界的确定性诊断与恢复（默认只读）。含首次安装中断、冲突拒绝，安装器共 10 项测试通过。尚未覆盖回滚中断及恢复自身中断。最新包 outputs/live-assistant-v093.zip。账户五小时窗口已更新，最近使用率为 15%，原 98% 已过时；用户再次明确要求继续自主迭代。

更新 V094：回滚中断和恢复自身中断已覆盖，安装器 13 项测试通过。用包内工具在真实游戏目录完成同版本 install --apply → rollback --apply，最终 rolled_back，12 项自检通过、5 份存档哈希不变。未启动游戏。最新包 outputs/live-assistant-v094.zip。下一步转向官方模组入口/规则支持，不继续重复安装器边界测试。

更新 V095：只读审计当前安装 PCK 的 Main.tscn，确认普通模组入口有两处校验调用、函数许可列表为空、仅 _init 声明例外和字段赋值限制。现有轮询/文件读写/显示实现不能直接迁入普通工坊脚本。未绕过限制，没导出游戏源码。详见 workshop_distribution_audit.md 与 v095_mod_surface.json。下一步优先增加有独立规则依据的 live 支持范围；不能宣称工坊目标已完成。

1. 本地包安装/回滚演练：可先在隔离假游戏目录测试，避免再次改用户存档。当前包是人工复制插件的说明，尚无事务式安装器；需保留旧文件和恢复清单、拒绝游戏运行时替换。
2. 官方工坊入口可行性：官方文档与当前 SlotWeave 架构不等同。源码观察应只读，不能声称 DLL 直接可订阅运行。结论见 workshop_distribution_audit.md。
3. 规则支持扩展：以 v089_scope_coverage.json 为依据，先选择能验证的简单符号/物品组合，增加独立对照，再决定是否放开 live_advisor 白名单。不要仅删除 items 拒绝来制造正向推荐。

## 环境与注意事项

- CWD 为本项目，Windows PowerShell。没有要求子代理，不要启动代理。
- .venv-model Python 可用于工作区测试；实际 AppData 读取使用普通非 Store Python，原 Store Python 有重定向问题。
- 新启动器 start_live_assistant.ps1 支持普通 Python 自动查找和显式路径，不要求 Codex 缓存路径。
- 实机 UI 必须使用 computer-use 技能的 @oai/sky，通过 node_repl 工具；每次动作基于新观察。实机测试先备份、关闭后恢复并核验。
- 所有现有工作不提交、不上传。仓库有大量此前工作未提交，不能清理或撤销。
- 最近全量日志 logs/v088-full-tests.txt。最新只改打包/审计，目标测试已通过，避免无变化重复跑全量。
- 当前无游戏或后台观察任务需要保留；不应自动在额度重置后启动新长时测试。

更新 V096：受限策略 v2 新增 sapphire/sand_dollar，保持物品/未知伙伴/永久加成拒绝。437 项全量测试通过（run_tests.py 含 legacy；仅 discover tests 为 223 项，不是全量）。历史 11 个自然决策仍全部超范围。最新包 outputs/live-assistant-v096.zip 已解压完整性核验及独立目录空源启动通过；没有改安装或存档。详见 v096_simple_symbol_scope.md。后续优先按实际阻塞核验物品与伙伴组合，不能仅删除白名单来扩大覆盖；安装器与工坊入口审计已完成当前可做部分。

更新 V097：策略 v3 新增 live_item_scope.py，严格核验鸡蛋盒/避税各一份与既有 11 符号组合；独立符号集合防止未来自动扩张。当前安装 Item.tscn 规则事实及真实物品投影夹具已保存。47 项 live 测试通过；包 outputs/live-assistant-v097.zip 校验与独立目录启动通过，未安装、未改存档。历史 11 自然决策仍因复杂库存候选拒绝。后续应研究负收益/计时符号所需状态证据，或自然新局实机覆盖；不能删除守卫冒充覆盖率提升。详见 v097_item_compatibility.md。

更新 V098：已准备并编译 integrations/collector_v06，补 times_displayed/values/modded/inherit_effects 原始字段及 collector_version。0 警告错误，但尚未实机验证，未安装；生产仍 0.5，交付包仍 V097。V086 524 次计时符号观测均缺字段；审计工具 3 测试通过。下一步优先备份后候选版实机计时字段验证、恢复核验，不继续增加白名单。详情 v098_raw_timer_capture.md。dotnet 位于 C:/Program Files/dotnet/dotnet.exe。

更新 V099：0.6 候选已临时实机两次旋转，喜鹊 2→3→0、赌徒 5→6→7，金币54→74→102。values 载入时尾部零、旋转后变短，后续解析不能固定长度。夹具及2回归测试通过，原始日志含中途9.23小时停留，绝非连续主动稳定性测试。已关闭游戏恢复2插件+5存档，7哈希相符；生产仍0.5、包V097。下一步计时状态解析及未出场边界，详见 v099_real_timer_capture.md。当前没有需要保留的游戏进程。

更新 V100：新增 live_timer_state.py 不可变原始计时解析，喜鹊/赌徒参数仅接受已验证2/4长度尾零形式，不从UI推导、不取模。audit_timer_capture 已集成；V099 62298重复观测全部格式可读（仅2实例）。14计时相关测试通过，其中4新增。未改游戏/模型/建议白名单，生产仍0.5、交付包V097。下一步查 reels.icons 是否完整库存及未出场计数证据，不能直接把 grid_position 当作当前出场证明。详见 v100_timer_state_parser.md。

更新 V101：当前源码证实 reels.icons 库存池与 displayed_icons 结算棋盘分开，后者递增 times_displayed。新增 collector_v07 候选输出 displayed_board 实例矩阵，编译成功但尚未实机；0.6源码保留。live_board.py 验证5x4唯一身份且属于库存，4合成测试通过。下一步备份后0.7实机映射验证及非空未出场计时；当前无运行游戏，生产0.5、包V097。详见 v101_board_membership.md。

更新 V102：0.7候选临时实机一转，显式棋盘两布局逐格对屏，25库存/20格/5场外空位，非空16。48有效记录、26标题界面空棋盘被拒；不能把prompt/effects当作完整稳定条件。实机夹具2新增测试、棋盘相关6通过。已关游戏恢复2插件+5存档7哈希一致，生产0.5包V097。下一步需隔离受控超容量库存场景，非空16自然继续刷无法验证未出场计时。不要混入训练或自然评估。详情 v102_real_board_mapping.md。

更新 V103：隔离受控插件 controlled_timer_test 在spin18将25实例替换喜鹊并计数归零，仅一次初始化，随后2真实旋转。每转20出场+1/5场外不变，共50实例变化符合；第二转5个原场外重入0→1。2实机夹具测试通过，142记录全部被自然审计排除。已关游戏恢复2插件+5存档7哈希一致；生产0.5包V097。下一步汇总0.7观察契约验收及显示兼容/回滚/参数漂移门槛，不重复随机刷计数。最近额度五小时使用52%，周84%（V103开始查询，后续会变化）。详见 v103_offboard_timer.md。

更新 V104：修复实时建议受控记录隔离缺口，LiveAdvisor默认拒绝test_fixture/fixture_applied存在（含false/null），撤回旧建议；仅离线allow_test_fixtures=True可启用并保留标记。LiveFeed默认不可启用。3新增测试，64live测试通过，全量461通过。最新包outputs/live-assistant-v104.zip，生产仍0.5，完整性/独立启动通过。下一步0.7消费者→显示兼容实机验收及升级事务验收；未改安装存档。详情v104_fixture_isolation.md。

更新 V105/V106：0.7正常插件显示兼容：30.109s不支持→离线屏幕验证，20.125s菜单消费者拒绝日志验证（暂停文字截图晚，不声称视觉确认）。恢复7哈希一致。打包增加0.5/0.7显式版本和分别指纹，默认0.5，3构建测试通过。新包outputs/live-assistant-v106.zip为0.7；真实目录用包内安装器0.5→0.7→0.5完成，12恢复自检通过。receipt=f637bb80f1254b07a06f790c9c6da540。当前无游戏/消费者，安装0.5；0.7有限本地测试可用，旧包V104保留。下一步转回观察契约和策略适配，别重复安装器验收；工坊原生限制仍未解决。详见v105_v106_collector_upgrade.md。

更新 V107：LiveAdvisor接入live_collector_contract.py，0.7必须显式5x4实例矩阵合法且符号/物品modded、inherit_effects均false。未知版本/混合字段拒绝；旧无版本0.5原兼容保留。4新增测试、69live通过；V102/V105普通就绪记录47+64全通过契约（含心跳，策略仍受限）。新包outputs/live-assistant-v107.zip含0.7与27白名单文件，完整性/独立启动通过。没有再动游戏存档，安装仍0.5。下一步真实计时符号与教师评分兼容性，别只删白名单。详见v107_observation_contract.md。

更新 V108：发现旧引擎喜鹊同类累计周期问题，20新喜鹊首转旧+25/逐实例-20（无物品合成对照）。新增instance-magpie-v1继承现有Goldfish实例环境，独立remaining1..4到期+9重置，旧源码不变。5引擎测试及实机轨迹对照通过；阶段全量471通过，补rule_identity后4版本测试通过（含1新增回放），未再全量。新config可main/evaluate，random/heuristic各100种子0..99零截断，平均通过租金3.36/6.51，非实机胜率。原教师喜鹊仍-2未改。下一步周期感知评分独立实验，别直接放实时白名单。游戏未动，包仍V107。详见v108_instance_magpie.md。

更新 V109：新增可选heuristic_magpie_cycle，固定库存独立出场DP估计租前新喜鹊收入/预期出场次数，原其他评分/移除不变。4新增测试+3并行测试通过。固定开发0..999原/候选平均租金6.541/6.757胜率17.6/21.5%；留出1000..1999为6.545/6.631、18.2/20.3%，主差+0.086近似95%CI[-0.075,0.247]，不推广默认/实时/训练。4000局零截断，留出候选符号决策分歧811/49228。脚本tools/compare_magpie_cycle.py存源码指纹/逐局CSV；日志v109-holdout及报告v109_magpie_cycle_experiment.md。下一步诊断已保存受损种子，勿追加样本追显著或用留出调参；如新策略需新协议新种子。游戏未动，包V107。

更新 V110：对V109留出最差3/最好3固定种子诊断，tools/diagnose_magpie_cycle.py先核源码指纹/规则身份，12条对局重放与原CSV7结果字段全部一致。最差1121/1188/1323：原13新2，首分歧奶酪/肥皂→喜鹊，均剩4转评分1.25，无喜鹊移除且自身收入正；最好1170/1674/1064也剩4转，煤/奶酪→喜鹊。不能把结果因果归于单次周期，分叉后库存/RNG不同。没有调参/新样本/训练，仍不推广。权威记录v110_magpie_verified_cases.json，早期v110_magpie_cases.json为未核指纹中间物。下一步若研究策略需统一候选比较标准、新协议新种子，别用已看案例当验证。游戏/包未动。

更新 V111：新增evaluation/choice_forecast.py，公开GameState重建InstanceMagpieEngine，用显式独立种子对所有PICK_SYMBOL/SKIP统一预测租前收入。不复制live RNG、不读effect_state；冻结后续选择/移除/租金结算，仅条件收入，不是存活概率。4测试通过，25硬币7转16采样合成4动作约37ms，喜鹊137.5/肥皂147.4375/煤134.8125/skip140。未接默认/实时/训练，未用V109种子调参。下一步固定代理决策规则和预算，未用小种子验证耗时合法性再独立对照。包V107游戏未动。详见v111_public_choice_forecast.md。


## V112
可选 forecast 策略完成：7 项针对测试通过；新种子 3000–3009 两策略各 10 局无截断。平均阶段 10.6 对 6.0，单次耗时 12.354 对 0.200 秒。仅冒烟，不证明效果、不晋升。详见 v112_forecast_agent_smoke.md。


## V113
固定新种子4000–4199，每策略200局：forecast平均阶段10.475 vs heuristic6.620，配对差+3.855，95%近似CI[3.298,4.412]。胜率均17.5%，无截断。通过预设研究门槛但不证明胜率非劣，不晋升默认/实机/训练。483全量回归通过。下一步诊断晚期失败/短视选择。详见v113_forecast_comparison.md。


## V114
6案例12回放源码指纹与V113一致，终局精确复现。预测在101次煤候选中0次选煤；煤15/20出场成熟超出租金<=10转窗口，证实规划盲区但非因果胜率结论。先设计跨租金公共状态规划/成熟确定性验证，不加手工煤奖励，不调默认。详见v114_forecast_diagnosis.md。


## V115
新增跨租金公共状态条件预测，复用引擎扣租/死亡/通关停止；支持煤15/20成熟收益，未来主动选择仍排除。11相关测试通过，原forecast种子4000–4002全终局字段与V113一致。重构修改源码指纹，旧诊断应严格拒绝当前源码，不篡改旧清单。尚非策略，下一步先固定决策排序和独立实验。详见v115_cross_rent_forecast.md。


## V116
新增可选forecast_rents，8样本30转，先当前租金安全再阶段/现金。14相关测试通过；新种子5000–5009各10局零截断，阶段11.7 vs短期9.7，胜率40% vs10%，仅冒烟。44.044s vs10.662s存在部分并发，不作严谨性能比。未晋升，下一步冻结主要胜率指标的新种子实验。详见v116_rent_forecast_agent.md。


## V117（运行中）
冻结 configs/v117_rent_comparison.json：种子6000–6099，forecast vs forecast_rents各100局，主要胜率差95%配对近似区间下界>0、阶段均值不下降、零截断。工具tools/compare_rent_forecast.py每10局保存，检查源码/规则数据/协议指纹前后一致。有效输出logs/v117-rent-comparison-run1；最初logs/v117-rent-comparison仅保存协议，因catalog路径错误在任何评估前退出，已保留。有效进程工具session=97209，必须检查同一会话，不重复启动。尚无最终效果结论。


## V117完成
同一session97209正常结束。固定新种子6000–6099各100局：跨租金49% vs短期12%，配对差+37pp，95%近似CI[24.65,49.35]pp；阶段11.72 vs10.48，零截断。独立逐批验收通过，490全量测试通过。有效目录logs/v117-rent-comparison-run1。研究门槛通过，不晋升默认/实机/训练。下一步测单决策延迟并保持策略语义优化，为教师生成成本提供证据。详见v117_rent_forecast_comparison.md。


## V118
既有种子6000–6002性能回放全字段吻合，267符号决策均66.94ms/P95 127.87ms/max136.89ms。热点证实消耗计划每转两次、棋盘构建三次；下一步只复用当转计划并逐步严格等价验证。logs/v118-latency保存未优化基线与profile；代码未改。详见v118_forecast_latency.md。


## V119
单次spin内复用consumption_plan，finally清理，外部调用不缓存；492全量测试通过。5随机局逐步状态/事件/RNG相等，跨租金种子6000/6001缓存/未缓存818决策轨迹摘要相等，耗时约降9.5%。未改策略参数与legacy，不覆盖V117源码清单。下一步按局多进程确定性/吞吐，游戏包仍V107。详见v119_consumption_cache.md。


## V120
跨租金策略8完整局单/双进程全部逐局字段一致零截断，交替顺序墙钟含启动：单32.035s/双19.250s，约1.66倍吞吐。4并行回归通过，新增不均匀批次跨租金短回归。未改默认workers和策略。下一步核对新规则域教师轨迹schema/种子隔离再生成小批量，不混旧BC。详见v120_parallel_forecast.md。


## V121
旧煤/金鱼编码不兼容新域，新增独立magpie-spatial-candidates-v1（旧入口不改），1版本/计时器测试通过。跨租金教师3工程样例种子train7000/test7004/validation7018共1186转移，精确回放+编码+batch通过，无训练。logs/v121-magpie-smoke，不是统计留出集。下一步新域读取端manifest/哈希/教师/分区验收，不直接训练。详见v121_magpie_trajectory_smoke.md。


## V122
新增显式magpie smoke读取器，先验全部分区再返回指定split；1186条成功。6类副本损坏拒绝（哈希/教师/规则/重复seed/path逃逸/缺分区），原数据前后hash未变。无训练，尚非扩量多episode读取合同。详见v122_magpie_reader.md及checks.json；下一步新域模型前向/重载兼容验证。


## V123
独立喜鹊模型接口复用空间架构，旧默认不变；1186样例前向、13802补齐mask、合法argmax和保存重载精确通过，旧模型入口拒新版本。4相关测试通过。outputs/v123-magpie-prototype/untrained.pt仅原始标量接口原型，0更新，未部署。下一步训练分区专属归一化及正式checkpoint数据指纹绑定。详见v123_magpie_model_interface.md。


## V124
magpie-smoke-zscore-v1只拟合train409条，绑定manifest与编码；重算校验拒改均值。2自动化测试通过，1186条缩放有限，train均值误差<2e-15。scaler与V123 raw原型是独立文件，尚未绑定正式checkpoint。0更新。下一步正式研究checkpoint合同，不将小样本作为泛化结论。详见v124_magpie_normalization.md。


## V125
新增magpie-research-checkpoint-v1绑定规则/词表/教师/数据manifest和重算训练scaler；409归一化样例保存重载logits精确，7类错配拒绝。outputs/v125-magpie-checkpoint/research-zero-updates.pt为0更新研究样例。下一步固定少量训练链路smoke，不声称泛化或教师49%效果。详见v125_magpie_checkpoint.md。


## V126
固定20次BC工程更新完成（seed123/batch32/lr.001），仅单train局195多候选决策。trainNLL2.3278→1.1918/匹配38.46%→68.21%；val62.61%、test53.10%仅各单局工程指标非胜率。梯度有限，重载精确，496全量测试通过。模型outputs/v126-magpie-training-smoke/research-20-updates.pt，不部署。下一步逐阶段错误与在线接口行为检查，不立刻扩大训练。详见v126_magpie_training_smoke.md。


## V127
研究MagpieModelAgent可运行，固定V126模型种子8000–8009共1460合法动作零截断，但全部stage5/spin36失败。训练符号匹配42/99，移除83/84抬高总体；val符号51/89、test49/99，非胜率。无新训练/调参，不部署。下一步多对局分片数据覆盖/隔离协议，不继续单局过拟合。详见v127_magpie_model_diagnosis.md。


## V128运行中
固定48局多分片数据协议configs/v128_magpie_corpus.json：train9000–9031/validation10000–10007/test11000–11007，教师forecast_rents，2进程，每局精确回放和编码，全部成功才manifest。工具tools/collect_magpie_shards.py，有效session31984必须先轮询同一会话，不重复启动。输出logs/v128-magpie-shards/progress.jsonl逐局记录；尚未完成、未训练，不读test效果做调参。此次查额度五小时92%已用。下一步进程完成后独立核对48种子/哈希/合同，并添加正式分片读取器（旧smoke读取器不兼容），不要改运行中luck_agent源码触发指纹失败。


## V128完成
原session31984正常完成48局/17889转移，全部逐步回放+编码，无截断，独立verify_magpie_shards通过。train11755/val3149/test2985，train多候选symbol2843/item351/remove655。未汇总test效果、未训练。logs/v128-magpie-shards/manifest.json已生成。下一步正式多分片读取/训练scaler/checkpoint绑定，旧smoke合同不适用；新代码变更会使严格源码检查失败，应保存现有证据不改原manifest。详见v128_magpie_sharded_corpus.md。


## V129
正式magpie_corpus读取+magpie-corpus-zscore-v1，实际train11755条/32种子严格匹配，训练归一化均值误差<8e-15；3类副本损坏拒绝（重叠/缺片/非train hash）。outputs/v129-magpie-corpus/train_scaler.json。0新更新，无test调参。读取器检查合同/数据而非当前全源码必须等于历史（历史hash保留不改）。下一步独立corpus checkpoint合同+固定训练协议。详见v129_magpie_corpus_reader.md。


## V130
固定200更新多局BC完成：train3849多候选NLL1.7944→.5476，匹配28.60%→78.44%；val1111匹配81.28%，符号train72.88%/val75.85%。test未算指标。梯度有限，全部train重载logits精确。新magpie-corpus-checkpoint-v1与smoke双向拒绝，模型outputs/v130-magpie-corpus-training/research-200-updates.pt。下一步新合同Agent+冻结自由对局未训/已训/教师同seed对照，不部署。详见v130_magpie_corpus_training.md。


## V131运行中
冻结configs/v131_model_rollout.json：新种子12000–12031，未训seed123/固定V130训练模型/forecast_rents教师三方。新MagpieCorpusAgent复用公共模型Agent通过类属性选择checkpoint/scaler。有效session89329，先检查同一会话，勿重复启动；输出logs/v131-model-rollouts。主指标训练-未训配对stage差，胜率/teacher gap次要。无训练、不看封存test轨迹指标。代码运行前后hash检查，运行中不要编辑luck_agent。完成后审查comparison和全部种子/截断，再写报告。


## V131完成
原session89329正常结束，新seed12000–12031三方各32局全合法零截断：未训stage2.5/win0，训9.53125/win1，教师11.3125/win14。训-未训stage+7.03125 CI[6.400,7.663]，32局均改善；距教师仍显著。无训练/test调参，模型不部署。下一步自身轨迹错误/晚期失租诊断，别凭离线81%当通关能力。详见v131_model_rollout_comparison.md。


## V132
3最差既有seed12028/12007/12016模型轨迹精确复现+源码/checkpoint核验。自身155符号决策71与teacher不同，其中25soap→mouse/goldfish；64移除全一致。仅选例诊断非因果/总体估计，无训练。下一步仅原train9000–9031上收集模型轨迹teacher_action，不能用120xx或val/test训练；真实action/reward/next_state保持。详见v132_learner_state_diagnosis.md。


## V133
仅train9000–9003固定V130模型自身轨迹4局1193转移，teacher_action单独标签，全部精确回放/合法/RNG隔离，零截断；符号288中93分歧/物品37中4/移除221中9。logs/v133-magpie-corrections，0训练更新。下一步显式监督适配器+manifest/源训练seed校验，不让原reward/next_state变教师转移。详见v133_training_seed_corrections.md。


## V134
最新heartbeat要求减token/不重复遍历/不污染/聚焦工坊决策助手。已停止新增训练，实时advisor去重复评分三候选7→3调用，2新增等价/次数测试+71live通过；新本地包outputs/live-assistant-v134.zip（0.7），27载荷完整性+隔离CLI导入，无研究数据模型；未安装/上传，生产0.5不变。工坊普通入口架构阻塞仍在，不再以训练进展替代分发能力。下一步需官方受支持接入新证据。详见v134_live_scoring_optimization.md。


## V135

V138：官方询问信已获授权并由QQ邮箱确认发送（详见workshop_api_email_sent.md）。准备 integrations/workshop_probe 两个原生声明式公式样例；82个库存计数案例与既有mouse/cheese教师评分一致，2测试通过。仅离线公式验证，未安装/原生执行/上传，existing_symbol覆盖副作用未验收，Card缺口仍未解决。不修改训练数据、不重复轮询邮件。详见v138_native_formula_probe.md。

V137 定向接入核查：用户明确要求解决工坊独立接入。发现官方 value_text+var_math 可按库存动态计算，修正此前过宽判断；但本机 Card 没有 value_text/parse_var_math 路径，原生选牌评分显示仍缺接口。新增 tools/audit_workshop_candidate_display.py 与资源哈希/事实 JSON，未启动游戏、未绕过校验、未外发。最小方案收敛为原生候选评分元数据接口，非完整外部桥接；详见 v137_native_workshop_path.md。未实现或宣称工坊接入成功。

V139：将 V138 公式探针整理为官方上传器空白项目结构（SELECTME.LBAL、art/scripts/sfx），新增从当前安装包提取字段白名单和加载器合同的静态校验器；两个脚本零错误，4 项目标测试通过，含4类拒绝反例。游戏本地 mods 目录仍为0条目，未安装/运行/上传。解决本地草稿格式与当前版本静态兼容检查，Card 候选显示缺口仍在，不能称为可上架助手。详见 v139_official_uploader_skeleton.md 与 v139_workshop_probe_validation.json。

V140：按新接管要求完成Repository Audit。确认复用无动画fast_env，真实链路为GameEnv/legal_actions→Teacher/Policy→可重放Episode→分区/编码/BC/checkpoint→专用rollout；模型环境507项全通过，默认环境491通过/16个可选Torch跳过。V128语料48局17889转移，分区种子互斥，55个重复公开观测/5个跨分区/0冲突标签；无实际Reroll或SELECT_INTERACTION选择。修复批量汇总缺Std/95%CI，旧字段不变；同种子Random/Heuristic各1000局修改前后CSV哈希完全一致。平均阶段3.175/5.633，阶段CI[3.0976,3.2524]/[5.5482,5.7178]，零截断。当前三大瓶颈是完整规则后端、统一模型评估入口、数据/版本治理；本轮未训练或改环境。详见v140_repository_audit.md。

V141：V130经严格SHA/模型/编码器/词表/规则/教师/scaler/数据合同接入公共evaluate.py；512测试全通过，改造前后2739动作trace哈希一致，BC单/双进程CSV一致，V140旧基线核心字段逐局不变。instance-magpie-v1新种子15000–15127各128局：Random/Heuristic/Teacher/BC平均阶段3.219/6.609/11.609/9.633，通关0/19/57/4，全部零非法/零截断。BC−Teacher配对阶段差−1.977 CI[−2.367,−1.594]；symbol/item/remove同状态教师一致率66.26%/83.48%/97.07%，高置信错误1009。BC与教师Reroll分别7734/9690次可用均0选择；SELECT_INTERACTION均0机会。纯BC4.53 eps、平均模型决策0.794ms；诊断墙钟含昂贵教师。0训练/0数据/0规则改动，不晋升。详见v141_unified_model_evaluation.md/json及logs/v141-unified。

后续 V136：本地两个启动入口统一 Python 检测，去掉监控脚本 Codex 缓存路径默认值；ASCII JSON 处理中文路径，缺采集目录给明确提示。6 项针对性测试通过，新包 outputs/live-assistant-v136.zip 解压完整性通过（28载荷）。未安装/启动游戏/改数据，工坊接入仍受阻。详见 v136_portable_python_startup.md。下一步标准安装自动选择/旧版本回退与首次运行提示验证。
官方四页定向复核：声明式/继承说明可用，但未建立动态候选回调/只读快照/非侵入显示/工坊外部运行依赖路径。静态说明不能替代动态助手，不做降格占位发布。记录capability JSON；除build/docs/新具体证据变化，不再重复该审计。V134仍本地测试包，工坊门槛未满足。详见v135_workshop_integration_gap.md。


## 工坊阻塞复核（V135后第1次heartbeat）
无新build/API/接入示例，不重复遍历/网络审计/训练。已整理workshop_api_inquiry_draft.md，未发送。当前推进工坊独立动态助手需要官方受支持候选回调/只读状态/显示/订阅加载路径的新证据；外部依赖本地包不能替代。若后续心跳仍无新证据且无实质下一步，应按连续阻塞规则停止目标空转，而非制造微小版本消耗token。

## V142

冻结V141基线，128局BC诊断重放逐局终局/1009高置信错误hash与动作/phase计数均一致；补齐状态和全决策Teacher labels，未重跑独立Teacher benchmark。前/中/后期符号一致率69.20%/65.58%/57.82%，高置信错误515/425/69。原train符号拟合72.88%；训练支持低1002/高3/近似异标4，实际encoder exact/near/model context异标碰撞均0。错误build支持0.804，对照0.793；首错后5/10/20窗口一致率52.34%/56.38%/66.25%，未证明选择性OOD或持续错误累积。7个有限分支中4例Stage改善，随机事件分叉限制明确。

Teacher在评分前排除REROLL，原train2363次可用/0标签；6个Skip、tokens≥2、低租金压力机会重掷均验证资源/候选语义正常。SELECT_INTERACTION仍NO OPPORTUNITY。515完整测试+最终4诊断测试通过；0训练、0规则/环境/教师/Dataset改动。V143选择上游Teacher Reroll评分与机会测试，不将此缺口当成BC−Teacher差距的唯一解释，不立即DAgger/PPO。详见v142_high_confidence_error_attribution.md/json及logs/v142-diagnostics；既有seed15000–15127只做诊断，不是新holdout。

## V143

新增forecast_rents_v143教师版本，原forecast_rents源码及V128/V130/V141/V142保留。复用PreparedSymbolOffers独立公开状态抽样，旧8trial/30转预测对每符号只算一次，共享给N个新offer；E[max lexicographic(first rent,rents,cash)]减显式资源预留向量。比较zero/constant/token-aware成本，不加bonus，threshold0；8类机会及8/16/32/64收敛按预设容限选择16。522完整测试全通过，真实RNG不变/拒绝Reroll时序列一致/隐藏RNG不影响评分/旧非重掷语义兼容/cache失效合同均验证，0训练及0旧数据/规则改动，V128全部48shards hash核对。

4局Legacy控制shadow共1390决策，276机会/43正优势/0非重掷变化。新开发种子16000–16063：Legacy/V143平均Stage11.671875/12.078125，Wins31/36，reward1047.9375/1072.875；配对Stage+0.40625 CI[-0.109375,0.890625]，改善/相同/更差24/24/16，全部无截断/非法。Reroll0→125（1.953/局），立即score改善88/125；连续run1=81/run2=22，无3+，各次重新满足正优势。26次决定分量优势≤一个outer-MC SE。候选资源代理仍未验证最优，不能宣称性能提升/非劣，暂不生成新版数据。

V144选择Teacher Reroll差异案例归因/估计不确定性及机会成本校准；BC train符号拟合72.9%独立问题保留，未开始BC训练或DAgger/PPO。详见v143_teacher_reroll_value.md/json，logs/v143-reroll包含CSV、全决策gzip轨迹、协议及完整测试记录。

## V144

复用V143全轨迹，提取全部1369重掷机会（125选择/1244拒绝）；未发生新offer的立即收益留N/A。全机会8/16/32/64/128公开状态嵌套抽样重现N16原分数；128与16共15符号方向变化，选择正转负4/125，其中3个未立即改善。立即gross改善88/125，减冻结reservation后67/125；租金/现金误差分别统计，不能混成scalar。低confidence26例失败42.3%，其余99例26.3%，仅探索性。

严格前缀分析Top10 better/worse，首分歧后RNG/状态变化不作局部因果归因。冻结20经验分层状态、每current/reroll32独立终局续局；同一V143 continuation，deepcopy/独立SHA RNG，未假装CRN。另4个既有状态库存减1token各32次（原晚期2个+单独冻结最早阶段覆盖补充2个），共1408正式续局，smoke8单独存放。所有阶段差区间含0，决定租金分量n12的stage/reward相关−0.376/−0.327，未建立长期校准。少量资源probe区间均含0；无3+token或high pressure自然机会。15个经验lex桶表及全部字段/估计/CI/完整案例均保存；不把缺失字段填0或把零经验方差当精确零效果。

531完整测试0失败，421历史规则/Teacher/V128/V130/V141–143文件hash验证不变；Training Updates=0，无在线扩局/阈值/模型/规则改动。V145暂选D：有限rollout/长期价值验证，不宣称已证明短视错误；3.2%选择signflip不足以认定Sampling为主因，资源系统偏差及近零总体效果均未证实。V143继续冻结为审计参照，暂不认证新版label教师，不进入BC训练。工具tools/calibrate_reroll_value.py，报告reports/v144_reroll_value_calibration.md/json；所有诊断cache位于logs/v144-reroll-calibration，可重用，勿重跑已有实验或覆盖历史资产。


## V145

有限长期续局验证完成：冻结40状态/37原开发局，19选择与21拒绝，租金主轴36例及两个稀少轴各2例。K32正式2560完整路径，收敛额外256路径，共2816唯一终局路径；192个pilot前缀复用，无新训练/holdout。四个收敛状态K32→64终局Stage/Reward符号一致率均75%，不能据此认证最小K。独立分支RNG，不声称CRN。pilot收入字段192条从保存状态修正，0重跑；执行并发3→6不改变协议/策略/种子。

主轴局部分数与终局Stage Pearson -0.178，方向一致17/36（非零17/32）；独立两半终局Stage方向一致47.2%、相关-0.103。短期H1/H2 Stage全0，H3信号稀少；同路径H2/H3 Reward与终局符号一致60%，独立复验未显示稳定优势。全部40状态终局Stage代理TP/FP/TN/FN/Zero=8/8/9/7/8；Strong Positive六例中三例阶段点估计负，但没有区间排除0的假阳性证据。近零桶未呈错误集中，32个非零阶段案例机制归因均Unknown。资源比较同时改变候选和库存，不能独立证明成本偏差，3+token N/A。

完整543测试0失败，1937历史文件SHA不变，Training Updates=0。平均H2/终局K32双分支每状态约119/383累计模拟CPU秒，非受控墙钟基准。D：按硬停止条件冻结V143/V145，不接入rollout teacher、不训练value模型、不产生新版标签；V146转BC Optimization Audit，优先原train符号拟合72.9%已知缺口。工具tools/validate_long_horizon.py；报告reports/v145_limited_rollout_validation.md/json；协议、原始路径、独立复验与案例logs/v145-rollout，勿重复实验。


## V146

完整复现V130训练合同：32/8局、train/val3849/1111多候选、8 scalar/4 candidate/20×5 board、train-only scaler11755状态、宽16/28785参数、Adam 0.001 batch64 clip1 seed123、200更新CE、无scheduler/weight decay/early stop。冻结V130权重第200更新bitwise重现；原train Symbol2072/2843=72.88%，val578/762=75.85%，最终模型tensor异标冲突0。tiny32/128/512分别200/300/500更新100%且CE≤.05。

主预算200/500/1000/2000更新train Symbol72.88/80.27/89.94/98.70%，val75.85/76.64/76.90/73.75%，val CE在500最低0.5702、2000恶化0.9939。训练拟合的主要解释为200更新不足，但延长更新无法作为发布改进；宽16可拟合完整train，容量门槛未触发。Symbol-only500相对multi500的val差在seed123/456/789为+2.62/−0.66/−0.92pp，非稳定多任务干扰证据。按teacher目标频次分桶train head/medium/tail fit81.47/36.14/18.56%，但难度混杂。train错误771中rank2 554，rank3+217。六模块梯度均非零，scaler无零方差。

V146新增实验checkpoint全部隔离于logs/v146-bc-audit，无新teacher数据/test指标/在线对局/模型晋升；5026历史文件SHA于实验末不变，549测试0失败。V147优先预先冻结的预算/泛化控制与多种子验证，再凭离线门槛做32局smoke；Reroll继续冻结。报告reports/v146_bc_optimization_audit.md/json。


## V147

预注册5种子123/456/789/24680/13579、5更新点200/300/500/750/1000，固定V128 train/val、宽16/28785参数、Adam0.001/CE/64、train-only scaler，test指标封存。复用V146种子123/456/789的200点与部分500/1000检查点；优化器及采样序列精确续跑，500权重bitwise全3种子一致、1000种子123一致。五种子全部25点齐全；训练期间100步与750额外曲线记录。

Val Symbol Top1五种子均值200/300/500/750/1000为75.70/77.01/77.69/77.22/76.51%；Val CE0.631/0.585/0.578/0.613/0.658。500−200配对5/5改善、平均+1.994750656pp、bootstrap95%CI[+0.866,+3.123]pp；500−300仅3/5改善、区间跨0，750不稳定。训练Symbol持续上升至1000的92.17%；验证高置信错误均值17.2→67.6。CE逐种子最低位于300–600，Top1最优400–600，3/5同点。Head/medium/tail val200→1000为82.75→80.68/40.67→61.12/17.60→23.20%，tail n25，分布和难度混杂。

预注册candidate平均提升门槛≥2.000pp；500严格1.994750656pp，不得四舍五入放行。其余预算亦不合门槛；32局smoke NOT TRIGGERED，0在线/0模型晋升/0test指标。5118历史文件实验末hash不变；555完整测试0失败。V148优先预注册CE-based checkpoint选择规则并做独立于选择的验证，不修改本轮门槛，不开始Reroll/模型扩容/loss搜索。报告reports/v147_multiseed_generalization.md/json，原始分析logs/v147-generalization。


## V148

原V128 train32局按预注册SHA规则派生3组episode-level 24 FIT/8 SELECTION拆分；主拆分5训练seed，另两拆分各3seed，共11条1000-update轨迹。固定宽16/28785参数、Adam0.001/CE/batch64/clip1，保存200/300/400/500/600/750/1000。专用读取器不调用旧全corpus校验；Scaler仅以FIT全部转移拟合。训练与选择阶段未打开V128 validation；11个选择及checkpoint SHA锁定后才进行development validation审计。V148进程未打开test shard，也未读取嵌入test outcome的V128 manifest。

主拆分CE-selected updates为400/400/400/300/400（mean380, SD44.7）；三拆分11次选择均在300–500。外部development validation中CE-selected/Fixed300/Fixed500 Top1均值76.69/76.25/76.96%；CE-selected−Fixed500为−0.262pp，2胜1平2负，bootstrap95%CI[−1.129,+0.367]pp。平均regret0.866/1.312/0.604pp，CE选择未优于Fixed500。CE-selected的Val CE0.5841优于0.5991，高置信错误31.0少于42.6，错误置信度0.629低于0.658；Mean Rank1.3024略差于1.2982，故只构成soft generalization/calibration证据，预注册综合门槛FAILED。

两组次级拆分6次CE-selected−Fixed500 Top1平均+0.066pp、CE−0.0120，说明Top1收益仍受split/seed噪声影响。主selection与validation标签/候选/stage TV0.060/0.030/0.048，deck/candidate-count TV0.184/0.096；无极端标签偏移但有episode组成差异。561完整测试0失败，历史文件0变化；Online Smoke NOT APPLICABLE，0完整train refit/0模型晋升。V149不生产化early stopping；固定500作为简单诊断基线，进入单变量Regularization Audit，优先高置信错误与中长尾泛化。报告reports/v148_checkpoint_selection_audit.md/json，原始资产logs/v148-checkpoint-selection。

## V149

固定 V128 full-train、development validation、宽16/28785参数、Adam0.001/batch64/clip1与500 updates，只审计 ε=0/0.02/0.05/0.10，5个相同训练seed共20 runs。专用读取器只按显式文件名打开train9000–9031与validation10000–10007；test11000–11007及含test outcome的V128 manifest均未打开。ε=0五个seed均与V147 Fixed500权重bitwise一致，正ε实验仅在回归门槛通过后开始。

Val Symbol Top1均值为77.69/77.43/77.87/78.11%；相对基线paired平均−0.262/+0.184/+0.420pp，三个bootstrap95%CI均跨0，改善方向2/5、2/5、3/5。HC Wrong 32.6→27.6/22.0/14.2，错误置信度0.6414→0.6192/0.5988/0.5681；但统一hard CE0.5779→0.5838/0.5923/0.6172、Mean Rank1.2979→1.3029/1.3010/1.2990，ECE也恶化，说明主要是整体压低置信度而非稳定排序泛化改善。Medium探索性提高，Tail不升且n25。

三个ε均未通过预注册综合门槛；无candidate/canonical seed，32局Online Smoke NOT TRIGGERED，17000–17031未消耗，test继续SEALED。568完整测试0失败，5313历史文件hash无变化。Label Smoothing支线停止；V150进入单变量Weight Decay Audit，不细调epsilon、不组合正则。详见reports/v149_label_smoothing_audit.md/json与logs/v149-label-smoothing。
