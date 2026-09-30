import unittest
from dataclasses import replace
from luck_agent.agents.rent_forecast_agent import RentForecastAgent,rent_rank
from luck_agent.evaluation.rent_forecast import RentForecast,RentTrial
from luck_agent.env.action import Action,ActionType as T
from luck_agent.env.game_env import GameEnv,EnvConfig


class RentForecastAgentTests(unittest.TestCase):
    def test_coal_selected_with_sufficient_reserves(self):
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-magpie-v1"))
        state=replace(env.state,coins=10000,symbols=(),decision_type="symbol",candidates=("coal","coin"))
        actions=(Action(T.PICK_SYMBOL,"coal"),Action(T.PICK_SYMBOL,"coin"),Action(T.SKIP_SYMBOL))
        agent=RentForecastAgent(env.catalog,trials=1)
        self.assertEqual(agent.choose(state,actions),actions[0])
        self.assertEqual(agent.choose(state,tuple(reversed(actions))),actions[0])
        # Current rent needs five coins: coal cannot defer this payment.
        self.assertEqual(agent.choose(replace(state,coins=20),actions),actions[1])

    def test_current_survival_precedes_long_term_mean(self):
        safe=RentForecast(Action(T.SKIP_SYMBOL),(RentTrial(25,0,1,5,False,False,True),)*2)
        risk=RentForecast(Action(T.PICK_SYMBOL,"coal"),(
            RentTrial(1000,1000,6,30,False,False,True),RentTrial(0,0,0,5,True,False,False)))
        self.assertLess(rent_rank(safe),rent_rank(risk))

    def test_short_policy_horizon_rejected(self):
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-magpie-v1"))
        with self.assertRaises(ValueError):RentForecastAgent(env.catalog,horizon=9)
