from collections import Counter
import random
import unittest
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.rule_engine import load_catalog
from luck_agent.env.instance_goldfish_engine import goldfish_catalog
from luck_agent.legacy.fast_env import FastLandlordEnv


class GoldfishTests(unittest.TestCase):
    def test_mixed_plan_matches_exhaustive_geometry(self):
        rng = random.Random(54)
        rules = {'cat': ('milk',9,'cat_milk'), 'mouse': ('cheese',20,'mouse_cheese'),
                 'goldfish': ('bubble',15,'goldfish_bubble')}
        for _ in range(300):
            symbols = rng.choices(['cat','milk','mouse','cheese','goldfish','bubble','coin'],
                                  k=rng.randrange(21))
            timers = {i:rng.randint(1,3) for i,s in enumerate(symbols) if s=='bubble'}
            e, ids = self.fixture(symbols,timers)
            expected, consumed = [], set()
            for i,s in enumerate(symbols):
                if s not in rules: continue
                kind,bonus,reason = rules[s]
                for j,target in enumerate(symbols):
                    if (target != kind or j in consumed or i==j
                            or max(abs(i//5-j//5),abs(i%5-j%5))!=1
                            or (target=='bubble' and timers[j]<=1)):
                        continue
                    expected.append((ids[i],ids[j],bonus,reason));consumed.add(j);break
            self.assertEqual(e.consumption_plan(e.instances.snapshot()),tuple(expected))

    def fixture(self, symbols, timers=None):
        env = GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1'))
        e = env._engine
        for s in e.instances.snapshot(): e.instances.remove(s.instance_id)
        timers = timers or {}
        ids = tuple(e.instances.add(s,remaining_appearances=timers.get(i,e.initial_lifetime(s))).instance_id
                    for i,s in enumerate(symbols))
        e._sync_deck(); e.pending_instance_ids=ids; e.pending_shown=list(symbols)
        return e, ids

    def test_all_positions_and_lifetimes_against_legacy(self):
        for ttl in (1,2,3):
            for actor in range(20):
                for target in range(20):
                    if actor == target: continue
                    symbols=['coin']*20;symbols[actor]='goldfish';symbols[target]='bubble'
                    e,_=self.fixture(symbols,{target:ttl})
                    old=FastLandlordEnv(goldfish_catalog(load_catalog()),seed=0,floor=1)
                    old.deck=list(symbols);old.pending_shown=list(symbols);old.bubble_ttls=[ttl]
                    self.assertEqual(old.spin(),e.spin())
                    self.assertEqual(Counter(old.deck),Counter(e.deck))
                    self.assertEqual(old.bubble_ttls,e.bubble_ttls)
                    self.assertEqual(old.destroyed_count,e.destroyed_count)

    def test_expiring_target_skipped_without_compacting_board(self):
        e,ids=self.fixture(['bubble','goldfish','bubble'],{0:1,2:3})
        income=e.spin()
        self.assertEqual(income,15+2*e.catalog['symbol_values']['bubble']+e.catalog['symbol_values']['goldfish'])
        events=[v for v in e.instance_events if v['type']=='destroy']
        self.assertEqual(len(events),2)
        reasons={v['instance_id']:v['reason'] for v in events}
        self.assertEqual(reasons,{ids[0]:'bubble_lifetime',ids[2]:'goldfish_bubble'})
        self.assertEqual(e.destroyed_count,2)

    def test_competition_and_unshown_bubble(self):
        e,ids=self.fixture(['goldfish','bubble','goldfish'])
        extra=e.instances.add('bubble',remaining_appearances=2);e._sync_deck()
        e.spin()
        events=[v for v in e.instance_events if v['type']=='destroy']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['source_instance_id'],ids[0])
        self.assertEqual(e.instances.get(extra.instance_id).remaining_appearances,2)

    def test_one_target_per_goldfish(self):
        e,ids=self.fixture(['bubble','goldfish','bubble'])
        e.spin()
        self.assertEqual(e.destroyed_count,1)
        self.assertEqual(e.instances.get(ids[2]).remaining_appearances,2)

    def test_new_soap_child_neither_consumed_nor_aged(self):
        e,ids=self.fixture(['goldfish','bar_of_soap'],{1:1})
        income=e.spin()
        self.assertEqual(income,e.catalog['symbol_values']['goldfish']+e.catalog['symbol_values']['bar_of_soap'])
        bubbles=[s for s in e.instances.snapshot() if s.symbol_id=='bubble']
        self.assertEqual(len(bubbles),1)
        self.assertEqual(bubbles[0].remaining_appearances,3)
        self.assertNotIn(bubbles[0].instance_id,e.last_instance_board.cells)
        self.assertEqual(e.destroyed_count,1)

    def test_previous_scope_rejects_goldfish(self):
        e=GameEnv(EnvConfig(floor=1,rule_version='instance-cheese-v1'))._engine
        with self.assertRaises(ValueError): e.choose('goldfish')
