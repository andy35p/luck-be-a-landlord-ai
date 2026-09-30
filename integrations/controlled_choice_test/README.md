# TEST ONLY: controlled-choice-v080

Temporary test build derived from production collector 0.5. Replaces the saved
candidate types at ordinary first-floor add_cards: spin 1 cheese/coin/flower;
later spins mouse/milk/flower. The game creates and resolves its normal cards.
Inventory, scoring, scoring policy and selection handlers are not replaced.

On-screen prefix 【受控测试】 and every record's test_fixture explicitly identify
the modified candidate distribution. This is integration validation, not natural
rollout evaluation or evidence of policy quality. Never train on these traces.

Install only with the game closed and plugin/save backups, then restore both after
testing. Never publish this DLL as the normal collector. No automated selection.
