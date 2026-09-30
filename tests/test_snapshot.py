from collections import Counter
from copy import deepcopy
from dataclasses import fields
import unittest
from luck_agent.env.snapshot import copy_public_value
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType


class SnapshotTests(unittest.TestCase):
    def test_flat_values_preserve_types_and_isolation(self):
        for value in ([1,'a',None], {'a':1}, Counter({'a':2}), [], {}, Counter()):
            expected = deepcopy(value)
            actual = copy_public_value(value)
            self.assertEqual(actual,deepcopy(value))
            self.assertIs(type(actual),type(value))
            self.assertIsNot(actual,value)
            actual.clear()
            self.assertEqual(value,expected)
        self.assertEqual(copy_public_value(Counter())['missing'],0)

    def test_nested_aliases_and_cycles_keep_deepcopy_semantics(self):
        shared = [1]
        value = {'a':shared,'b':shared,'counter':Counter({'x':2})}
        actual = copy_public_value(value)
        self.assertEqual(actual,deepcopy(value))
        self.assertIs(actual['a'],actual['b'])
        actual['a'].append(2)
        self.assertEqual(shared,[1])
        cycle=[];cycle.append(cycle)
        copied=copy_public_value(cycle)
        self.assertIs(copied[0],copied)
        self.assertIsNot(copied,cycle)

    def test_public_state_matches_deepcopy_and_remains_isolated(self):
        for version in ('legacy','instance-goldfish-v1'):
            env=GameEnv(EnvConfig(floor=1,rule_version=version));e=env._engine
            e.essence_lifetimes=[{'name':'fixture','nested':[1]}]
            e.matryoshka_ttls={'fixture':[3]}
            rng=e.rng.getstate()
            state=env.state
            expected={f.name:deepcopy(getattr(e,f.name)) for f in fields(e)
                      if f.name not in {'catalog','seed','pending_shown'}}
            expected['pending_shown']=None
            self.assertEqual(state.effect_state,expected)
            state.effect_state['essence_lifetimes'][0]['nested'].append(2)
            state.effect_state['matryoshka_ttls']['fixture'].clear()
            state.effect_state['display_counts']['fake']=99
            state.effect_state['deck'].clear()
            self.assertEqual(env.state.effect_state,expected)
            self.assertEqual(e.rng.getstate(),rng)

    def test_prior_snapshot_survives_future_steps(self):
        env=GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1'))
        state=env.state; expected=deepcopy(state)
        env.step(Action(ActionType.SPIN))
        self.assertEqual(state,expected)
