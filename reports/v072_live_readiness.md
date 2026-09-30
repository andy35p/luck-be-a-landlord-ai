# V0.7.2：真实选牌观察适配与采集器 0.2

已修正普通选牌的观察条件，并构建采集器 0.2。393 项测试通过；C# 构建零错误、零警告。尚未安装新插件或实机验证其嵌入的 GDScript，尚未输出真实游戏建议。

## 判断依据

检查旧工程保留的 `work/game_scripts/Pop-up.tscn`：`_input` 以卡片存在且首张卡片 active 为入口，快捷键还检查 Options/Title 不可见以及窗口焦点。弹窗到达位置后设置卡片 active、locked_in_position。普通非 prompt 邮件并不要求 prompt_delay 为零。

这解释了旧日志中 active 卡片伴随 prompt_delay=300 的记录。旧脚本尚未与当前安装包逐字核验，因此这些条件是有源代码依据的保守观察提示，不是已经验证的完整合法动作掩码。

## 新接口

`luck_agent/evaluation/live_observation.py` 提供独立于模拟器 GameState 的只读观察转换：

- 保留候选 ID、实际观察到的跳过按钮、去除 empty 后的符号对象。
- 用会话、序号和状态内容生成 observation_id，支持未来建议与原观察绑定；当前没有实现运行时过期处理。
- 检查普通 add_tile、卡片 active、界面就位、效果结束和输入上下文。缺失关键字段会阻断 readiness_hint。
- 不推测计时器、合法动作、模型兼容性，不将动作尝试当成成功标签，recommendation 始终为 null。

## 历史数据核验

22 个历史日志文件中有 17559 条 add_tile 观察。其中 11890 条通过其余保守条件，仅缺少三个输入上下文字段；其余记录有卡片未激活或界面尚未就位等原因。所有历史记录均缺少完整 input_context，所以没有输出准备就绪或建议。计数为观察记录数，不是去重决策数。

逐文件哈希及阻断原因见 `reports/v072_readiness_audit.json`，可用 `audit_live_readiness.py` 重跑到新输出路径。

## 采集器变更与构建

从 `integrations/recovered_collector` 派生 `integrations/collector_v02`，保留旧源码。新版本增加 options_visible、title_visible、window_focused，缺失节点时不伪造 false；记录 schema 升为 0.2，插件元数据版本为 0.2.0。

使用本机 .NET SDK 9.0.317，目标 net8.0，引用已安装 SlotWeave。产物为 `logs/collector-v072/build/LandlordResearch.dll`，构建记录为 `reports/v072_build.txt`。C# 构建只是将 GDScript 作为资源嵌入，不能证明其语法、节点路径或游戏行为正确。

测试覆盖普通 prompt_delay=300、缺失上下文、动画/卡片未就绪、动作尝试拒绝、观察标识变化以及原记录不被修改。完整测试记录为 `reports/v072_tests.txt`。

## 下一步

在保留可回滚旧插件的前提下验证新采集器：启动游戏、打开设置、切换窗口焦点、进入普通选牌并跳过，核对 schema 0.2 与 readiness_hint 的变化。确认后再建立限定支持范围的建议层。当前安装插件、存档和默认策略未修改。
