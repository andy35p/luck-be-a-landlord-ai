import unittest
import copy
from luck_agent.env.instance_soap_engine import InstanceSoapEngine, soap_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType as T
from luck_agent.legacy.fast_env import FastLandlordEnv


class SoapMigrationTests(unittest.TestCase):
    def engine(self):
        e = InstanceSoapEngine(soap_catalog(load_catalog()))
        e.spins_left = 100
        return e

    def show(self, e, *ids):
        e.pending_instance_ids = ids
        e.pending_shown = [e.instances.get(uid).symbol_id for uid in ids]

    def test_three_children_final_generation_and_no_early_payout(self):
        e = self.engine(); e.choose("bar_of_soap")
        parent = e.instances.snapshot()[-1].instance_id
        children = []
        for _ in range(3):
            self.show(e, parent)
            self.assertEqual(e.spin(), e.catalog["symbol_values"]["bar_of_soap"])
            event = next(x for x in e.instance_events if x["type"] == "generate")
            self.assertEqual(event["source_instance_id"], parent)
            children.append(event["instance_id"])
            self.assertEqual(e.instances.get(children[-1]).remaining_appearances, 3)
            self.assertEqual([x["instance_id"] for x in e.instance_events if x["type"] == "payout"], [parent])
        self.assertEqual(len(set(children)), 3)
        self.assertNotIn(parent, [s.instance_id for s in e.instances.snapshot()])
        self.assertEqual([x["type"] for x in e.instance_events], ["payout", "generate", "destroy"])
        for _ in range(3):
            self.show(e, *children)
            self.assertEqual(e.spin(), 3 * e.catalog["symbol_values"]["bubble"])
        self.assertFalse(set(children) & {s.instance_id for s in e.instances.snapshot()})
        self.assertEqual(e.destroyed_count, 4)
        e.choose("bubble")
        self.assertNotIn(e.instances.snapshot()[-1].instance_id, children)

    def test_only_shown_copy_ticks_and_generation_has_correct_parent(self):
        e = self.engine()
        for _ in range(2): e.choose("bar_of_soap")
        a, b = e.instances.snapshot()[-2:]
        for _ in range(2): e.instances.tick((a.instance_id,))
        e._sync_deck()
        self.show(e, b.instance_id); e.spin()
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances, 1)
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances, 2)
        self.assertEqual(e.instance_events[-1]["source_instance_id"], b.instance_id)
        self.show(e, a.instance_id, b.instance_id); e.spin()
        generated = [x for x in e.instance_events if x["type"] == "generate"]
        self.assertEqual([x["source_instance_id"] for x in generated], [a.instance_id, b.instance_id])
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances, 1)

    def test_undertaker_does_not_pause_soap_or_bubble(self):
        e = self.engine(); e.choose("undertaker", "item")
        for kind in ("bar_of_soap", "bubble"): e.choose(kind)
        ids = tuple(s.instance_id for s in e.instances.snapshot()[-2:])
        for _ in range(3): self.show(e, *ids); e.spin()
        self.assertFalse(set(ids) & {s.instance_id for s in e.instances.snapshot()})

    def test_exact_removal_and_event_delivery_through_env(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-soap-v1"))
        e = env._engine
        for _ in range(2): e.choose("bar_of_soap")
        a, b = e.instances.snapshot()[-2:]
        e.instances.tick((a.instance_id,)); e._sync_deck()
        e.removals = 1; env._phase = "remove"
        env.step(Action(T.REMOVE_SYMBOL, b.instance_id))
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances, 2)
        self.assertEqual(e.soap_ttls, [2])
        env._phase = "spin"; self.show(e, a.instance_id)
        state, _, _, _, info = env.step(Action(T.SPIN))
        child = next(x["instance_id"] for x in info["instance_events"] if x["type"] == "generate")
        self.assertNotIn(child, state.visible_board_ids)
        self.assertIn(child, {s.instance_id for s in state.symbols})
        self.assertEqual(env.step(Action(T.KEEP_OPTIONS))[-1]["instance_events"], [])

    def test_single_soap_matches_legacy_payout_deck_and_rng(self):
        catalog = soap_catalog(load_catalog())
        for seed in range(20):
            old = FastLandlordEnv(catalog, seed=seed, floor=1)
            new = InstanceSoapEngine(catalog, seed=seed)
            old.spins_left = new.spins_left = 100
            old.choose("bar_of_soap"); new.choose("bar_of_soap")
            for _ in range(7):
                self.assertEqual(old.spin(), new.spin())
                self.assertEqual(old.deck, new.deck)
                self.assertEqual(old.bubble_ttls, new.bubble_ttls)
                self.assertEqual(old.soap_ttls, new.soap_ttls)
                self.assertEqual(old.rng.getstate(), new.rng.getstate())

    def test_old_scope_stays_restricted_and_timer_import_rejected(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-spirit-v1"))
        self.assertNotIn("bubble", env.catalog["symbol_pool"])
        with self.assertRaises(ValueError): env._engine.choose("bar_of_soap")
        e = self.engine(); e.choose("bar_of_soap"); e.soap_ttls = [1]
        with self.assertRaises(ValueError): e.spin()

    def test_large_deck_only_drawn_soap_generates(self):
        e = self.engine()
        for _ in range(15): e.choose("coin")
        e.choose("bar_of_soap"); e.choose("bar_of_soap")
        a, b = e.instances.snapshot()[-2:]
        for seed in range(100):
            e.rng.seed(seed)
            expected = e.instances.draw(20, copy.deepcopy(e.rng))
            if a.instance_id not in expected and b.instance_id in expected:
                break
        else: self.fail("No fixture seed found")
        e.spin()
        self.assertEqual(tuple(s.instance_id for s in e.last_board_instances), expected)
        generated = [x for x in e.instance_events if x["type"] == "generate"]
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0]["source_instance_id"], b.instance_id)
        self.assertNotIn(generated[0]["instance_id"], expected)
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances, 3)
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances, 2)
