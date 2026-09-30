# V098：补齐计时状态的采集候选版

当前游戏的喜鹊等周期符号使用 times_displayed；赌徒提醒也由该计数计算。已验证当前安装的 Slot Icon.tscn 声明 times_displayed、values、modded、inherit_effects；Item.tscn 声明后两项。仅记录属性存在和资源指纹，见 v098_collector_candidate.json，没有复制游戏源码进入发行包。

旧采集器虽有 displayed_text_value，但那是显示结果，不能据此构造权威计时状态。对 V086 的 298 条记录审计，524 次计时符号观测全部缺少上述四项，涉及 4 个实例身份；这不是 524 个独立样本。结果见 v098_timer_capture_gap.json。

新增 integrations/collector_v06 候选源代码：符号补四项、物品补来源标志，记录新增 collector_version=0.6.0，仍使用兼容的 schema 0.2。缺属性不填零、不从显示文字推导。原 0.5 源码、生产指纹和游戏安装不变。

候选 DLL 本地构建成功，0 警告、0 错误，输出 outputs/collector-v06/LandlordResearch.dll。C# 构建不验证注入 GDScript 的实机解析与字段行为，不能据此更新 verified_build.json。最新可用交付包仍是 V097 的已验证 0.5 采集器。

新增 tools/audit_timer_capture.py 检查原始字段可读性，3 项测试通过：显示文字不替代缺字段、按实例识别多个计数值、错误计数不转成零。工具本身不证明计时推进或重置正确。

下一步：有备份及回滚保障的实机短测，核对计时符号前后出场、计数推进/重置及菜单显示，结束恢复存档和生产插件。仍不开放喜鹊/赌徒建议。旧引擎避税检查依据基础负值，而当前游戏检查非前态最终值；喜鹊周期收入与避税叠加需要独立对照，不得直接迁入支持范围。
