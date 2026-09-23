import unittest
from dataclasses import replace
from random import Random
from luck_agent.agents.baselines import Agent
from luck_agent.env.action_space import Action, ActionType as T
from luck_agent.env.game_env import Config, GameEnv
from luck_agent.env.simulator import adjacent, resolve
from luck_agent.env.state_encoder import Symbol, encode
from luck_agent.evaluation.evaluator import episode
from luck_agent.knowledge import Knowledge


class RulesTests(unittest.TestCase):
    def payout(self, kinds, board=None, items=(), seed=0):
        deck = tuple(Symbol(i, k) for i, k in enumerate(kinds))
        return resolve(deck, tuple(range(len(deck))) if board is None else board, items, Knowledge(), Random(seed), 3)

    def test_base_and_item(self):
        self.assertEqual(self.payout(["coin", "flower"], items=("purse", "garden"))[0], 5)

    def test_adjacency(self):
        self.assertFalse(adjacent(2, 3, 3))
        self.assertTrue(adjacent(0, 3, 3))
        self.assertEqual(self.payout(["bee", "flower"])[0], 4)
        self.assertEqual(self.payout(["bee", "flower"], (0, None, None, None, None, 1))[0], 2)

    def test_destroy_only_once(self):
        income, deck, board, events = self.payout(["eater", "fruit", "eater"])
        self.assertEqual(income, 9)
        self.assertEqual([s.kind for s in deck], ["eater", "eater"])
        self.assertIsNone(board[1])
        self.assertEqual(len(events), 1)

    def test_transform_no_same_spin_payout(self):
        income, deck, _, _ = self.payout(["seed"], seed=1)
        self.assertEqual(income, 0)
        self.assertEqual(deck[0], Symbol(0, "flower"))

    def test_rent_success_and_failure(self):
        env = GameEnv(Config(rents=(4,), spins_per_rent=1))
        state, reward, done, _, info = env.step(Action(T.SPIN))
        self.assertTrue(done and state.won)
        self.assertEqual((state.coins, reward, info["rent_paid"]), (0, 1, 4))
        env = GameEnv(Config(rents=(5,), spins_per_rent=1))
        self.assertEqual(env.step(Action(T.SPIN))[1], -1)

    def test_mask_and_illegal_atomic(self):
        env = GameEnv()
        before = env.state
        with self.assertRaises(ValueError):
            env.step(Action(T.PICK_SYMBOL, 0))
        self.assertEqual(before, env.state)
        self.assertFalse(env.action_mask((Action(T.SPECIAL_ACTION), Action(T.SPIN, parameter=1)))[0])
        self.assertFalse(env.action_mask((Action(T.SPIN, parameter=1),))[0])
        env.step(Action(T.SPIN))
        self.assertNotIn(Action(T.SPIN), env.legal_actions())
        self.assertFalse(env.action_mask((Action(T.PICK_SYMBOL, 99),))[0])

    def test_resource_exhaustion(self):
        env = GameEnv()
        env.step(Action(T.REMOVE_SYMBOL, 0))
        env.step(Action(T.REMOVE_SYMBOL, 1))
        self.assertFalse(env.action_mask((Action(T.REMOVE_SYMBOL, 2),))[0])
        env.step(Action(T.SPIN))
        env.step(Action(T.REROLL))
        env.step(Action(T.REROLL))
        self.assertNotIn(Action(T.REROLL), env.legal_actions())

    def test_terminal_mask(self):
        env = GameEnv(Config(rents=(1,), spins_per_rent=1))
        env.step(Action(T.SPIN))
        self.assertFalse(any(env.action_mask()))

    def test_shaping_telescopes(self):
        env = GameEnv(Config(rents=(999,), spins_per_rent=2, reward_mode="shaped", gamma=0.9))
        total, discount = 0., 1.
        while not env.state.terminated:
            action = Action(T.SPIN if env.state.phase == "spin" else T.SKIP_SYMBOL)
            _, reward, _, _, _ = env.step(action)
            total += discount * reward
            if not env.state.terminated:
                discount *= 0.9
        self.assertAlmostEqual(total, -discount)

    def test_no_hidden_state(self):
        self.assertNotIn("rng", str(encode(GameEnv().state)))
        self.assertNotIn("seed", str(encode(GameEnv().state)))

    def test_reproducible_and_agent_legal(self):
        for mode in ("random", "greedy", "heuristic"):
            variant = {"name": mode, "mode": mode, "synergy_weight": 1.0}
            for seed in range(10):
                self.assertEqual(episode(Config(), variant, seed), episode(Config(), variant, seed))

    def test_item_phase_and_uid(self):
        env = GameEnv(Config(rents=(1, 100), spins_per_rent=1))
        env.step(Action(T.SPIN))
        self.assertEqual(env.state.phase, "item")
        env.step(Action(T.PICK_ITEM, 0))
        self.assertEqual(env.state.items, ("purse",))
        env.step(Action(T.PICK_SYMBOL, 0))
        self.assertEqual(len({s.uid for s in env.state.deck}), len(env.state.deck))


if __name__ == "__main__":
    unittest.main()
