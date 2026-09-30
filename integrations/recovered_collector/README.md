# LandlordResearch 0.1

本地课程项目的独立采集扩展，依赖已安装的 SlotWeave。源码为本项目编写。构建：`dotnet build -c Release`，可用 `-p:GamePath=游戏路径` 指定框架位置。将 DLL 和 manifest.json 放到 SlotWeave/mods/LandlordResearch 后重启游戏。

## 已验证

游戏v1.2.24、Steam Build 16940935，SlotWeave v1.0.0与BetterLandlord v1.2.7。

实机通过两次符号选择：螃蟹、钥匙。选择请求前分别记录5和10金币，租金剩余[25,4]和[25,3]，三项候选准确；随后同一旋转内对应库存数量各增加1。机器可读证据见上级目录“选牌实机验证.json”。这些为界面测试操作，不是模型输出。

## 数据

游戏用户数据目录下 landlordResearch/*.jsonl。每250毫秒检查一次变化，记录observation；resolve_event入口记录action_attempt。状态含经济、进度、资源、符号实例、可见棋盘、物品、提示、候选卡和按钮。

action_attempt不等于动作成功：action_accepted保留null。两条实机样本通过后续同回合库存变化单独核验，没有把全部请求默认标为成功。

instance_id是引擎对象标识，只能在本次会话内使用，不能跨重启视为稳定身份。symbols包含后台空位，不能用数组长度当作有效牌数；visible_grid关联当前格子的实例。缺失字段表示未采到，不应替换成0。

## 边界

这仍是采集原型：动画期间也会记录，未保证每条observation都是稳定决策点。只验证了普通选牌；重掷、删牌、物品选择及特殊交互尚未完整验证。物品/精华不代表所有内部效果状态均已覆盖。没有训练器、自动动作接口、通关能力或第20层验证。

当前扩展只读取状态和写独立日志，不替换游戏结算。要停用，在关闭游戏后将本模组目录移出SlotWeave/mods，保留日志即可。
