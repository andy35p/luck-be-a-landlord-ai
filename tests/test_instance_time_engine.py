import unittest
from luck_agent.env.instance_time_engine import InstanceTimeEngine, time_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.legacy.fast_env import FastLandlordEnv
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType as T


class TimeMachineTests(unittest.TestCase):
    def engine(self):
        e=InstanceTimeEngine(time_catalog(load_catalog()));e.spins_left=100;return e

    def test_existing_instances_keep_remaining_lifetime(self):
        e=self.engine();e.choose('coal');e.choose('present')
        a,b=e.instances.snapshot()[-2:];e.instances.tick((a.instance_id,b.instance_id));e._sync_deck()
        e.choose('time_machine','item')
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances,19)
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances,11)
        e.choose('coal');e.choose('present')
        self.assertEqual([s.remaining_appearances for s in e.instances.snapshot()[-2:]],[15,7])

    def test_duplicate_items_do_not_stack_and_other_timers_unchanged(self):
        e=self.engine()
        for _ in range(2):e.choose('time_machine','item')
        for kind in ('coal','present','spirit','bubble','bar_of_soap'):e.choose(kind)
        self.assertEqual([s.remaining_appearances for s in e.instances.snapshot()[-5:]],[15,7,4,3,3])
        e.reset();e.choose('coal');self.assertEqual(e.instances.snapshot()[-1].remaining_appearances,20)

    def test_new_present_and_coal_complete_on_shortened_schedule(self):
        for kind,lifetime in [('present',7),('coal',15)]:
            e=self.engine();e.choose('time_machine','item');e.choose(kind);uid=e.instances.snapshot()[-1].instance_id
            for i in range(lifetime):
                e.pending_instance_ids=(uid,);e.pending_shown=[kind];income=e.spin()
                if i<lifetime-1:self.assertEqual(e.instances.get(uid).symbol_id,kind)
            if kind=='present':
                self.assertEqual(income,10+e.catalog['symbol_values'][kind])
                self.assertNotIn(uid,{s.instance_id for s in e.instances.snapshot()})
            else:self.assertEqual(e.instances.get(uid).symbol_id,'diamond')

    def test_old_engine_acquisition_order_differential(self):
        catalog=time_catalog(load_catalog())
        for seed in range(10):
            for kind in ('coal','present'):
                for acquire_first in (True,False):
                    old=FastLandlordEnv(catalog,seed=seed,floor=1);new=InstanceTimeEngine(catalog,seed=seed)
                    old.spins_left=new.spins_left=100
                    for e in (old,new):
                        if acquire_first:e.choose('time_machine','item')
                        e.choose(kind)
                    for step in range(22):
                        if step==3 and not acquire_first:
                            old.choose('time_machine','item');new.choose('time_machine','item')
                        self.assertEqual(old.spin(),new.spin());self.assertEqual(old.deck,new.deck)
                        self.assertEqual(old.coal_ttls,new.coal_ttls);self.assertEqual(old.present_ttls,new.present_ttls)
                        self.assertEqual(old.rng.getstate(),new.rng.getstate())

    def test_gameenv_item_action_and_old_scope(self):
        env=GameEnv(EnvConfig(floor=1,rule_version='instance-time-v1'))
        env._phase='item';env._options=('time_machine',)
        env.step(Action(T.PICK_ITEM,'time_machine'))
        self.assertIn('time_machine',env.state.items)
        env._engine.choose('present');self.assertEqual(env.state.symbols[-1].remaining_appearances,7)
        old=GameEnv(EnvConfig(floor=1,rule_version='instance-present-v1'))
        self.assertNotIn('time_machine',old.catalog['item_pool'])
        with self.assertRaises(ValueError):old._engine.choose('time_machine','item')
