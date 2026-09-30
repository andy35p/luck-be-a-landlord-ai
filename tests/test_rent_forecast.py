import unittest
from dataclasses import replace
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.game_state import SymbolInstance
from luck_agent.env.action import Action,ActionType as T
from luck_agent.evaluation.rent_forecast import forecast_rents


class RentForecastTests(unittest.TestCase):
    def fixture(self):
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-magpie-v1"))
        state=replace(env.state,coins=10000,symbols=(),decision_type="symbol",candidates=("coal",),
                      rent_stage=0,current_rent=25,spins_until_rent=5)
        return env,state,(Action(T.PICK_SYMBOL,"coal"),Action(T.SKIP_SYMBOL))

    def test_coal_matures_only_after_twenty_appearances(self):
        env,state,actions=self.fixture()
        short=forecast_rents(state,actions,env.catalog,horizon=20,trials=1)
        long=forecast_rents(state,actions,env.catalog,horizon=21,trials=1)
        self.assertEqual(short[0].trials[0].income,0)
        self.assertEqual(long[0].trials[0].income,5)
        self.assertEqual(long[1].trials[0].income,0)
        self.assertEqual(long[0].trials[0].cash,10000-25-50-100+5)
        self.assertEqual(long[0].trials[0].rents_paid,3)

    def test_no_post_death_maturity_income(self):
        env,state,actions=self.fixture()
        result=forecast_rents(replace(state,coins=0),actions,env.catalog,horizon=30,trials=1)[0].trials[0]
        self.assertTrue(result.died)
        self.assertEqual((result.spins,result.income,result.rents_paid),(5,0,0))

    def test_time_machine_and_final_win_stop(self):
        env,state,actions=self.fixture()
        accelerated=forecast_rents(replace(state,items=("time_machine",)),actions,env.catalog,horizon=16,trials=1)[0].trials[0]
        self.assertEqual(accelerated.income,5)
        last=replace(state,rent_stage=12,current_rent=1000,spins_until_rent=1)
        result=forecast_rents(last,actions,env.catalog,horizon=30,trials=1)[0].trials[0]
        self.assertEqual((result.spins,result.cash),(1,9000))
        self.assertTrue(result.won)
        self.assertFalse(result.died)

    def test_schedule_mismatch_and_rng_isolation(self):
        env,state,actions=self.fixture();rng=env._engine.rng.getstate()
        first=forecast_rents(state,actions,env.catalog,trials=2,seed=77)
        self.assertEqual(env._engine.rng.getstate(),rng)
        self.assertEqual(first,forecast_rents(state,actions,env.catalog,trials=2,seed=77))
        with self.assertRaises(ValueError):
            forecast_rents(replace(state,current_rent=26),actions,env.catalog)
