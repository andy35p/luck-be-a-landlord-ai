# V136 本地启动运行时检测

两个 PowerShell 入口统一使用 resolve_live_python.ps1，不再默认引用 Codex 缓存中的 Python。自动依次检查 py、python；版本不足或探测失败时继续后备，跳过 Windows Store 安装别名。显式路径不存在或版本不足时给出具体错误。

路径探测通过 ASCII JSON 传输，避免中文安装路径受到终端编码影响。首次运行缺少采集目录时提示安装采集插件并启动游戏。

验证：3 项真实 PowerShell 子进程测试（显式路径、无效路径、空 PATH）和 3 项打包测试全部通过。测试运行于本机 pwsh；未验证独立干净电脑、Windows PowerShell 5.1 或自动检测的所有安装组合。

新包 outputs/live-assistant-v136.zip，28 个载荷文件及 manifest，collector 0.7。临时目录解压完整性核验通过，无额外文件。

SHA256: ba3913de1e0e8a4a7a0302049d34b7894d6e3d6f57935683121ccef9843ad5ba

未安装新包、未启动游戏、未修改存档或训练数据。依旧是本地测试包；工坊独立接入阻塞未解决。下一步验证标准 Python 安装下的自动选择、旧版本回退和首次运行提示；不要重复模型训练来替代发布验收。
