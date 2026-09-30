# Controlled timer fixture — never ship

V103 temporary real-game test based on collector 0.7. After continuing the backed-up
floor-1 save at spin 18, replaces exactly 25 reel icons with magpies and explicitly
sets their counters to zero once. Does not automate spins. The game performs its
normal shuffling and timer updates afterward. UI and every record are marked
controlled-timer-v103; fixture_applied records whether setup happened.

Two manual spins verified 20 displayed counters advance and 5 off-board counters
remain unchanged. Five previously absent instances entered on the second spin.
The original plugin and five save files were restored afterward with matching
hashes. BetterLandlord history is separate and may retain the test session.

Do not publish this DLL, use it as a production collector, or include its records
in natural coverage, win-rate statistics or training. Build fingerprints differ
from the production allowlist. See reports/v103_offboard_timer.md.
