import unittest
from copy import deepcopy
from types import MethodType
from unittest.mock import patch
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.agents.random_agent import RandomAgent


class ConsumptionCacheTests(unittest.TestCase):
    def test_complete_random_episodes_equal_uncached_reference(self):
        for seed in range(5):
            env=GameEnv(EnvConfig(floor=1,rule_version="instance-magpie-v1"));env.reset(seed)
            reference=deepcopy(env)
            reference._engine._plan_for_spin=MethodType(lambda self,shown:self.consumption_plan(shown),reference._engine)
            agent=RandomAgent(seed+1000)
            while not (env.state.is_terminal or env.state.is_truncated):
                self.assertEqual(env.state,reference.state)
                self.assertEqual(env.legal_actions(),reference.legal_actions())
                action=agent.choose(env.state,env.legal_actions())
                self.assertEqual(env.step(action),reference.step(action))
                self.assertEqual(env._engine.rng.getstate(),reference._engine.rng.getstate())
            self.assertEqual(env.state,reference.state)

    def test_single_compute_and_exception_cleanup(self):
        engine=GameEnv(EnvConfig(floor=1,rule_version="instance-magpie-v1"))._engine
        with patch.object(engine,'consumption_plan',wraps=engine.consumption_plan) as plan:
            engine.spin()
            self.assertEqual(plan.call_count,1)
        self.assertIsNone(engine._consumption_cache)
        self.assertFalse(engine._consumption_cache_active)
        with patch.object(engine,'_resolve_instances',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):engine.spin()
        self.assertIsNone(engine._consumption_cache)
        self.assertFalse(engine._consumption_cache_active)
        # Independent calls must never reuse a previous spin's plan.
        with patch.object(engine,'consumption_plan',wraps=engine.consumption_plan) as plan:
            shown=engine.instances.snapshot()
            engine._plan_for_spin(shown);engine._plan_for_spin(shown)
            self.assertEqual(plan.call_count,2)
