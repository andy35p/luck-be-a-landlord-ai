"""Audit guarantees, not tests that simply mirror policy implementation."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from tools.calibrate_reroll_value import (extract_episode, boundaries, bucket,
    positive, coordinate, stats, difference, independent_clone, reconstruct,
    observations, load, OUT, verify, trace, digest)
from luck_agent.env.action import Action, ActionType as T
from luck_agent.evaluation.trajectory import normalized
from luck_agent.agents.rent_reroll_agent import sample_offers, RentRerollAgent, RentRerollConfig
from tools.evaluate_reroll_teacher import restore


class CalibrationUnitTests(unittest.TestCase):
    def test_lexicographic_units_and_empirical_buckets(self):
        self.assertFalse(positive([0,-.001,1e6]))
        self.assertTrue(positive([.001,-1e6,-1e6]))
        self.assertEqual(coordinate([0,0,2]),2)
        rows=[dict(reroll_advantage=[0,-x,100]) for x in (1,2,3,4,5,6)]
        rows += [dict(reroll_advantage=[0,0,x]) for x in (100,200,300)]
        limits=boundaries(rows)
        self.assertEqual(bucket([0,-1,100],limits),'axis1_near_zero_negative')
        self.assertEqual(bucket([0,-6,100],limits),'axis1_strong_negative')
        self.assertEqual(bucket([0,0,100],limits),'axis2_near_zero_positive')
        self.assertEqual(bucket([0,0,0],limits),'exact_zero')

    def test_component_error_and_independent_ci(self):
        r=stats([1,2,3],[0,1,2])
        self.assertAlmostEqual(r['correlation'],1)
        self.assertEqual(r['bias'],1)
        self.assertEqual(r['mae'],1)
        self.assertEqual(stats([1,1],[0,1])['correlation'],None)
        self.assertEqual(stats([],[])['n'],0)
        d=difference([dict(stage=1),dict(stage=3)], [dict(stage=3),dict(stage=5)],'stage')
        self.assertEqual(d['delta'],2)
        self.assertAlmostEqual(d['se'],2**.5)
        same=[dict(stage=13,reward=500) for _ in range(32)]
        z=difference(same,same,'stage')
        self.assertLess(z['ci95'][0],0)
        self.assertGreater(z['ci95'][1],0)
        self.assertIsNone(difference(same,same,'reward')['ci95'])

    def test_extract_rejected_offer_missing_not_zero(self):
        evidence=dict(reroll_available=True,rent_pressure=0,reroll_advantage=[0,-1,100],
                      current_best_score=[1,2,0])
        state=dict(reroll_tokens=2,symbols=[],items=[],candidates=['coin'])
        record=dict(step=0,teacher=evidence,state=state,action=normalized(Action(T.PICK_SYMBOL,'coin')))
        part=dict(success_proxy=[],row=dict(stage=5,reward=10,won=0))
        with patch('tools.calibrate_reroll_value.load',return_value=part),patch('tools.calibrate_reroll_value.trace',return_value=[record]):
            r=extract_episode(1)[0][0]
        self.assertFalse(r['did_reroll'])
        self.assertIsNone(r['immediate_realized_gain'])
        self.assertIsNone(r['new_best_score'])
        self.assertIsNone(r['new_candidates'])


class CalibrationArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OUT/'opportunities.json.gz').exists():
            raise unittest.SkipTest('V144 extraction artifacts not generated')
        cls.data=observations()

    def test_dataset_all_opportunities_and_observed_tokens(self):
        rows=[x['row'] for x in self.data]
        self.assertEqual(len(rows),1369)
        self.assertEqual(len({r['state_id'] for r in rows}),1369)
        self.assertEqual(sum(r['did_reroll'] for r in rows),125)
        for r in rows:
            self.assertEqual(positive(r['reroll_advantage']),r['did_reroll'])
            if r['did_reroll']:
                self.assertEqual(r['reroll_tokens_after'],r['reroll_tokens_before']-1)
                self.assertEqual(positive(r['immediate_realized_gain']),r['immediate_improved'])
            else:self.assertIsNone(r['immediate_realized_gain'])

    def test_public_sampling_nested_prefix_and_n16_reproduction(self):
        obj=self.data[0];s=restore(obj['state']);env,_=reconstruct(obj['row']['state_id'])
        rng=env._engine.rng.getstate();original=normalized(env.state)
        small=sample_offers(s,env.catalog,samples=16,seed=20260929)
        large=sample_offers(s,env.catalog,samples=128,seed=20260929)
        self.assertEqual(small,large[:16])
        self.assertEqual([list(x) for x in small],obj['row']['sampled_offers'])
        a=RentRerollAgent(env.catalog,config=RentRerollConfig(samples=16))
        _,e=a.decide(s,env.legal_actions())
        self.assertEqual(e['reroll_advantage'],obj['row']['reroll_advantage'])
        self.assertEqual(rng,env._engine.rng.getstate())
        self.assertEqual(original,normalized(env.state))

    def test_clone_exact_rng_isolation_and_branch_independence(self):
        sid=load(OUT/'protocol.json')['selected_state_ids'][0]
        env,_=reconstruct(sid);rng=env._engine.rng.getstate();state=normalized(env.state)
        a=independent_clone(env,sid,'current',0);b=independent_clone(env,sid,'reroll',0)
        again=independent_clone(env,sid,'current',0)
        self.assertEqual(a._engine.rng.getstate(),again._engine.rng.getstate())
        self.assertNotEqual(a._engine.rng.getstate(),b._engine.rng.getstate())
        exact=deepcopy(env)
        self.assertEqual(exact._engine.rng.getstate(),rng)
        b.step(Action(T.REROLL))
        self.assertEqual(normalized(env.state),state)
        self.assertEqual(env._engine.rng.getstate(),rng)
        self.assertEqual(normalized(a.state),state)

    def test_assets_and_continuation_protocol(self):
        self.assertGreater(verify(),100)
        p=load(OUT/'protocol.json')
        self.assertEqual(len(p['selected_state_ids']),20)
        self.assertEqual(p['continuation_samples'],32)
        self.assertEqual(p['training_updates'],0)
        self.assertEqual(p['online_episodes_added'],0)
        gate=OUT/'smoke_gate.json'
        if gate.exists():self.assertTrue(load(gate)['passed'])

    def test_sampling_sign_flip_and_bucket_counts(self):
        paths=list(OUT.glob('sampling-*.json'))
        if not paths:raise unittest.SkipTest('Sampling not yet available')
        records=load(paths[0]);grouped={}
        for r in records:grouped.setdefault(r['state_id'],{})[r['N']]=r
        for group in grouped.values():
            self.assertEqual(set(group),{8,16,32,64,128})
            for record in group.values():
                self.assertEqual(record['positive'],positive(record['advantage']))
                self.assertEqual(record['sign_flip_vs16'],record['positive']!=group[16]['positive'])
        rows=[o['row'] for o in self.data];limits=load(OUT/'protocol.json')['bucket_limits']
        self.assertEqual(sum(len([r for r in rows if r['bucket']==b]) for b in {r['bucket'] for r in rows}),1369)
        for r in rows:self.assertEqual(bucket(r['reroll_advantage'],limits),r['bucket'])

    def test_resource_addendum_is_context_based_not_outcome_selected(self):
        path=OUT/'resource_addendum.json'
        if not path.exists():raise unittest.SkipTest('No resource coverage amendment')
        amendment=load(path);protocol=load(OUT/'protocol.json')
        selected=[o['row'] for o in self.data if o['row']['state_id'] in protocol['selected_state_ids']]
        expected=[min((r for r in selected if r['reroll_tokens_before']==k),
                      key=lambda r:(r['rent_stage'],digest(r['state_id'])))['state_id'] for k in (1,2)]
        expected=[sid for sid in expected if sid not in protocol['resource_state_ids']]
        self.assertEqual(amendment['state_ids'],expected)
        self.assertEqual(amendment['continuation_samples'],32)
        self.assertTrue(set(expected).issubset(protocol['selected_state_ids']))


if __name__=='__main__':unittest.main()
