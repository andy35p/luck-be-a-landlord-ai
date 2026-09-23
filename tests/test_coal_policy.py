import unittest
from types import SimpleNamespace
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType as T


class CoalPolicyTests(unittest.TestCase):
    def test_only_coal_score_changes_and_default_matches_prior(self):
        from luck_agent.legacy.fast_env import HeuristicAgent as Prior
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))
        base = HeuristicAgent(env.catalog); candidate = HeuristicAgent(env.catalog, coal_score_adjustment=-1.2)
        view = SimpleNamespace(catalog=env.catalog, deck=env._engine.deck,
            items=[], coins=0, state=lambda: {"rent": 25})
        for symbol in env.catalog["symbol_pool"]:
            a = base.prior.score_symbol(view, symbol)
            self.assertEqual(a, Prior().score_symbol(view, symbol))
            self.assertAlmostEqual(candidate.prior.score_symbol(view, symbol)-a, -1.2 if symbol == "coal" else 0)

    def test_selection_changes_but_removal_does_not(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))
        base = HeuristicAgent(env.catalog); candidate = HeuristicAgent(env.catalog, coal_score_adjustment=-1.2)
        env._phase = "symbol"; env._options = ("coal", "coin", "flower")
        self.assertEqual(base.choose(env.state, env.legal_actions()), Action(T.PICK_SYMBOL, "coal"))
        self.assertEqual(candidate.choose(env.state, env.legal_actions()), Action(T.PICK_SYMBOL, "coin"))
        env._engine.choose("coal"); env._engine.removals = 1; env._phase = "remove"
        self.assertEqual(base.choose(env.state, env.legal_actions()), candidate.choose(env.state, env.legal_actions()))

    def test_invalid_adjustment_rejected(self):
        with self.assertRaises(ValueError): HeuristicAgent(coal_score_adjustment=float("nan"))
