# V108：喜鹊从同类合并计数迁为逐实例周期

旧引擎对同类型符号累计 display_counts，再按除以周期的次数发奖励。该实现会把多只新喜鹊的出场合并：25 只全新喜鹊、固定 20 只出场、无物品的合成对照中，旧引擎收入 +25，新逐实例规则为 -20。差额 45 来自旧规则提前发出五次周期奖励。复现结果见 v108_legacy_magpie_difference.json；旧源码保持不变。

新增 instance-magpie-v1，在既有 InstanceGoldfishEngine 上扩展：每只喜鹊独立持有距下次奖励的 remaining_appearances（1..4）；只对出场实例递减，到期奖励 +9 并重置为 4，保留身份、不销毁。状态、动作、候选、租金、随机种子及既有符号规则继续复用。通过 configs/instance_magpie_v1.json 显式选择，新旧规则版本不会暗中替换。

边界：未支持避税或方格旗组合，不推断完整游戏 EV。V103 实机轨迹用于核对 25 个实例的出场/未出场计数，不用于对照无物品环境的整盘收入；V099 单实例轨迹用于核对到期重置。基础 -1、周期 +9 的实现依据既有目录和已审计游戏规则。尚没有这个新环境与完整实机对局逐步等价的证明。

5 项新引擎测试通过：多只新喜鹊不共享周期、部分到期与场外保持、受控实机身份轨迹重放、自然单实例到期轨迹、旧范围和未支持物品拒绝。阶段全量 471 项测试通过；随后补规则身份登记及 1 项轨迹往返测试，规则版本相关 4 项通过，未再次运行全量。新版本轨迹必须有显式 rule_identity，缺失即拒绝，避免被旧版本读取为相同语义。

首轮评估曾因缺少规则版本登记而拒绝输出，补齐后重新成功运行。以下只引用成功输出：随机与原启发式各 100 局、相同种子 0..99，均无截断。

| 策略 | 平均通过租金 | 平均旋转 | 胜率 |
|---|---:|---:|---:|
| 随机 | 3.36 | 25.35 | 0% |
| 原启发式 | 6.51 | 49.25 | 18% |

这些是受限新环境的运行检查，不是与旧环境的因果比较或真实游戏胜率。成功输出分别在 logs/v108-random/random-20260926T160056401828Z 与 logs/v108-heuristic/heuristic-20260926T160057419214Z。main.py 单局入口也已跑到 GAME OVER。

复现命令：

```powershell
python main.py --agent random --seed 0 --config configs/instance_magpie_v1.json
python evaluate.py --agent random --games 100 --config configs/instance_magpie_v1.json --output logs/magpie-random
python evaluate.py --agent heuristic --games 100 --config configs/instance_magpie_v1.json --output logs/magpie-heuristic
```

原启发式对喜鹊仍评分 -2，不代表正确考虑周期回报。本轮未修改教师、模型或训练数据，也未将喜鹊加入实时建议白名单。下一步应单独比较周期感知评分与原教师，结合租金前剩余出场机会，不能仅用长期平均 1.25 替代短期风险。游戏安装和存档未改，最新实时助手包仍 V107。
