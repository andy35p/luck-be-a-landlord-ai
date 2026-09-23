from dataclasses import FrozenInstanceError
from random import Random
import unittest
from luck_agent.env.instance_store import InstanceStore
from luck_agent.env.game_env import GameEnv


class InstanceStoreTests(unittest.TestCase):
    def store(self):
        return InstanceStore({"spirit","archaeologist","coal","diamond","coin"})

    def test_bonus_is_per_instance(self):
        store=self.store()
        a,b=store.add("archaeologist"),store.add("archaeologist")
        store.add_bonus(a.instance_id,1)
        self.assertEqual(store.get(a.instance_id).permanent_bonus,1)
        self.assertEqual(store.get(b.instance_id).permanent_bonus,0)

    def test_unshown_timer_does_not_tick(self):
        store=self.store()
        a=store.add("spirit",remaining_appearances=1)
        b=store.add("spirit",remaining_appearances=4)
        self.assertEqual(store.tick((b.instance_id,)),())
        self.assertEqual(store.get(a.instance_id).remaining_appearances,1)
        self.assertEqual(store.get(b.instance_id).remaining_appearances,3)

    def test_remove_second_copy_and_never_reuse_id(self):
        store=self.store()
        a,b=store.add("coin"),store.add("coin")
        store.remove(b.instance_id)
        c=store.add("coin")
        self.assertNotEqual(b.instance_id,c.instance_id)
        self.assertEqual(store.snapshot(),(a,c))
        with self.assertRaises(KeyError):
            store.remove(b.instance_id)

    def test_transform_preserves_identity_and_does_not_change_old_snapshot(self):
        store=self.store()
        coal=store.add("coal",remaining_appearances=1)
        snapshot=store.snapshot()
        self.assertEqual(store.tick((coal.instance_id,)),(coal.instance_id,))
        diamond=store.transform(coal.instance_id,"diamond",permanent_bonus=0,remaining_appearances=None)
        self.assertEqual(diamond.instance_id,coal.instance_id)
        self.assertEqual(snapshot[0].symbol_id,"coal")
        self.assertEqual(snapshot[0].remaining_appearances,1)
        with self.assertRaises(FrozenInstanceError):
            snapshot[0].symbol_id="coin"

    def test_invalid_tick_is_atomic_and_duplicates_rejected(self):
        store=self.store();a=store.add("spirit",remaining_appearances=3)
        for board,error in (((a.instance_id,"missing"),KeyError),((a.instance_id,a.instance_id),ValueError)):
            before=store.snapshot()
            with self.assertRaises(error): store.tick(board)
            self.assertEqual(before,store.snapshot())

    def test_draw_preserves_exact_ids_and_reproducibility(self):
        store=self.store()
        for _ in range(30):store.add("coin")
        board=store.draw(20,Random(42))
        self.assertEqual(board,store.draw(20,Random(42)))
        self.assertEqual(len(set(board)),20)
        store.require_board(board)
        self.assertEqual(len(store.snapshot()),30)

    def test_validation_and_legacy_capability(self):
        store=self.store()
        with self.assertRaises(ValueError): store.add("unknown")
        with self.assertRaises(ValueError): store.add("coin",permanent_bonus=float("nan"))
        with self.assertRaises(ValueError): store.add("coin",remaining_appearances=-1)
        state=GameEnv().state
        self.assertFalse(state.supports_stable_instances)
        self.assertTrue(all(s.identity_scope=="snapshot" and s.permanent_bonus is None for s in state.symbols))
