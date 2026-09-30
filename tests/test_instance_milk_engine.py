import unittest
from luck_agent.env.instance_milk_engine import InstanceMilkEngine, milk_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType
from luck_agent.legacy.fast_env import FastLandlordEnv


class MilkTests(unittest.TestCase):
    def fixture(self, symbols):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-milk-v1"))
        e = env._engine
        for s in e.instances.snapshot():
            e.instances.remove(s.instance_id)
        ids = tuple(e.instances.add(s).instance_id for s in symbols)
        e._sync_deck()
        e.pending_instance_ids = ids
        e.pending_shown = list(symbols)
        return env, e, ids

    def test_competition_and_base_payout(self):
        env, e, ids = self.fixture(["cat", "milk", "cat"])
        state, reward, _, _, info = env.step(Action(ActionType.SPIN))
        self.assertEqual(reward, 9 + sum(e.catalog['symbol_values'][s] for s in ['cat','milk','cat']))
        destroyed = [v for v in info['instance_events'] if v['type']=='destroy']
        self.assertEqual(len(destroyed), 1)
        self.assertEqual(destroyed[0]['source_instance_id'], ids[0])
        self.assertEqual(destroyed[0]['instance_id'], ids[1])
        self.assertNotIn(ids[1], {s.instance_id for s in state.symbols})
        self.assertEqual(state.visible_board_cells[:3], ids)

    def test_multiple_targets_and_unshown_copy(self):
        _, e, ids = self.fixture(['milk','cat','milk'])
        extra = e.instances.add('milk').instance_id
        e._sync_deck()
        self.assertEqual(e.spin(), 9 + sum(e.catalog['symbol_values'][s] for s in ['milk','cat','milk']))
        self.assertEqual(e.destroyed_count,1)
        self.assertEqual(e.instances.get(extra).symbol_id,'milk')
        self.assertEqual({s.instance_id for s in e.instances.snapshot()}, {ids[1],ids[2],extra})

    def test_row_edge_not_adjacent(self):
        _, e, ids = self.fixture(['coin']*4+['cat','milk'])
        e.spin()
        self.assertEqual(e.destroyed_count,0)
        self.assertEqual(e.instances.get(ids[5]).symbol_id,'milk')

    def test_all_board_pairs_match_legacy(self):
        catalog = milk_catalog(load_catalog())
        for cat in range(20):
            for milk in range(20):
                if cat == milk:
                    continue
                symbols = ['coin']*20
                symbols[cat]='cat'; symbols[milk]='milk'
                _, new, _ = self.fixture(symbols)
                old = FastLandlordEnv(catalog, seed=0, floor=1)
                old.deck=list(symbols); old.pending_shown=list(symbols)
                self.assertEqual(old.spin(),new.spin())
                self.assertEqual(old.deck,new.deck)
                self.assertEqual(old.destroyed_count,new.destroyed_count)
                self.assertEqual(old.destroyed_history,new.destroyed_history)

    def test_old_scope_rejects_milk(self):
        old=GameEnv(EnvConfig(floor=1,rule_version='instance-time-v1'))
        with self.assertRaises(ValueError):
            old._engine.choose('milk')
