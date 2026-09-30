import json
from pathlib import Path
import unittest
from luck_agent.env.game_env import GameEnv, EnvConfig


class InstanceMagpieTests(unittest.TestCase):
    def fixture(self, remaining):
        engine=GameEnv(EnvConfig(floor=1,rule_version='instance-magpie-v1'))._engine
        for symbol in engine.instances.snapshot():engine.instances.remove(symbol.instance_id)
        ids=[engine.instances.add('magpie',remaining_appearances=n).instance_id for n in remaining]
        engine._sync_deck();engine.spins_left=100
        return engine,ids

    def spin_board(self, engine, ids):
        engine.pending_instance_ids=tuple(ids)
        engine.pending_shown=[engine.instances.get(i).symbol_id for i in ids]
        return engine.spin()

    def test_twenty_fresh_copies_do_not_share_a_cycle(self):
        engine,ids=self.fixture([4]*25)
        self.assertEqual(self.spin_board(engine,ids[:20]),-20)
        self.assertEqual([engine.instances.get(i).remaining_appearances for i in ids],[3]*20+[4]*5)
        self.assertFalse(any(e['type']=='cycle_reset' for e in engine.instance_events))

    def test_separate_due_copies_reset_without_destruction(self):
        engine,ids=self.fixture([1,2,1,4])
        self.assertEqual(self.spin_board(engine,ids[:2]),7)
        self.assertEqual([engine.instances.get(i).remaining_appearances for i in ids],[4,1,1,4])
        self.assertEqual(engine.destroyed_count,0)
        resets=[e['instance_id'] for e in engine.instance_events if e['type']=='cycle_reset']
        self.assertEqual(resets,[ids[0]])

    def test_observed_controlled_membership_replays_per_instance(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/controlled_timer_trace.json').read_text(encoding='utf-8'))
        rows=fixture['cases'];engine,ids=self.fixture([4]*25)
        mapping=dict(zip([s['instance_id'] for s in rows[0]['state']['symbols']],ids))
        for row in rows[1:]:
            board=[mapping[i] for line in row['state']['displayed_board']['rows'] for i in line]
            self.spin_board(engine,board)
            for observed in row['state']['symbols']:
                self.assertEqual(engine.instances.get(mapping[observed['instance_id']]).remaining_appearances,
                                 4-observed['times_displayed'])

    def test_natural_single_instance_reset_trace(self):
        trace=json.loads((Path(__file__).parent/'fixtures/live_timer_trace.json').read_text(encoding='utf-8'))['trace']
        counts=[next(s['times_displayed'] for s in row['symbols'] if s['type']=='magpie') for row in trace]
        engine,ids=self.fixture([4-counts[0]])
        self.assertEqual(self.spin_board(engine,ids),-1)
        self.assertEqual(engine.instances.get(ids[0]).remaining_appearances,4-counts[1])
        self.assertEqual(self.spin_board(engine,ids),8)
        self.assertEqual(engine.instances.get(ids[0]).remaining_appearances,4-counts[2])

    def test_prior_scope_and_unverified_items_remain_rejected(self):
        old=GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1'))._engine
        with self.assertRaises(ValueError):old.choose('magpie')
        engine,ids=self.fixture([4]);engine.items=['tax_evasion']
        with self.assertRaises(ValueError):self.spin_board(engine,ids)
