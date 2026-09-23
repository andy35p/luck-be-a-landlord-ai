import copy
import unittest
from luck_agent.env.instance_present_engine import InstancePresentEngine, present_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.legacy.fast_env import FastLandlordEnv
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType as T


class PresentTests(unittest.TestCase):
    def engine(self):
        e=InstancePresentEngine(present_catalog(load_catalog()));e.spins_left=100;return e

    def show(self,e,*ids):
        e.pending_instance_ids=ids;e.pending_shown=[e.instances.get(i).symbol_id for i in ids]

    def test_final_bonus_once_and_destruction(self):
        e=self.engine();e.choose('present');uid=e.instances.snapshot()[-1].instance_id
        base=e.catalog['symbol_values']['present']
        for i in range(12):
            self.show(e,uid);self.assertEqual(e.spin(),base+(10 if i==11 else 0))
        self.assertEqual(e.destroyed_history,['present']);self.assertEqual(e.destroyed_count,1)
        self.assertEqual(e.present_ttls,[])
        self.assertEqual(e.instance_events[0]['amount'],base+10)
        self.assertEqual(e.instance_events[-1]['instance_id'],uid)
        self.show(e);self.assertEqual(e.spin(),0)

    def test_other_copy_not_ticked_and_removal_no_bonus(self):
        e=self.engine();e.choose('present');e.choose('present');a,b=e.instances.snapshot()[-2:]
        for _ in range(11):e.instances.tick((a.instance_id,))
        e._sync_deck();self.show(e,b.instance_id);e.spin()
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances,1)
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances,11)
        coins=e.coins;e.removals=1;self.assertTrue(e.remove(a.instance_id))
        self.assertEqual(e.coins,coins);self.assertEqual(e.present_ttls,[11])

    def test_undertaker_does_not_pause_present(self):
        e=self.engine();e.choose('present');e.choose('undertaker','item');uid=e.instances.snapshot()[-1].instance_id
        for _ in range(12):self.show(e,uid);e.spin()
        self.assertNotIn(uid,{s.instance_id for s in e.instances.snapshot()})

    def test_legacy_differential(self):
        catalog=present_catalog(load_catalog())
        for seed in range(20):
            old=FastLandlordEnv(catalog,seed=seed,floor=1);new=InstancePresentEngine(catalog,seed=seed)
            old.spins_left=new.spins_left=100;old.choose('present');new.choose('present')
            for _ in range(14):
                self.assertEqual(old.spin(),new.spin());self.assertEqual(old.deck,new.deck)
                self.assertEqual(old.present_ttls,new.present_ttls)
                self.assertEqual(old.destroyed_history,new.destroyed_history)
                self.assertEqual(old.rng.getstate(),new.rng.getstate())

    def test_large_deck_only_sampled_present_ticks(self):
        e=self.engine()
        for _ in range(15):e.choose('coin')
        e.choose('present');e.choose('present');a,b=e.instances.snapshot()[-2:]
        for seed in range(100):
            e.rng.seed(seed);board=e.instances.draw(20,copy.deepcopy(e.rng))
            if a.instance_id not in board and b.instance_id in board:break
        else:self.fail('No fixture seed')
        e.spin()
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances,12)
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances,11)

    def test_env_reward_and_old_scope(self):
        env=GameEnv(EnvConfig(floor=1,rule_version='instance-present-v1'));e=env._engine
        e.choose('present');uid=e.instances.snapshot()[-1].instance_id
        for _ in range(11):e.instances.tick((uid,))
        e._sync_deck();self.show(e,uid)
        state,reward,_,_,info=env.step(Action(T.SPIN))
        self.assertEqual(reward,10+e.catalog['symbol_values']['present'])
        self.assertEqual(state.visible_board_instances[0].remaining_appearances,1)
        self.assertNotIn(uid,{s.instance_id for s in state.symbols})
        self.assertEqual(info['instance_events'][-1]['reason'],'present_lifetime')
        old=GameEnv(EnvConfig(floor=1,rule_version='instance-coal-v1'))
        with self.assertRaises(ValueError):old._engine.choose('present')
        with self.assertRaises(ValueError):e.choose('time_machine','item')
