import unittest
from collections import Counter
from luck_agent.env.instance_coal_engine import InstanceCoalEngine, coal_catalog
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.rule_engine import load_catalog
from luck_agent.env.action import Action, ActionType as T
from luck_agent.legacy.fast_env import FastLandlordEnv


class CoalMigrationTests(unittest.TestCase):
    def engine(self):
        e = InstanceCoalEngine(coal_catalog(load_catalog()))
        e.spins_left = 100
        return e

    def show(self, e, *ids):
        e.pending_instance_ids = ids
        e.pending_shown = [e.instances.get(uid).symbol_id for uid in ids]

    def test_twenty_appearances_preserve_id_and_clear_timer(self):
        e = self.engine(); e.choose("coal")
        uid = e.instances.snapshot()[-1].instance_id
        for i in range(20):
            self.show(e, uid)
            self.assertEqual(e.spin(), e.catalog["symbol_values"]["coal"])
            self.assertEqual(e.last_board_instances[0].symbol_id, "coal")
            self.assertEqual(e.last_board_instances[0].remaining_appearances, 20-i)
        diamond = e.instances.get(uid)
        self.assertEqual(diamond.symbol_id, "diamond")
        self.assertIsNone(diamond.remaining_appearances)
        self.assertEqual(diamond.permanent_bonus, 0)
        self.assertEqual(e.destroyed_count, 0)
        self.assertEqual(e.coal_ttls, [])
        self.assertEqual([x["type"] for x in e.instance_events], ["payout", "transform"])
        self.show(e, uid)
        self.assertEqual(e.spin(), e.catalog["symbol_values"]["diamond"])

    def test_only_selected_copy_transforms_and_new_diamond_waits(self):
        e = self.engine()
        for kind in ("coal", "coal", "diamond"): e.choose(kind)
        a, b, d = e.instances.snapshot()[-3:]
        for _ in range(19): e.instances.tick((a.instance_id, b.instance_id))
        e._sync_deck()
        self.show(e, b.instance_id, d.instance_id)
        self.assertEqual(e.spin(), e.catalog["symbol_values"]["coal"] + e.catalog["symbol_values"]["diamond"])
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances, 1)
        self.assertEqual(e.instances.get(b.instance_id).symbol_id, "diamond")
        self.show(e, b.instance_id, d.instance_id)
        self.assertEqual(e.spin(), 2 * (e.catalog["symbol_values"]["diamond"] + 1))
        self.assertEqual(sum(x["amount"] for x in e.instance_events if x["type"] == "payout"), e.catalog["symbol_values"]["diamond"]*2+2)

    def test_transformed_target_remains_removable_through_env(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))
        e = env._engine; e.choose("coal")
        uid = e.instances.snapshot()[-1].instance_id
        for _ in range(19): e.instances.tick((uid,))
        e._sync_deck(); self.show(e, uid)
        state, _, _, _, info = env.step(Action(T.SPIN))
        self.assertEqual(state.visible_board_instances[0].symbol_id, "coal")
        self.assertEqual(next(s.symbol_id for s in state.symbols if s.instance_id == uid), "diamond")
        self.assertEqual(info["instance_events"][-1]["instance_id"], uid)
        e.removals = 1; env._phase = "remove"
        action = Action(T.REMOVE_SYMBOL, uid)
        self.assertEqual(env.action_mask((action,)), (True,))
        env.step(action)
        self.assertNotIn(uid, {s.instance_id for s in env.state.symbols})

    def test_compatible_single_coal_matches_old_engine(self):
        catalog = coal_catalog(load_catalog())
        for seed in range(20):
            old = FastLandlordEnv(catalog, seed=seed, floor=1)
            new = InstanceCoalEngine(catalog, seed=seed)
            old.spins_left = new.spins_left = 100
            old.choose("coal"); new.choose("coal")
            for _ in range(22):
                self.assertEqual(old.spin(), new.spin())
                self.assertEqual(Counter(old.deck), Counter(new.deck))
                self.assertEqual(old.coal_ttls, new.coal_ttls)
                self.assertEqual(old.rng.getstate(), new.rng.getstate())

    def test_multiple_diamonds_match_old_synergy(self):
        e = self.engine()
        old = FastLandlordEnv(e.catalog, floor=1)
        for _ in range(3): old.choose("diamond"); e.choose("diamond")
        self.assertEqual(old.spin(), e.spin())

    def test_old_scope_and_unmigrated_time_machine_rejected(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-soap-v1"))
        with self.assertRaises(ValueError): env._engine.choose("coal")
        e = self.engine()
        with self.assertRaises(ValueError): e.choose("time_machine", "item")
        e.choose("coal"); e.coal_ttls = [1]
        with self.assertRaises(ValueError): e.spin()
