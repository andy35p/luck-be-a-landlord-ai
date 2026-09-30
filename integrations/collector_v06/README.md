# Collector 0.6 candidate

Adds raw symbol times_displayed, values, modded and inherit_effects; items also
include modded and inherit_effects. Record collector_version is 0.6.0. Additive
fields retain schema 0.2 and existing display protocol/state revision behavior.
Absent properties stay absent, never inferred from displayed reminder text.

V099 temporarily installed and verified two real spins: magpie 2→3→0, gambler
5→6→7, raw fields readable. Restored the 0.5 plugin and five save files afterward
with matching hashes. Off-board and destruction behavior remain untested. NOT
approved for the production bundle. The 0.5 fingerprint remains the baseline.
Building C# does not prove injected GDScript parses or captures correct values.

Before promotion: install with reversible backup, capture an unchanged save,
check magpie/gambler timer fields across actual spins and unseen/seen positions,
verify reset behavior and UI lifetime, then restore and compare save hashes.
Use tools/audit_timer_capture.py for field availability only; timer correctness
requires ordered before/after gameplay evidence. Do not widen adviser support
solely because the fields exist.
