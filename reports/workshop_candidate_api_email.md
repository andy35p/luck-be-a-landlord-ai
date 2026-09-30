# 候选卡片动态评分接口询问（待授权，未发送）

拟收件人：contact@TrampolineTales.com

地址来源：https://trampolinetales.com/lbal/presskit

Subject: Workshop API question: read-only dynamic scores on symbol selection cards

Hi Dan,

I'm developing a read-only decision assistant for Luck be a Landlord, with the goal of running entirely through a normal Steam Workshop subscription, without an external loader or Python installation.

Your documentation describes dynamic value_text using var_math, including inventory-based variables such as symbols_in_inventory. Is there a supported way to display such an expression on a symbol selection card before the player picks it?

For a minimal example, the displayed score for a Milk candidate would change when the number of Cats in the inventory changes. The score would be a separate advisory value, not the symbol's payout. It must leave symbol identity, effects, rarity, RNG and existing reminder text unchanged.

Our static inspection of the installed Windows build suggests that owned-symbol reminders evaluate value_text, while selection cards use description and values without evaluating value_text. We have not verified this with a native Workshop runtime example, so we may be missing a supported route.

Could you point us to an existing API or minimal example? If this is not currently supported, would a separate declarative candidate-score field, evaluated read-only when cards refresh, be a feasible addition? Deterministic arithmetic and read-only inventory counts would be enough for an initial prototype; arbitrary script execution or file access would not be needed.

Documentation consulted:
https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/Tutorial-1.6:-Value-Text
https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/var_math
https://github.com/TrampolineTales/LBAL-Modding-Docs/wiki/Comparisons

Thank you for your guidance.

---

发送范围：仅上述英文正文，不附游戏源码、存档、模型、研究数据或本地日志。此文件不是已发送邮件记录。
