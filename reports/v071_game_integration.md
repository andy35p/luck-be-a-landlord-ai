# V0.7.1：真实游戏接入勘察

已找到并复用旧工程采集器，而不是从零设计接入。现有日志证明真实游戏状态采集路径曾运行；本轮没有完成建议生成、游戏内显示或工坊订阅安装，不能宣称接入闭环已打通。

## 本机证据

- Steam 游戏安装目录：`D:/SteamLibrary/steamapps/common/Luck be a Landlord`，安装清单 Build ID 为 16940935。
- 已安装 SlotWeave 1.0.0、LandlordResearch 0.1.0、BetterLandlord 1.2.7。运行日志显示两个插件均已加载。
- 旧工程源码：`C:/Users/14489/Documents/Codex/2026-09-13/w/outputs/LandlordResearch`。已复制其五个源文件到本项目 `integrations/recovered_collector/`，保留原代码。
- 已安装采集器 DLL 与旧工程 `work/collector_build/LandlordResearch.dll` SHA256 一致：`1fe19431d60b1d14843822fa7820f98e9e8fa8a6bddfcad3a85709c76804fd67`。这是二进制一致性证据，本轮未重新构建核验源码与二进制的对应关系。
- 旧工程 README 与 `选牌实机验证.json` 记录了两次人工选牌验证：螃蟹、钥匙。本轮仅检查历史证据，未重新操作游戏。

## 日志审计

本轮读取时目录中的 22 个 JSONL 文件，共 65820 条记录，其中 12134 条为动作尝试，49853 条包含空位。第 20 层记录 42371 条，其余覆盖 1–19 层。逐文件哈希及计数保存在 `v071_collector_audit.json`。这些是记录数，不是独立决策数或游戏局数。

采集器包含经济、租金数组、资源、符号对象、物品、候选卡、提示、按钮和可见棋盘。符号数组含 `empty`，不能直接把数组长度作为牌组大小；对象 ID 仅限本次会话；`action_attempt` 发生在处理入口，`action_accepted` 为 null，不能当成成功动作标签。动画中间状态也被记录。

审计脚本采用待验证的严格观察条件：候选全部 active、选牌提示、界面打开、动画停止且两个延时字段均为 0。满足条件的记录为 0。进一步检查发现，候选全部 active 的选牌观察中，常见组合是 `delay_timer=-2,prompt_delay=300`（9392 条），其次为 `delay_timer=0,prompt_delay=300`（2498 条）。这说明不能仅凭字段名称将 prompt_delay 解释成倒计时。0 不代表没有真实选牌点；此条件不是合法动作掩码，必须从游戏逻辑与实机对照确认。

当前受限 goldfish 模型只支持一楼及部分符号/物品，不能将这些原版高楼层状态直接送入模型，或把缺失字段补 0 后伪装成可支持状态。

## 发布路径判断

官方文档描述的是内容模组及游戏随附的 Mod Uploader；SlotWeave 的安装方式要求游戏目录中的代理 DLL、框架目录和 .NET 8 Desktop Runtime。现有采集器属于后者。当前没有证据证明“只订阅工坊即可安装并运行本助手”。

参考来源：

- [官方入门教程](https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/Tutorial-1.1%3A-Getting-Started)
- [官方模组变量](https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/Modding-Variables)
- [SlotWeave 项目说明与安装方式](https://github.com/Piraeus42/SlotWeave)

## 下一步验收

1. 复用采集器，核对 add_tile 界面的 active、delay_timer、prompt_delay 与按钮可点击条件，建立有依据的稳定决策事件。
2. 在受支持的一楼局面建立只读适配：显式区分真实游戏观测与训练 GameState，不支持的符号、物品、计时及状态缺口返回原因。
3. 先输出建议，再验证游戏内提示。真实建议需要绑定会话与决策标识，状态变化后作废。
4. 单独验证官方模组路径是否满足显示需求；若依赖 SlotWeave，发布说明必须写明额外安装步骤，不能称为工坊一键版。

390 项测试通过。新增审计测试验证缺失关键字段不会误报准备就绪、空位计数与楼层/符号范围阻断。游戏安装、存档和已有插件均未修改，本轮未新增训练。
