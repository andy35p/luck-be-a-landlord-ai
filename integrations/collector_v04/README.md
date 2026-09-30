# Collector 0.4: display-only prototype

Adds a mouse-transparent Label in a CanvasLayer. Reads user://landlordResearch/advice.json.
The sidecar contains text/status/identity, no executable game action. Rejects wrong
session, wrong sequence and expired timestamps. Local loss of focus pauses display.

Installed build is under logs/collector-v077/build; previous 0.3 plugin backup is
logs/collector-v077/plugin-backup. Start the Python consumer with:

    .\watch_live_advice.ps1 -Display -Seconds 300

Current UI uses small English prototype text. Heartbeat sequence changes can briefly
show Waiting for current state until the consumer catches up. Model-generated
recommendations and Workshop-only installation are not implemented.
