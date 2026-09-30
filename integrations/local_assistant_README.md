# 幸运房东只读助手：本地测试包

这是本地测试包，尚未发布到 Steam 创意工坊。默认使用受限启发式建议，不含训练模型或自动操作。

实时建议默认拒绝带 test_fixture 或 fixture_applied 标记的受控测试记录，并撤回旧建议；即使标记值为空或 false 也拒绝。仅离线回归代码可显式启用测试输入，普通启动器不提供该开关。测试插件不得替代生产采集器。

当前策略 restricted_heuristic_v3 支持一楼、无永久加成的普通符号选择。库存和候选必须全部属于：硬币、珍珠、樱桃、花、猫、老鼠、奶酪、牛奶、金鱼、蓝宝石、沙钱。物品允许为空，或各一份状态完整且数值符合已核验规则的鸡蛋盒、避税；它们在此符号范围内不改变启发式选牌评分。其他物品、重复物品、其他符号、删除/重转/物品选择和特殊交互仍显示“暂不建议”。沙钱的移除奖励不在本策略的动作范围内。这是规则启发式评分，未经完整局胜率验证。新增物品兼容已通过离线测试，尚未完成对应自然局实机验收。

需要 Windows、Python 3.11+、游戏，以及已单独安装的兼容 SlotWeave/.NET 运行环境。包内不附带游戏、字体、SlotWeave、Python、用户存档或采集日志。

具体采集器版本见 package_manifest.json 的 collector_version。0.7 增加原始计时、规则来源和显式棋盘实例矩阵，沿用显示协议；新增字段不意味着建议策略已经支持更多符号。0.5 包继续保留供回退。两版均属于有限实测的本地测试包。

读取 0.7 记录时，建议器核验 20 个唯一棋盘实例均存在于库存，并要求符号/物品的 modded 与 inherit_effects 明确为 false。缺字段、未知版本或规则来源不明确会停止建议；版本字符串本身不是身份认证。旧 0.5 记录维持原兼容范围，无法提供同等规则来源证据。

1. 解压到一个可写目录。先关闭游戏，备份现有 LandlordResearch 插件目录。
2. 将包内 `collector` 下的 DLL 和 manifest.json 复制到已有游戏安装的 `SlotWeave/mods/LandlordResearch`。这一步不是工坊订阅安装，不能替代加载器安装。
3. 启动游戏后，在包目录执行 `./start_live_assistant.ps1`，默认观察 5 分钟并显示建议。
4. 如自动寻找 Python 不成功，可传入 `-PythonPath '完整的/python.exe路径'`；时长使用 `-Minutes 1` 到 `-Minutes 60`。
5. 诊断写入包内 run-logs。退出后助手提示离线；恢复插件时应先关闭游戏，再还原此前备份。

Python 与 Windows 看到的采集目录不同会停止启动，不绕过该检查。界面出现“暂不建议”意味着局面超出当前支持范围。游戏内显示依赖 collector 0.5 的显示协议；只更新其中一侧可能无法显示。

`package_manifest.json` 列出包内文件的 SHA256；只含已实机验证的生产 DLL，构建工具会拒绝其他指纹。相同输入生成相同 ZIP，不包含开发缓存、日志、测试改牌插件或模型权重。文件哈希用于完整性核对，不是发布者数字签名。

启动器会先校验包内文件；也可执行 `python verify_live_bundle.py 包目录` 单独核对。缺失、修改或多出的非运行文件会导致失败，避免把旧版本文件混入新包。原始 ZIP 请保存在解压目录外。

此包尚未通过独立干净电脑的安装验收。请勿把本机隔离目录启动测试解释为全新系统或 Steam 工坊兼容性证明。

## 可选安装与回滚工具

已有 SlotWeave 时，可用工具替代手工复制。先关闭游戏，然后在包目录执行只读预检：

```powershell
python manage_live_install.py install --game 'D:/SteamLibrary/steamapps/common/Luck be a Landlord'
```

核对目标后加 `--apply` 执行。原插件整个目录保存在游戏 `SlotWeave/research-backups/唯一编号/previous`，新增版本保留原有其他配置。返回的 receipt.json 是本次操作凭据。工具不修改存档、不安装 SlotWeave、不上传工坊。

回滚同样先预检，再加 `--apply`：

```powershell
python manage_live_install.py rollback --game 'D:/SteamLibrary/steamapps/common/Luck be a Landlord' --receipt '本次返回的完整receipt.json路径'
```

回滚会把新插件归档到 removed-install，再恢复旧目录；首次安装则只归档新增目录。安装后文件被修改或原备份哈希不符时停止，避免覆盖后续编辑。若进程或电脑在文件切换间异常终止，需检查凭据及 previous/staged/removed-install；目前不承诺断电自动恢复。

同一游戏目录的安装和回滚通过系统文件锁互斥，进程结束会释放锁。发现未完成的 prepared 凭据时拒绝再次安装，保留现场；请勿删除凭据来强行重试。

对未完成事务可用 `inspect --game 游戏目录 --receipt 凭据路径` 只读判断阶段；`recover` 默认也只读。只有字节哈希和目录状态能唯一对应到切换前、旧目录已归档或新目录已就位时，`recover ... --apply` 才恢复到安装前状态。冲突会拒绝自动恢复。恢复后的新版本或暂存文件仍保留供排查。这里验证的是文件切换中断模拟，不能保证硬件损坏或文件系统损坏后的恢复。

回滚也会在切换前写入 rollback_prepared；恢复过程中写入 recovering。再次中断后，可用同一凭据重新 inspect/recover，继续回到原安装状态。不要通过手工改凭据状态跳过哈希核验。
