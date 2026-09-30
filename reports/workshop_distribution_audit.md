# 工坊分发路径核查（2026-09-26）

当前 collector 不能直接视为官方工坊模组：它是 .NET DLL，通过 SlotWeave 向 Main/Pop-up 的 GDScript 注入采集和显示代码。只将现有 ZIP 上传工坊不能证明会被游戏加载。

官方文档列出的 API 支持符号、物品、邮件、合同条款、楼层和现有符号/物品修改；未在该能力列表中提供任意 .NET DLL 的安装入口。[官方 API 首页](https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki)

官方上传流程使用游戏目录内的 Mod Uploader 创建模组目录，再编辑模组内容并上传。该流程与当前的外部加载器目录不同。[官方入门教程](https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/Tutorial-1.1:-Getting-Started)

SlotWeave 项目说明要求在游戏程序旁安装 winmm.dll 和 SlotWeave 目录，模组放入 SlotWeave/mods，并需要 .NET 8 Desktop Runtime。这是外部依赖，不能假定工坊订阅会代为安装。[SlotWeave 安装说明](https://github.com/Piraeus42/SlotWeave#installation)

据此作出的工程判断：当前可交付物应保持“本地只读助手测试包”。若要实现仅订阅工坊即可使用，应单独验证官方 GDScript 模组生命周期能否承载只读采集/显示、外部建议计算如何启动，以及是否需要把受限启发式移入 GDScript。上述文档不足以证明这种替代架构一定可行或不可行。

下一步先做只读源码/官方模板可行性分析，不向工坊发布占位内容，不以引导手工安装外部加载器冒充工坊独立运行。现有训练环境和原 collector 保留，迁移只针对实机接入层。

## V095：本机实际加载器核查

只读检查已安装游戏 PCK 内的 Main 场景，未修改或导出其源码。结果见 v095_mod_surface.json，可由 tools/audit_local_mod_surface.py 重算。当前场景具有两处模组校验调用，函数调用许可列表为空，仅对 `_init` 声明提供特殊处理，同时拒绝非声明字段赋值。现有轮询、文件读写和动态 Label 创建不属于该普通声明式入口的支持用法。

这把“尚未确认可直接迁移”缩小为明确的当前架构阻塞：不能直接把 collector.gd 改名放入官方工坊脚本目录。此结论限定于本机当前实现与已观察校验入口，不宣称所有未来官方 API 都不可行。未研究或尝试绕过校验。

旧恢复场景与当前安装场景的原始文件哈希不一致，因此此次结论使用当前 PCK 直接读取的校验事实，而非依赖旧副本。报告只保存哈希与布尔事实，不把游戏源码加入本地分发包。

后续路线：继续提升独立本地助手的实际支持范围和使用体验；工坊独立运行门槛仍保留，须等待或找到官方支持的接入能力，不能用“外部加载器+工坊说明页”冒充已达成该目标。
