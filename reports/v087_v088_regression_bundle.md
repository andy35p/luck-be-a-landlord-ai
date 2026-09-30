# V087–V088：离线回归与本地测试包

从 V080/V085/V086 的本地日志投影出 10 个固定样本，保留决策、经济和必要校验字段，移除无关数据；会话及实例标识改为离线别名，原日志 SHA256 和原序号保留用于溯源。受控正向样本明确标记，不能用于自然局统计或训练。

新增 6 项实机样本回归测试，覆盖历史记录默认拒绝、受控正向选择、交租/失败/物品字段、状态切换撤回及历史文件注入拒绝。样本位于 `tests/fixtures/live_records.json`，无需运行游戏或访问用户 AppData 即可复现。

本地包 `outputs/live-assistant-v088.zip` 使用固定 22 文件白名单构建，另附 package_manifest.json。不包含原始采集日志、存档、模型、游戏资产、受控插件、Python 或 SlotWeave。生产 DLL 指纹必须等于已实测基线。相同输入生成字节一致的 ZIP，既有输出不会覆盖。

新启动器 start_live_assistant.ps1 从普通 Python 安装寻找运行时，也允许显式指定完整路径；无需依赖 Codex 缓存路径。仍需用户本机已有 Python 3.11+ 及游戏/加载器。包已解压到独立临时目录，忽略 Python 环境变量和用户 site-packages，成功启动并正常完成短时空源观察。此验证不等于干净系统安装或实机包验收。

新增 2 项打包测试验证可重现性、白名单、内容哈希、拒绝未知 DLL 和不匹配 manifest。构建命令：

```powershell
python tools/build_live_bundle.py --collector-dll logs/collector-v078/build/LandlordResearch.dll --output outputs/live-assistant-new.zip
```

本地包仅供测试，未上传或发布。安装说明在包内 README.md。
