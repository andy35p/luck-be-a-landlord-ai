from copy import deepcopy
from random import Random
import unittest
from luck_agent.env.offer_sampler import PreparedSymbolOffers
from luck_agent.env.rule_engine import RuleEngine, load_catalog
from luck_agent.env.game_env import GameEnv
from luck_agent.agents.reroll_agent import RerollHeuristicAgent


class OfferSamplerTests(unittest.TestCase):
    def compare(self, sim, n=3):
        other = deepcopy(sim)
        fast = PreparedSymbolOffers(other, n=n)
        for _ in range(16):
            self.assertEqual(sim.candidates("symbol", n=n), fast.sample())
            self.assertEqual(sim.rng.getstate(), other.rng.getstate())
            a = {k:v for k,v in sim.__dict__.items() if k != "rng"}
            b = {k:v for k,v in other.__dict__.items() if k != "rng"}
            self.assertEqual(a, b)

    def test_randomized_public_scenarios(self):
        catalog = load_catalog()
        rng = Random(513)
        items = ["credit_card","rain_cloud","dark_humor","flush","void_party","lucky_carrot","golden_carrot","lucky_cat"]
        for seed in range(80):
            sim = RuleEngine(catalog,seed=seed)
            sim.items = rng.choices(items, k=rng.randrange(12))
            sim.deck += ["highlander"] if seed % 2 else []
            sim.rent_index = seed % 13
            sim.item_counters["credit_card_spins"] = 7 if seed % 3 else 6
            sim.last_shown = rng.choices(["cat","shiny_pebble","hex_of_tedium"], k=8)
            sim.rare_candidate_slots = seed % 5
            if seed % 4 == 0:
                sim.pending_symbol_groups = ["animal"]
            if seed % 5 == 0:
                sim.pending_symbol_rarities = ["=rare" if seed % 2 else "uncommon"]
            self.compare(sim)

    def test_empty_skip_missing_rarity_and_exhausted_rare(self):
        for pool, rarities, rare_slots, skip in [([],{},0,False),(["coin"],{},0,False),
                (["coin"],{"coin":"common"},3,False),
                (["coin","cat"],{"coin":"rare","cat":"very_rare"},3,False),
                (["coin"],{},0,True)]:
            catalog=load_catalog()
            catalog["symbol_pool"],catalog["symbol_rarity"]=pool,rarities
            sim=RuleEngine(catalog,seed=4)
            sim.force_skip_next_choice=skip
            sim.rare_candidate_slots=rare_slots
            self.compare(sim)

    def test_agent_evidence_exact_and_no_stale_cache(self):
        env = GameEnv()
        old = RerollHeuristicAgent(env.catalog, sampler_backend="reference")
        fast = RerollHeuristicAgent(env.catalog)
        for i in range(10):
            env._engine.rerolls = 2
            env._engine.coins = 100*i
            env._engine.items = ["rain_cloud"]*i
            env._offer("symbol","symbol")
            state=env.state
            self.assertEqual(old.estimate(state),fast.estimate(state))
            self.assertEqual(old.choose(state,env.legal_actions()),fast.choose(state,env.legal_actions()))
