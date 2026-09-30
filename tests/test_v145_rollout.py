from copy import deepcopy
from types import SimpleNamespace
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import unittest
from tools.validate_long_horizon import (OUT,load,parent,fork_env,reached,walk,
    delta_stats,relationships,rank,classify,aggregate,frozen_check)
from tools.validate_long_horizon import reproducibility_probe
from luck_agent.env.game_env import GameEnv
from luck_agent.env.action import Action,ActionType as T
from luck_agent.evaluation.trajectory import normalized
from tools.evaluate_reroll_teacher import ENV
from luck_agent.agents.rent_reroll_agent import RentRerollAgent


class SimplePolicy:
    def choose(self,state,actions):
        for typ in (T.KEEP_OPTIONS,T.SKIP_SYMBOL,T.SKIP_ITEM,T.SPIN):
            choice=next((a for a in actions if a.action_type==typ),None)
            if choice:return choice
        return actions[0]


class RolloutUnitTests(unittest.TestCase):
    def test_horizon_boundary_and_terminal_absorption(self):
        s=SimpleNamespace(rent_stage=6,is_terminal=False,is_truncated=False)
        self.assertTrue(reached(s,5,1));self.assertFalse(reached(s,5,2))
        self.assertFalse(reached(s,5,'end'))
        s.is_terminal=True
        self.assertTrue(all(reached(s,5,h) for h in (1,2,3,'end')))
        s.is_terminal=False;s.rent_stage=13
        self.assertTrue(reached(s,12,3))

    def test_actual_rent_payment_cut_and_reward_accounting(self):
        env=GameEnv(ENV);env.reset(145000)
        env._engine.coins=10000;env._engine.spins_left=1
        initial=env.state
        acc,cuts,trace,elapsed=walk(env,Action(T.SPIN),SimplePolicy(),1)
        self.assertEqual(env.state.rent_stage,1)
        self.assertEqual(set(cuts),{'1'})
        self.assertFalse(cuts['1']['terminal'])
        self.assertEqual(cuts['1']['stage_gain'],1)
        self.assertEqual(cuts['1']['rent_survival'],1)
        self.assertIsNone(cuts['1']['final_stage'])
        self.assertIsNone(cuts['1']['win'])
        self.assertEqual(cuts['1']['spin_income'],sum(env._recent))
        self.assertEqual(acc['reward'],env.state.coins-initial.coins+20)
        self.assertGreaterEqual(cuts['1']['decisions'],1)

    def test_final_rent_terminal_and_no_double_payment(self):
        env=GameEnv(ENV);env.reset(145000)
        env._engine.rent_index=12;env._engine.coins=10000;env._engine.spins_left=1
        acc,cuts,_,_=walk(env,Action(T.SPIN),SimplePolicy(),'end')
        self.assertTrue(env.state.is_terminal)
        self.assertEqual(set(cuts),{'1','2','3','end'})
        self.assertTrue(all(m['win']==1 and m['stage_gain']==1 for m in cuts.values()))
        reward=acc['reward']
        empty,again,_,_=walk(env,None,SimplePolicy(),'end')
        self.assertEqual(empty['reward'],0)
        self.assertEqual(again['end']['reward_gain'],0)
        self.assertEqual(reward,env.state.coins-10000+20+500)

    def test_resume_same_path_exactness(self):
        base=GameEnv(ENV);base.reset(145000)
        base._engine.coins=10000;base._engine.rent_index=10;base._engine.spins_left=1
        full=deepcopy(base);partial=deepcopy(base)
        a,c1,_,_=walk(full,Action(T.SPIN),SimplePolicy(),'end')
        b,c2,traces,elapsed=walk(partial,Action(T.SPIN),SimplePolicy(),1)
        c,c3,_,_=walk(partial,None,SimplePolicy(),'end',b,c2,elapsed,base.state,traces)
        self.assertEqual(normalized(full.state),normalized(partial.state))
        self.assertEqual(full._engine.rng.getstate(),partial._engine.rng.getstate())
        self.assertEqual(a,c)
        for key in c1:
            left={k:v for k,v in c1[key].items() if k!='elapsed_seconds'}
            right={k:v for k,v in c3[key].items() if k!='elapsed_seconds'}
            self.assertEqual(left,right)

    def test_sign_classification_ties(self):
        self.assertEqual(classify(1,1),'TRUE POSITIVE PROXY')
        self.assertEqual(classify(1,-1),'FALSE POSITIVE PROXY')
        self.assertEqual(classify(-1,1),'FALSE NEGATIVE PROXY')
        self.assertEqual(classify(-1,-1),'TRUE NEGATIVE PROXY')
        self.assertEqual(classify(1,0),'ZERO LONG-TERM PROXY')

    def test_tie_aware_spearman_and_sign_metrics(self):
        self.assertEqual(rank([2,1,2,3]),[1.5,0.,1.5,3.])
        r=relationships([-2,-1,1,2],[-4,-2,2,4])
        self.assertAlmostEqual(r['pearson'],1)
        self.assertAlmostEqual(r['spearman'],1)
        self.assertEqual(r['sign_agreement'],1)
        self.assertIsNone(relationships([1,2],[2,1])['pearson'])

    def test_rollout_metric_aggregation_independent_errors(self):
        rows=[]
        for h in (1,2,3,'end'):
            for branch,offset in [('current',0),('reroll',1)]:
                for i in range(8):
                    rows.append(dict(state_id='x',horizon=h,branch=branch,continuation_id=i,
                        stage_gain=i%2+offset,reward_gain=i+offset,net_coins_gained=i,
                        rent_survival=i%2,future_reroll_opportunities=i,tokens_after=1))
        result=aggregate(rows,['x'],8)
        self.assertEqual(len(result),4)
        self.assertTrue(all(r['stage_gain']['delta']==1 for r in result))
        self.assertIn('2.365',result[0]['stage_gain']['ci_method'])
        z=delta_stats([dict(stage_gain=1)]*8,[dict(stage_gain=1)]*8,'stage_gain')
        self.assertLess(z['ci95'][0],0);self.assertGreater(z['ci95'][1],0)


class RolloutArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OUT/'selected_states.json').exists():raise unittest.SkipTest('V145 setup absent')
        cls.selected=load(OUT/'selected_states.json')

    def test_saved_clone_exact_public_and_rng(self):
        p=parent(self.selected['pilot_state_ids'][0])
        self.assertEqual(normalized(p['env'].state),p['state'])
        self.assertEqual(p['env']._engine.rng.getstate(),p['rng_state'])
        self.assertEqual(normalized(p['env'].legal_actions()),p['legal_actions'])
        self.assertEqual(p['env'].state.reroll_tokens,p['row']['reroll_tokens_before'])

    def test_independent_branches_and_seed_label_reproducibility(self):
        sid=self.selected['pilot_state_ids'][0];env=parent(sid)['env'];state=normalized(env.state);rng=env._engine.rng.getstate()
        a=fork_env(env,sid,'current',0);b=fork_env(env,sid,'reroll',0);c=fork_env(env,sid,'reroll',0)
        self.assertNotEqual(a._engine.rng.getstate(),b._engine.rng.getstate())
        self.assertEqual(b._engine.rng.getstate(),c._engine.rng.getstate())
        b.step(Action(T.REROLL));c.step(Action(T.REROLL))
        self.assertEqual(normalized(b.state),normalized(c.state))
        self.assertEqual(normalized(env.state),state);self.assertEqual(env._engine.rng.getstate(),rng)

    def test_frozen_selection_and_asset_preservation(self):
        rows=self.selected['selected']
        self.assertEqual(len(rows),40);self.assertEqual(len({r['state_id'] for r in rows}),40)
        self.assertEqual(len(self.selected['pilot_state_ids']),12)
        self.assertEqual(len(self.selected['convergence_state_ids']),4)
        self.assertTrue(any(r['did_reroll'] for r in rows))
        self.assertTrue(any(not r['did_reroll'] for r in rows))
        self.assertGreater(frozen_check(),400)

    def test_warm_frozen_teacher_cache_preserves_full_path(self):
        sid=self.selected['pilot_state_ids'][0];base=parent(sid)['env']
        warm=RentRerollAgent(base.catalog)
        a=fork_env(base,sid,'reroll',0);b=fork_env(base,sid,'reroll',0)
        left,cuts,_,_=walk(a,Action(T.REROLL),warm,1)
        right,other,_,_=walk(b,Action(T.REROLL),warm,1)
        cold=fork_env(base,sid,'reroll',0)
        fresh,_,_,_=walk(cold,Action(T.REROLL),RentRerollAgent(base.catalog),1)
        self.assertEqual(left,right);self.assertEqual(left,fresh)
        self.assertEqual(normalized(a.state),normalized(b.state))
        self.assertEqual(normalized(a.state),normalized(cold.state))
        self.assertEqual(a._engine.rng.getstate(),cold._engine.rng.getstate())

    def test_process_independent_continuation_reproducibility(self):
        sid=self.selected['pilot_state_ids'][0]
        serial=reproducibility_probe(sid)
        with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
            a=pool.submit(reproducibility_probe,sid);b=pool.submit(reproducibility_probe,sid)
            self.assertEqual(a.result(),serial);self.assertEqual(b.result(),serial)


if __name__=='__main__':unittest.main()
