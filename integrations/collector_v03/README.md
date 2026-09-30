# Collector 0.3 candidate

Additive schema 0.2: captured_unix_seconds records local wall time. Unchanged
observations are emitted about once per second with new sequence/ticks, allowing
the read-only consumer to distinguish a live stationary screen from a stopped game.
State changes retain the existing 250 ms polling behavior.

This increases log volume. Installed and live-validated in V076 on build 16940935;
the previous plugin and saves are backed up in logs/collector-v076. Static ordinary
selection heartbeat and stopping the game were tested. See reports/live_feed.md.
