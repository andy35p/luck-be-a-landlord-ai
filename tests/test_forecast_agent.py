import unittest
from dataclasses import replace
from luck_agent.agents.forecast_agent import ForecastAgent
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.game_state import SymbolInstance
from luck_agent.env.action import Action, ActionType as T


class ForecastAgentTests(unittest.TestCase):
    def test_horizon_changes_choice_and_order_does_not(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-magpie-v1"))
        agent = ForecastAgent(env.catalog, trials=2)
        state = replace(env.state, symbols=(SymbolInstance("a","coin",0,None,"episode"),),
                        decision_type="symbol", candidates=("magpie","coin"), spins_until_rent=4)
        actions = (Action(T.PICK_SYMBOL,"magpie"), Action(T.PICK_SYMBOL,"coin"), Action(T.SKIP_SYMBOL))
        self.assertEqual(agent.choose(state,actions), actions[0])
        self.assertEqual(agent.choose(state,tuple(reversed(actions))), actions[0])
        self.assertEqual(agent.choose(replace(state,spins_until_rent=3),actions), actions[1])

    def test_exact_tie_prefers_skip(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-magpie-v1"))
        state = replace(env.state, symbols=tuple(SymbolInstance(str(i),"coin",0,None,"episode") for i in range(25)),
                        decision_type="symbol", candidates=("coin",), spins_until_rent=2)
        self.assertEqual(ForecastAgent(env.catalog,trials=2).choose(state,
            (Action(T.PICK_SYMBOL,"coin"),Action(T.SKIP_SYMBOL))), Action(T.SKIP_SYMBOL))

    def test_wrong_domain_rejected(self):
        with self.assertRaises(ValueError): ForecastAgent(GameEnv().catalog)

