import copy
import unittest
from luck_agent.agents.reroll_agent import RerollConfig, RerollHeuristicAgent
from luck_agent.env.action import Action, ActionType as T
from luck_agent.env.game_env import GameEnv


class RerollTests(unittest.TestCase):
    def offer(self):
        env = GameEnv()
        env._engine.rerolls = 3
        env._offer("symbol", "symbol")
        return env

    def test_public_simulation_does_not_change_game(self):
        env = self.offer()
        state = env.state
        rng = env._engine.rng.getstate()
        before = copy.deepcopy(state)
        agent = RerollHeuristicAgent(env.catalog)
        first = agent.estimate(state)
        self.assertEqual(first, agent.estimate(state))
        self.assertEqual(rng, env._engine.rng.getstate())
        self.assertEqual(before, env.state)
        self.assertEqual(before, state)

    def test_live_random_state_cannot_change_decision(self):
        env = self.offer()
        agent = RerollHeuristicAgent(env.catalog)
        first = agent.choose(env.state, env.legal_actions())
        evidence = agent.last_evidence
        env._engine.rng.seed(998877)
        self.assertEqual(first, agent.choose(env.state, env.legal_actions()))
        self.assertEqual(evidence, agent.last_evidence)

    def test_no_resource_no_sampling(self):
        env = GameEnv()
        env._offer("symbol", "symbol")
        agent = RerollHeuristicAgent(env.catalog)
        self.assertNotEqual(agent.choose(env.state, env.legal_actions()), Action(T.REROLL))
        self.assertIsNone(agent.last_evidence)

    def test_poor_offer_rerolls_good_offer_kept(self):
        env = self.offer()
        env.catalog["symbol_pool"] = ["coin"]
        env.catalog["symbol_values"]["coin"] = 10
        env._options = ("dud",)
        agent = RerollHeuristicAgent(env.catalog)
        self.assertEqual(agent.choose(env.state, env.legal_actions()), Action(T.REROLL))
        env._options = ("coin",)
        self.assertNotEqual(agent.choose(env.state, env.legal_actions()), Action(T.REROLL))

    def test_invalid_config(self):
        with self.assertRaises(ValueError):
            RerollConfig(trials=1)
