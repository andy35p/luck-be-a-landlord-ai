# V139 官方上传器本地骨架与安装版静态校验

## 结果

已将 V138 的 Mouse/Cheese 原生公式探针整理为官方 `LBAL Mod Uploader`
创建空白模组时采用的目录结构：

```text
integrations/workshop_probe/package/
├── SELECTME.LBAL
├── art/
├── scripts/
│   ├── cheese.gd
│   └── mouse.gd
└── sfx/
```

`SELECTME.LBAL` 为空文件，只供上传器选择本地目录；没有创建
`workshop_info.json` 或临时 `-upload` 目录，也没有执行 Steam 上传。

## 校验

新增 `tools/validate_workshop_probe.py`。它直接读取本机已安装游戏包中的
`Main.tscn`，提取 `base_mod_fields` 字段白名单，并确认加载器校验逻辑仍符合
本探针支持的合同，再检查目录、载荷和两个脚本。

- 安装版 `Main.tscn` SHA-256：
  `8fc8547be296d731a504ad42fa3241443a79d7ba12827731063d1ca43957400a`
- 两个脚本：零静态错误。
- 4 项针对性测试通过。
- 反例覆盖：任意函数调用、未知赋值、未闭合引号、混合制表符/空格。
- 游戏本地 `mods` 目录条目数：0；没有安装到正式游戏环境。

机器可读结果见 `reports/v139_workshop_probe_validation.json`。

## 边界

这一步解决了“上传器能选择的本地草稿格式”和“当前安装版会静态拒绝哪些
脚本”两个工程问题，但没有解决选牌卡片显示。V137 已确认当前 `Card` 路径不
读取 `value_text`，因此该探针仍只能作为向开发者复现接口缺口的最小材料，
不能当作可上架的完整决策助手。`existing_symbol` 的覆盖副作用也必须等受支持
接口或隔离实机验证后再验收。

下一步保持停止训练和数据扩增，等待开发者接口答复；若得到支持路径，再在
隔离配置中进行原生加载、候选显示、规则/RNG 不变性和订阅安装验收。
