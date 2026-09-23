import copy
import unittest
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.instance_spirit_engine import InstanceSpiritEngine, restricted_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.legacy.fast_env import FastLandlordEnv
from luck_agent.env.action import Action, ActionType as T
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.evaluation.evaluator import evaluate


class SpiritMigrationTests(unittest.TestCase):
    def engine(self, seed=0):
        e=InstanceSpiritEngine(restricted_catalog(load_catalog()),seed=seed)
        e.spins_left=100
        return e

    def show(self, engine, ids):
        engine.pending_instance_ids=tuple(ids)
        engine.pending_shown=[engine.instances.get(uid).symbol_id for uid in ids]

    def test_only_selected_copy_ticks_and_exact_copy_expires(self):
        e=self.engine()
        e.choose("spirit");e.choose("spirit")
        a,b=[s for s in e.instances.snapshot() if s.symbol_id=="spirit"]
        e.instances.tick((a.instance_id,));e.instances.tick((a.instance_id,));e.instances.tick((a.instance_id,))
        e._sync_deck()
        self.show(e,(b.instance_id,))
        self.assertEqual(e.spin(),6)  # recovered catalog, not the older unit fixture
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances,1)
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances,3)
        self.show(e,(a.instance_id,))
        self.assertEqual(e.spin(),6)
        with self.assertRaises(KeyError):e.instances.get(a.instance_id)
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances,3)
        self.assertEqual(e.instance_events[-1]["instance_id"],a.instance_id)
        self.assertEqual(e.instance_events[-1]["type"],"destroy")

    def test_four_payouts_and_new_copy_fresh(self):
        e=self.engine();e.choose("spirit")
        spirit=e.instances.snapshot()[-1]
        total=0
        for _ in range(4):
            self.show(e,(spirit.instance_id,));total+=e.spin()
        self.assertEqual(total,24)
        e.choose("spirit")
        fresh=e.instances.snapshot()[-1]
        self.assertNotEqual(fresh.instance_id,spirit.instance_id)
        self.assertEqual(fresh.remaining_appearances,4)

    def test_undertaker_pauses_individual_timer(self):
        e=self.engine();e.choose("spirit");e.choose("undertaker","item")
        uid=e.instances.snapshot()[-1].instance_id
        for _ in range(8):
            self.show(e,(uid,));self.assertEqual(e.spin(),6)
        self.assertEqual(e.instances.get(uid).remaining_appearances,4)

    def test_board_ids_link_payout_and_final_destruction(self):
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-spirit-v1"))
        e=env._engine;e.choose("spirit")
        uid=e.instances.snapshot()[-1].instance_id
        for _ in range(3):e.instances.tick((uid,))
        e._sync_deck()
        self.show(e,(uid,))
        state,_,_,_,info=env.step(Action(T.SPIN))
        self.assertTrue(state.supports_stable_instances)
        self.assertEqual(state.visible_board_ids,(uid,))
        self.assertEqual(state.visible_board_instances[0].remaining_appearances,1)
        self.assertNotIn(uid,{s.instance_id for s in state.symbols})
        self.assertEqual([x["type"] for x in info["instance_events"]],["payout","destroy"])
        # The next menu action must not repeat the previous spin's events.
        self.assertEqual(env.step(Action(T.KEEP_OPTIONS))[-1]["instance_events"],[])

    def test_remove_second_id_and_stale_target_masked(self):
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-spirit-v1"));e=env._engine
        e.choose("spirit");e.choose("spirit")
        a,b=[s for s in e.instances.snapshot() if s.symbol_id=="spirit"]
        e.instances.tick((a.instance_id,));e._sync_deck();e.removals=2;env._phase="remove"
        env.step(Action(T.REMOVE_SYMBOL,b.instance_id))
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances,3)
        env._phase="remove"
        self.assertFalse(env.action_mask((Action(T.REMOVE_SYMBOL,b.instance_id),))[0])
        with self.assertRaises(ValueError):env.step(Action(T.REMOVE_SYMBOL,b.instance_id))

    def test_old_heuristic_resolves_id_instead_of_parsing(self):
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-spirit-v1"));env._engine.removals=1;env._phase="remove"
        action=HeuristicAgent(env.catalog).choose(env.state,env.legal_actions())
        self.assertEqual(action,Action(T.KEEP_OPTIONS))  # every supported starting symbol is worth 1

    def test_unsupported_effects_are_rejected_without_rng_change(self):
        e=self.engine();before=e.instances.snapshot();rng=e.rng.getstate()
        for choice,kind in (("coal","symbol"),("oil_can","item"),("x","essence")):
            with self.assertRaises(ValueError):e.choose(choice,kind)
        with self.assertRaises(ValueError):e.spin("swap:0:1")
        self.assertEqual(before,e.instances.snapshot());self.assertEqual(rng,e.rng.getstate())
        e.items.append("oil_can")
        with self.assertRaises(ValueError):e.spin()
        self.assertEqual(rng,e.rng.getstate())
        with self.assertRaises(ValueError):EnvConfig(rule_version="instance-spirit-v1")

    def test_single_spirit_matches_old_engine(self):
        catalog=restricted_catalog(load_catalog())
        for seed in range(20):
            old=FastLandlordEnv(catalog,seed=seed,floor=1);new=InstanceSpiritEngine(catalog,seed=seed)
            old.spins_left=new.spins_left=100
            old.choose("spirit");new.choose("spirit")
            for _ in range(6):
                self.assertEqual(old.spin(),new.spin())
                self.assertEqual(old.deck,new.deck)
                self.assertEqual(old.spirit_ttls,new.spirit_ttls)
                self.assertEqual(old.rng.getstate(),new.rng.getstate())

    def test_real_sampling_updates_only_the_selected_id(self):
        e=self.engine()
        for _ in range(15):e.choose("coin")
        e.choose("spirit");e.choose("spirit")
        a,b=[s for s in e.instances.snapshot() if s.symbol_id=="spirit"]
        for _ in range(3):e.instances.tick((a.instance_id,))
        e._sync_deck()
        for seed in range(100):
            e.rng.seed(seed)
            expected=e.instances.draw(20,copy.deepcopy(e.rng))
            if b.instance_id in expected and a.instance_id not in expected:
                break
        else:self.fail("No fixture seed found")
        e.spin()
        self.assertEqual(tuple(s.instance_id for s in e.last_board_instances),expected)
        self.assertEqual(e.instances.get(a.instance_id).remaining_appearances,1)
        self.assertEqual(e.instances.get(b.instance_id).remaining_appearances,3)

    def test_type_only_lifetime_import_rejected(self):
        e=self.engine();e.choose("spirit");e.spirit_ttls=[1]
        rng=e.rng.getstate()
        with self.assertRaises(ValueError):e.spin()
        self.assertEqual(rng,e.rng.getstate())

    def test_batches_reproduce_and_observation_reads_are_pure(self):
        config=EnvConfig(floor=1,rule_version="instance-spirit-v1")
        for mode in ("random","heuristic"):
            a,_=evaluate(10,mode,0,config);b,_=evaluate(10,mode,0,config)
            self.assertEqual(a,b)
            self.assertFalse(any(r["truncated"] for r in a))
        env=GameEnv(config);state=env.state;rng=env._engine.rng.getstate()
        self.assertEqual(env.state,state);env.legal_actions()
        self.assertEqual(rng,env._engine.rng.getstate())
