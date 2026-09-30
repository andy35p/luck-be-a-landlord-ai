# V105–V106：显示兼容与真实升级回滚

V105 临时安装 0.7 正常采集器，沿用原自然存档，运行现有实时消费者。30.109 秒观察正常完成：屏幕确认“暂不建议：当前符号或物品尚未支持”，结束后确认“建议助手已离线”。另一次菜单观察 20.125 秒正常完成，日志明确拒绝 input_context_options_visible。菜单截图晚于观察结束，因此没有声称已视觉验证暂停文字。没有正向选牌建议、模型效果或长时间稳定性结论。

两次事件日志均 duration_completed，未因游戏退出或异常中止。关闭游戏后恢复 2 个插件文件和 5 个存档/设置，7 项哈希匹配。证据位于 logs/collector-v105。BetterLandlord 历史数据库不在恢复范围。

V106 为打包工具增加明确的 0.5.0/0.7.0 版本选项，默认保留 0.5；每版 DLL 指纹、manifest 和版本必须配对。未知路径/版本和混合二进制拒绝。新增 1 项版本隔离测试，构建相关共 3 项通过。check_live_install.ps1 同步支持明确版本核验。

0.7 基线指纹 D93A347B4A7128F76E0125057D241E6732FEB6A4161259255D13D204ADB2ED63，来自 V102 的自然棋盘实测与 V105 显示兼容实测；V103 为单独受控边界证据，不将其测试 DLL 作为生产指纹。基线限定本地测试，并非工坊或全部策略认证。

交付包 outputs/live-assistant-v106.zip，25 个文件加清单，SHA256：7068bba10bc821f20f10e3e4477ab2faf86e033cee67126b05dca93dc7254fa7。实际解压完整性核验通过。使用包内安装器在真实游戏目录执行 0.5→0.7，再回滚至 0.5；新版检查通过，回滚后含存档恢复比对的 12 项自检通过。未启动游戏参与这次安装事务。

事务凭据：D:/SteamLibrary/steamapps/common/Luck be a Landlord/SlotWeave/research-backups/f637bb80f1254b07a06f790c9c6da540/receipt.json。证据见 logs/collector-v106/install-result.json、installed-check.json、rollback-result.json、restored-check.json。

当前实机仍为 0.5；V104 的 0.5 包保留，V106 提供 0.7 包。仍不是干净电脑验收或 Steam 创意工坊可直接订阅安装。新增采集字段不扩大建议白名单，工坊原生分发限制继续按 V095 结论处理。
