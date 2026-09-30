from copy import deepcopy
from dataclasses import replace
import unittest
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.env.game_state import SymbolInstance
from luck_agent.env.action import Action,ActionType as T
from luck_agent.evaluation.choice_forecast import forecast_choices


class ChoiceForecastTests(unittest.TestCase):
    def fixture(self,horizon=4):
        env=GameEnv(EnvConfig(floor=1,rule_version='instance-magpie-v1'))
        state=replace(env.state,coins=0,current_rent=5,spins_until_rent=horizon,
                      symbols=(SymbolInstance('one','coin',0,None,'episode'),),
                      decision_type='symbol',candidates=('magpie','coin'))
        actions=(Action(T.PICK_SYMBOL,'magpie'),Action(T.PICK_SYMBOL,'coin'),Action(T.SKIP_SYMBOL))
        return env,state,actions

    def test_all_choices_use_same_income_units_and_horizon(self):
        env,state,actions=self.fixture()
        forecasts=forecast_choices(state,actions,env.catalog,trials=2)
        self.assertEqual([r.mean_income for r in forecasts],[9,8,4])
        self.assertEqual([r.conditional_rent_coverage for r in forecasts],[1,1,0])
        short=forecast_choices(replace(state,spins_until_rent=3),actions,env.catalog,trials=2)
        self.assertEqual([r.mean_income for r in short],[0,6,3])

    def test_public_inputs_and_live_rng_untouched(self):
        env,state,actions=self.fixture();original=deepcopy(state);rng=env._engine.rng.getstate()
        first=forecast_choices(state,actions,env.catalog,trials=3,seed=42)
        env._engine.rng.random() # Unobserved live draw must not affect forecast.
        second=forecast_choices(state,actions,env.catalog,trials=3,seed=42)
        self.assertEqual(first,second);self.assertEqual(state,original)
        env._engine.rng.setstate(rng)
        forecast_choices(state,actions,env.catalog,trials=1)
        self.assertEqual(env._engine.rng.getstate(),rng)

    def test_action_order_preserves_per_action_samples(self):
        env,state,actions=self.fixture()
        state=replace(state,symbols=tuple(SymbolInstance(str(i),'coin',0,None,'episode') for i in range(25)))
        first=forecast_choices(state,actions,env.catalog,trials=8,seed=15)
        reverse=forecast_choices(state,tuple(reversed(actions)),env.catalog,trials=8,seed=15)
        self.assertEqual({r.action:r.incomes for r in first},{r.action:r.incomes for r in reverse})

    def test_unknown_state_and_illegal_choices_reject(self):
        env,state,actions=self.fixture()
        for bad in (replace(state,supports_stable_instances=False),replace(state,items=('tax_evasion',)),
                    replace(state,symbols=(SymbolInstance('x','magpie',0,None,'episode'),)),
                    replace(state,forced_choice=True)):
            with self.assertRaises(ValueError):forecast_choices(bad,actions,env.catalog,trials=1)
        with self.assertRaises(ValueError):forecast_choices(state,(Action(T.PICK_SYMBOL,'unknown'),),env.catalog,trials=1)
