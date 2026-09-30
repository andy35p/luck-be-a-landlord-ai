# 原生动态评分最小样例（未安装、未实机验证）

`package/` 按官方 Mod Uploader 的空白项目格式组织：根目录含
`SELECTME.LBAL`，并含 `art/`、`scripts/`、`sfx/` 三个目录。两个脚本使用
官方 existing_symbol、value_text、var_math 声明语法，复用既有启发式的
Mouse/Cheese 评分：

- Mouse：1 + 1.8 × 库存 Cheese 数量。
- Cheese：1 + 1.5 × 库存 Mouse 数量。

样例不包含 Python、DLL、外部调用或游戏源码。描述明确区分启发式评分与金币收益。没有增加效果、设置稀有度或改写基础收益；继承标志仅表达保留原行为的意图，不等于已证明运行时无影响。

**用途仅为开发接入探针。** 当前只定位到已入库符号的 reminder 支持此表达式；选牌卡片显示未接通。该样例不是可发布的决策助手，不含 Workshop 上传清单，也没有通过原生加载器/干净系统测试。`SELECTME.LBAL` 只是上传器的本地选择标记，不表示已上传。

existing_symbol 仍会使符号成为模组覆盖，可能影响符号 ID、其他模组兼容或成就。因此不得把这两个脚本装入用户正式存档，也不能声称完整规则无变化。后续只在隔离测试环境使用，比较加载前后规则、候选、收益和 RNG；最终产品优先采用单独候选评分元数据入口。

本地测试核对表达式和既有评分函数等价，并从当前安装包提取字段白名单，按已安装加载器对本样例所用语法进行静态校验。它不替代 Godot 解析、原生游戏执行或 Steam 订阅验收。

官方依据：
- https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/Tutorial-1.6:-Value-Text
- https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/var_math
- https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/Comparisons
