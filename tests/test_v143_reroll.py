from copy import deepcopy
from dataclasses import replace
import random
import unittest
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.env.action import Action,ActionType as T
from luck_agent.agents.rent_forecast_agent import RentForecastAgent
from luck_agent.agents.rent_reroll_agent import (RentRerollAgent,RentRerollConfig,
                                                sample_offers,token_cost)


class V143RerollTests(unittest.TestCase):
    def setUp(self):
        self.env=GameEnv(EnvConfig(floor=1,rule_version='instance-magpie-v1'))
        self.env.reset(143000)
        self.state,*_=self.env.step(Action(T.SPIN))
        legacy=RentForecastAgent(self.env.catalog)
        while self.state.decision_type!='symbol':
            self.state,*_=self.env.step(legacy.choose(self.state,self.env.legal_actions()))

    def test_legal_and_invalid_phases(self):
        self.assertIn(Action(T.REROLL),self.env.legal_actions()) if self.state.reroll_tokens else None
        with self.assertRaises(ValueError):
            sample_offers(replace(self.state,reroll_tokens=0),self.env.catalog,samples=8,seed=1)
        with self.assertRaises(ValueError):
            sample_offers(replace(self.state,decision_type='item'),self.env.catalog,samples=8,seed=1)
        self.assertNotIn(Action(T.REROLL),GameEnv(self.env.config).legal_actions())

    def test_sampling_prefix_reproducibility_and_distribution_scope(self):
        state=replace(self.state,reroll_tokens=3)
        small=sample_offers(state,self.env.catalog,samples=8,seed=42)
        large=sample_offers(state,self.env.catalog,samples=64,seed=42)
        self.assertEqual(small,large[:8])
        self.assertTrue(all(len(set(s))==len(s)==3 for s in large))
        self.assertTrue(all(self.env.catalog['symbol_rarity'][x]=='common' for s in large for x in s))
        self.assertNotEqual(small,sample_offers(state,self.env.catalog,samples=8,seed=43))

    def test_resource_cost_models_and_reservation_direction(self):
        state=replace(self.state,reroll_tokens=1)
        self.assertEqual(token_cost(state,RentRerollConfig(cost_model='zero')),(0.,0.,0.))
        self.assertEqual(token_cost(state,RentRerollConfig(cost_model='constant')),(0.,.125,1.))
        one=token_cost(state,RentRerollConfig())
        many=token_cost(replace(state,reroll_tokens=4),RentRerollConfig())
        self.assertTrue(all(b<=a for a,b in zip(one,many)))
        self.assertEqual(token_cost(replace(state,rent_stage=12),RentRerollConfig()),(0.,0.,0.))
        with self.assertRaises(ValueError):RentRerollConfig(cost_model='bonus')

    def test_rng_isolation_no_leakage_and_rejected_reroll_real_sequence(self):
        # Reservoir inventory normally starts at zero; add resources equally to
        # both test environments, not to production rules.
        self.env._engine.rerolls=2;state=self.env.state;control=deepcopy(self.env)
        policy=RentRerollAgent(self.env.catalog,config=RentRerollConfig(samples=8,cost_model='constant',base_cost=(1,1000,1000)))
        before=self.env._engine.rng.getstate();global_before=random.getstate()
        action,evidence=policy.decide(state,self.env.legal_actions())
        self.assertEqual(before,self.env._engine.rng.getstate())
        self.assertEqual(global_before,random.getstate())
        self.assertNotEqual(action.action_type,T.REROLL)
        legacy=RentForecastAgent(self.env.catalog)
        self.assertEqual(action,legacy.choose(state,control.legal_actions()))
        self.assertEqual(self.env.step(action),control.step(action))
        for _ in range(8):
            if self.env.state.is_terminal:break
            a=legacy.choose(self.env.state,self.env.legal_actions())
            self.assertEqual(self.env.step(a),control.step(a))
        # Hidden RNG mutation does not affect scores on the same public state.
        self.env._engine.rng.seed(999999)
        second,again=policy.decide(state,tuple(Action(T.PICK_SYMBOL,s) for s in state.candidates)+(Action(T.SKIP_SYMBOL),Action(T.REROLL)))
        self.assertEqual(action,second);self.assertEqual(evidence['reroll_score'],again['reroll_score'])

    def test_non_reroll_compatibility_and_trace(self):
        legacy=RentForecastAgent(self.env.catalog);policy=RentRerollAgent(self.env.catalog)
        self.assertEqual(legacy.choose(self.state,self.env.legal_actions()),policy.choose(self.state,self.env.legal_actions()))
        state=replace(self.state,reroll_tokens=2)
        actions=tuple(Action(T.PICK_SYMBOL,s) for s in state.candidates)+(Action(T.SKIP_SYMBOL),Action(T.REROLL))
        a,trace=policy.decide(state,actions);b,other=policy.decide(state,actions)
        self.assertEqual(a,b);self.assertEqual(trace['reroll_advantage'],other['reroll_advantage'])
        self.assertIn(a,actions);self.assertEqual(len(trace['sampled_offers']),16)
        self.assertEqual(trace['sample_count'],16)
        self.assertEqual(trace['reroll_score'],[x-y for x,y in zip(trace['expected_best_after_reroll'],trace['resource_cost'])])
        # Any successive reroll must reevaluate updated candidates and tokens.
        changed=replace(state,reroll_tokens=1,candidates=('coin','flower','cat'))
        aa=tuple(Action(T.PICK_SYMBOL,s) for s in changed.candidates)+(Action(T.SKIP_SYMBOL),Action(T.REROLL))
        _,updated=policy.decide(changed,aa)
        self.assertEqual(updated['reroll_tokens'],1)
        self.assertEqual(updated['current_candidates'],['coin','flower','cat'])
        self.assertNotEqual(trace['resource_cost'],updated['resource_cost'])

    def test_cache_does_not_hide_economy_or_catalog_changes(self):
        from unittest.mock import patch
        from luck_agent.evaluation.rent_forecast import forecast_rents
        policy=RentRerollAgent(deepcopy(self.env.catalog))
        state=replace(self.state,reroll_tokens=2)
        with patch('luck_agent.agents.rent_reroll_agent.forecast_rents',wraps=forecast_rents) as forecast:
            first=policy.candidate_values(state)
            self.assertIs(first,policy.candidate_values(replace(state,reroll_tokens=1,candidates=('coin','cat','flower'))))
            policy.candidate_values(replace(state,coins=state.coins+1))
            policy.catalog['symbol_values']['coin']+=1
            self.assertIsNot(first,policy.candidate_values(state))
            self.assertEqual(forecast.call_count,3)
