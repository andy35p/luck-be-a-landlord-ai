from collections import Counter
import random
import unittest
from luck_agent.env.instance_cheese_engine import cheese_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType
from luck_agent.legacy.fast_env import FastLandlordEnv


class CheeseTests(unittest.TestCase):
    def fixture(self, symbols):
        env = GameEnv(EnvConfig(floor=1, rule_version='instance-cheese-v1'))
        e = env._engine
        for s in e.instances.snapshot():
            e.instances.remove(s.instance_id)
        ids = tuple(e.instances.add(s).instance_id for s in symbols)
        e._sync_deck()
        e.pending_instance_ids = ids
        e.pending_shown = list(symbols)
        return env, e, ids

    def compare(self, symbols):
        _, e, _ = self.fixture(symbols)
        old = FastLandlordEnv(cheese_catalog(load_catalog()), seed=0, floor=1)
        old.deck = list(symbols); old.pending_shown = list(symbols)
        self.assertEqual(old.spin(), e.spin())
        self.assertEqual(Counter(old.deck), Counter(e.deck))
        self.assertEqual(old.destroyed_history, e.destroyed_history)
        self.assertEqual(old.destroyed_count, e.destroyed_count)
        self.assertEqual(old.rng.getstate(), e.rng.getstate())

    def test_all_positions_against_recovered_engine(self):
        for actor in range(20):
            for target in range(20):
                if actor == target:
                    continue
                symbols = ['coin']*20
                symbols[actor] = 'mouse'; symbols[target] = 'cheese'
                self.compare(symbols)

    def test_mixed_competition_against_recovered_engine(self):
        rng = random.Random(51)
        for _ in range(100):
            self.compare(rng.choices(['cat','milk','mouse','cheese','coin'], k=20))

    def test_competing_mice_exact_target_and_snapshot(self):
        env, e, ids = self.fixture(['mouse','cheese','mouse'])
        extra = e.instances.add('cheese').instance_id
        e._sync_deck()
        state, reward, _, _, info = env.step(Action(ActionType.SPIN))
        self.assertEqual(reward,20+2*e.catalog['symbol_values']['mouse']+e.catalog['symbol_values']['cheese'])
        events = [v for v in info['instance_events'] if v['type']=='destroy']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['source_instance_id'],ids[0])
        self.assertEqual(events[0]['instance_id'],ids[1])
        self.assertEqual(events[0]['reason'],'mouse_cheese')
        self.assertEqual({s.instance_id for s in state.symbols},{ids[0],ids[2],extra})
        self.assertEqual(state.visible_board_cells[:3],ids)

    def test_multiple_targets_and_wrong_food(self):
        _, e, _ = self.fixture(['cheese','mouse','cheese'])
        self.assertEqual(e.spin(),20+2*e.catalog['symbol_values']['cheese']+e.catalog['symbol_values']['mouse'])
        _, e, _ = self.fixture(['cat','cheese','mouse','milk'])
        e.spin()
        self.assertEqual(e.destroyed_history,['cheese'])

    def test_previous_backend_rejects_new_symbols(self):
        e = GameEnv(EnvConfig(floor=1,rule_version='instance-milk-v1'))._engine
        for symbol in ['mouse','cheese']:
            with self.assertRaises(ValueError):
                e.choose(symbol)
