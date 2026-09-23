import unittest
from luck_agent.env.rule_engine import load_catalog
from luck_agent.legacy.fast_env import FastLandlordEnv


class RemovalTimerRegression(unittest.TestCase):
    def test_adapter_version_and_target_cleanup(self):
        from luck_agent.env.game_env import GameEnv,EnvConfig
        from luck_agent.env.action import Action,ActionType
        env=GameEnv(EnvConfig(rule_version="removal-timers-v1"))
        env._engine.deck=["golem","golem"]
        env._engine.golem_ttls=[1,4];env._engine.removals=1;env._phase="remove"
        env.step(Action(ActionType.REMOVE_SYMBOL,"golem:0"))
        self.assertEqual(env.state.effect_state["golem_ttls"],[4])
        self.assertEqual(len(env.state.symbols),1)
        with self.assertRaises(ValueError):
            EnvConfig(rule_version="typo")

    def test_readded_golem_does_not_inherit_removed_lifetime(self):
        from luck_agent.env.rule_engine import CorrectedRuleEngine
        for cls, expected_ore in ((FastLandlordEnv,5),(CorrectedRuleEngine,0)):
            with self.subTest(engine=cls.__name__):
                env=cls(load_catalog(),seed=4,floor=1)
                env.deck=["golem"];env.golem_ttls=[1];env.removals=1
                self.assertTrue(env.remove("golem"))
                env.choose("golem")
                env.spin()
                self.assertEqual(env.deck.count("ore"),expected_ore)
                if cls is CorrectedRuleEngine:
                    self.assertEqual(env.golem_ttls,[4])

    def test_matching_first_timer_removed_and_failed_action_is_atomic(self):
        from luck_agent.env.rule_engine import CorrectedRuleEngine
        for symbol,field in (("golem","golem_ttls"),("bar_of_soap","soap_ttls")):
            env=CorrectedRuleEngine(load_catalog(),seed=1)
            env.deck=[symbol,symbol];setattr(env,field,[1,3]);env.removals=1
            self.assertTrue(env.remove(symbol))
            self.assertEqual(getattr(env,field),[3])
            self.assertFalse(env.remove(symbol))
            self.assertEqual(getattr(env,field),[3])

    def test_all_doll_stages_clean_only_matching_queue(self):
        from luck_agent.env.rule_engine import CorrectedRuleEngine
        for stage in range(1,5):
            symbol=f"matryoshka_doll_{stage}"
            env=CorrectedRuleEngine(load_catalog(),seed=2)
            env.deck=[symbol,symbol,"coin"];env.removals=1
            env.matryoshka_ttls={symbol:[1,5],"other":[7]}
            self.assertTrue(env.remove(symbol))
            self.assertEqual(env.matryoshka_ttls,{symbol:[5],"other":[7]})

    def test_lazy_uninitialized_timer_can_be_removed(self):
        from luck_agent.env.rule_engine import CorrectedRuleEngine
        env=CorrectedRuleEngine(load_catalog(),seed=2)
        env.deck=["bar_of_soap"];env.removals=1
        self.assertTrue(env.remove("bar_of_soap"))
        self.assertEqual(env.soap_ttls,[])
