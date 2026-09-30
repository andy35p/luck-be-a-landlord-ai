# V0.7.3：采集器安装与实机字段验证

采集器 0.2 已安装到本机游戏，完成一轮真实界面验证。13 项记录校验全部通过。本轮使用 computer-use 技能操作界面；没有模型参与决策，也没有发布工坊内容。

## 安装与备份

- 游戏：v1.2.24，Steam Build 16940935；SlotWeave 1.0.0。
- 安装目录：`D:/SteamLibrary/steamapps/common/Luck be a Landlord/SlotWeave/mods/LandlordResearch`。
- 已安装 DLL SHA256：`7b96f10d8eef2f36d4c8702990115eb35079823b67ed369dea134189865d0dc5`。
- 原插件备份：`logs/collector-v073/plugin-backup/`。
- 操作前 .save/.bak 文件备份：`logs/collector-v073/save-backup/`。
- 新插件保持启用。需要回滚时应先关闭游戏，再用 plugin-backup 中的 DLL 和 manifest 替换安装目录的同名文件。

## 实机过程及证据

继续原存档（一楼，旋转计数 16），旋转一次后进入选牌：三面骰、牡蛎、喜鹊，采集 ID 为 d3/oyster/magpie，与屏幕一致。金币从 8 增至 31，旋转计数变为 17。随后打开/关闭设置，切换到记事本并返回，最后点击跳过。本次测试实际推进了原存档一轮，未恢复操作前存档。

| 记录序号 | 真实界面状态 | 观察结果 |
|---|---|---|
| 1 | 标题界面 | title_visible=true，阻断 |
| 3 | 选牌界面进入中 | 卡片/位置未就绪，阻断 |
| 4 | 普通选牌稳定 | readiness_hint=true |
| 5 | 设置打开 | options_visible=true，阻断 |
| 6 | 设置关闭 | readiness_hint=true |
| 7 | 记事本获得焦点 | window_focused=false，阻断 |
| 8 | 返回游戏 | readiness_hint=true |
| 9 | 点击跳过 | action_attempt=skip，action_accepted 仍为 null |
| 10 | 选牌关闭、返回棋盘 | readiness_hint=false，候选清空 |

序号 8→10 的符号种类及数量、旋转计数和金币保持一致，提供了这一次跳过完成的后置证据；没有把其他 action_attempt 自动判定成功。

原始会话快照包含 10 条记录：`logs/collector-v073/session-snapshot.jsonl`。`verify_live_collector_v073.py` 可重跑 13 项校验，机器可读结果为 `reports/v073_live_validation.json`。此次会话末尾检查的 SlotWeave 日志显示正常加载及读取初始化，未出现新的错误行；这不是长期稳定性保证。

## 范围与下一步

已验证的是本机、本版本、一次普通选牌中的字段变化与只读阻断。未验证物品选择、删除、重掷、特殊交互、其他游戏版本或工坊安装。当前牌组和候选含模型不支持的符号，readiness_hint=true 不代表可向模型请求有效建议。

上一阶段的 393 项测试仍是代码回归基线，本轮额外完成 13 项实机记录校验。下一步将“界面已就绪”和“策略支持该状态”分开处理，建立只读建议层与状态变化后的失效机制，再验证游戏内显示。
