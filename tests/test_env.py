import copy
import hashlib
import json
import unittest
from luck_agent.env.action import Action, ActionType as T
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.rule_engine import DATA
from luck_agent.agents.random_agent import RandomAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.evaluation.evaluator import evaluate


class AdapterTests(unittest.TestCase):
    def test_preserved_core(self):
        provenance = json.loads((DATA/"provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256((DATA/"fast_env.py").read_bytes()).hexdigest(), provenance["core_sha256"])

    def test_reads_are_pure(self):
        env = GameEnv()
        before = copy.deepcopy(env._engine.__dict__)
        rng = env._engine.rng.getstate()
        for _ in range(3):
            _ = env.state
            _ = env.action_mask((Action(T.SPIN), Action(T.PICK_SYMBOL, "cat")))
        self.assertEqual(rng, env._engine.rng.getstate())
        self.assertEqual(before["deck"], env._engine.deck)
        self.assertEqual(before["pending_shown"], env._engine.pending_shown)

    def test_mask_illegal_atomic(self):
        env = GameEnv()
        state = env.state
        self.assertEqual(env.action_mask((Action(T.SPIN), Action(T.PICK_SYMBOL, "cat"))), (True, False))
        with self.assertRaises(ValueError):
            env.step(Action(T.PICK_SYMBOL, "cat"))
        self.assertEqual(state, env.state)
        with self.assertRaises(ValueError):
            env.step(Action(T.SPIN, secondary_target_id="cat"))

    def test_state_detached_no_rng(self):
        env = GameEnv()
        state = env.state
        self.assertNotIn("seed", state.effect_state)
        self.assertNotIn("rng", state.effect_state)
        state.effect_state["deck"].clear()
        self.assertTrue(env._engine.deck)

    def test_reset_reproducible(self):
        env = GameEnv()
        s = env.reset(34)
        actions = []
        agent = RandomAgent(1)
        for _ in range(5):
            a = agent.choose(s, env.legal_actions())
            actions.append(a)
            s = env.step(a)[0]
        env.reset(34)
        for a in actions:
            actual = env.step(a)[0]
        self.assertEqual(s, actual)

    def test_reward_components_and_rent(self):
        env = GameEnv()
        e = env._engine
        e.coins = 100
        e.spins_left = 1
        _, reward, _, _, info = env.step(Action(T.SPIN))
        self.assertEqual(info["rents_paid"], 1)
        self.assertEqual(reward, info["coin_delta"]+20)

    def test_forced_mask(self):
        env = GameEnv()
        env._engine.force_add_next_choice = True
        env._offer("symbol", "symbol")
        self.assertNotIn(Action(T.SKIP_SYMBOL), env.legal_actions())
        a = env.legal_actions()[0]
        self.assertIn(a.target_id, env.state.candidates)
        env.step(a)

    def test_position_no_secret_preview(self):
        env = GameEnv()
        self.assertEqual(env.state.visible_board, ())
        env._engine.items.append("swapping_device")
        s = env.step(Action(T.SPIN))[0]
        self.assertEqual(s.decision_type, "position")
        self.assertTrue(s.visible_board)
        self.assertTrue(env.action_mask(env.legal_actions())[0])
        env.step(Action(T.SELECT_INTERACTION, "skip"))
        self.assertIsNone(env.state.effect_state["pending_shown"])

    def test_truncation(self):
        env = GameEnv(EnvConfig(max_decisions=1))
        s, _, done, truncated, _ = env.step(Action(T.SPIN))
        self.assertTrue(truncated)
        self.assertFalse(done)
        self.assertEqual(env.legal_actions(), ())

    def test_batches_reproduce(self):
        for mode in ("random", "heuristic"):
            a, _ = evaluate(10, mode, 0, EnvConfig())
            b, _ = evaluate(10, mode, 0, EnvConfig())
            self.assertEqual(a, b)
            self.assertFalse(any(r["truncated"] for r in a))

    def test_terminal_reward(self):
        env = GameEnv()
        env._engine.coins = -1000
        env._engine.spins_left = 1
        s, reward, done, _, info = env.step(Action(T.SPIN))
        self.assertTrue(done)
        self.assertEqual(reward, info["coin_delta"]-100)
        self.assertFalse(env.legal_actions())

    def test_item_and_essence_queues(self):
        env = GameEnv()
        env._engine.pending_essence_choices = 1
        env._after_interactions()
        self.assertEqual(env.state.decision_type, "essence")
        env.step(env.legal_actions()[0])
        self.assertEqual(env._engine.pending_essence_choices, 0)
        self.assertEqual(len(env.state.essences), 1)
        env._engine.pending_item_choices = 2
        env._after_remove()
        env.step(env.legal_actions()[0])
        self.assertEqual(env.state.decision_type, "item")
        env.step(Action(T.SKIP_ITEM))
        self.assertEqual(env.state.decision_type, "spin")

    def test_removal_and_reroll_budget(self):
        env = GameEnv()
        env._engine.removals = 1
        env._phase = "remove"
        n = len(env.state.symbols)
        env.step(Action(T.REMOVE_SYMBOL, "coin:0"))
        self.assertEqual(len(env.state.symbols), n-1)
        self.assertEqual(env.state.removal_tokens, 0)
        env._engine.rerolls = 1
        env._offer("symbol", "symbol")
        env.step(Action(T.REROLL))
        self.assertNotIn(Action(T.REROLL), env.legal_actions())

    def test_rent_rescue_is_a_decision(self):
        env = GameEnv()
        env._engine.coins = 0
        env._engine.spins_left = 1
        env._engine.items.append("coffee")
        state = env.step(Action(T.SPIN))[0]
        self.assertFalse(state.is_terminal)
        self.assertIn(Action(T.SELECT_INTERACTION, "use:coffee"), env.legal_actions())
        env.step(Action(T.SELECT_INTERACTION, "use:coffee"))
        self.assertEqual(env.state.spins_until_rent, 1)
        env.step(Action(T.KEEP_OPTIONS))
        self.assertEqual(env.state.decision_type, "symbol")

    def test_win_reward_exactly_once(self):
        env = GameEnv()
        env._engine.rent_index = 12
        env._engine.coins = 10000
        env._engine.spins_left = 1
        s, reward, done, _, info = env.step(Action(T.SPIN))
        self.assertTrue(done and s.won)
        self.assertEqual(reward, info["coin_delta"] + 20 + 500)
        with self.assertRaises(ValueError):
            env.step(Action(T.SPIN))


if __name__ == "__main__":
    unittest.main()
