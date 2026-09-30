# Collector 0.2 source candidate

Recovered LandlordResearch source with additive input_context fields: options_visible,
title_visible and window_focused. Missing UI nodes leave fields absent, not false.
Uses record schema 0.2. Retains the original assembly ID and patch sentinel because this
is a replacement candidate, not a second simultaneously loaded collector.

Installed and smoke-tested in V073 on game v1.2.24 / build 16940935.
Original installed DLL is backed up in logs/collector-v073/plugin-backup.
See reports/v073_live_validation.md for the limited real-game validation scope.
Do not interpret successful Python reader tests as proof of GDScript or game compatibility.
Built successfully with SDK 9.0.317 targeting net8.0 and the installed SlotWeave reference.
Build output is in logs/collector-v072/build; this does not validate embedded GDScript syntax.
Then verify on a controlled game session before deployment, including opening Options,
losing focus, normal symbol selection and skip; no automated game actions are provided.
