# Collector 0.7 candidate

Based on 0.6; captures displayed_board width, height and row-major instance IDs
from the game's displayed_icons array. Missing slots are null, not invented IDs.
Full reels.icons capture remains unchanged. Schema 0.2 adds this optional field.

V102 temporarily installed: two board layouts matched the screen across one
spin, 20 displayed IDs mapped to 25 inventory IDs; five off-board IDs were empty.
The plugin and saves were restored with matching hashes. Nonempty off-board
timers were subsequently verified in the separate V103 controlled fixture.
V105 verified live unsupported-state display and offline transition. V106 ships
an explicit 0.7 local-test bundle and verified actual 0.5→0.7→0.5 install/rollback.
verified_build.json names the tested normal DLL; rebuilding requires revalidation.
Current machine installation was restored to 0.5. This is not Workshop validation.
Before promotion, verify rows map to the observed 5×4 board and IDs belong to the
full inventory, including a run with nonempty off-board symbols. Check transitions
only after effects settle. Do not infer membership from stale grid_position.
