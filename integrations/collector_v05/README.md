# Collector 0.5

Uses the game's existing NotoSansSC-Regular.otf for Chinese display. Sidecar schema 2
matches session and state_revision instead of heartbeat sequence. Revision increments
when captured state changes or an action attempt occurs; stationary heartbeats retain
their revision. Timestamps and local focus checks remain required.

Installed and smoke-tested on build 16940935. Previous plugin is backed up under
logs/collector-v078/plugin-backup. See reports/live_display.md for scope and results.
