from itertools import product
import unittest
from luck_agent.agents.magpie_cycle_agent import fresh_magpie_score,MagpieCycleAgent
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.evaluation.evaluator import evaluate


class MagpieCycleAgentTests(unittest.TestCase):
    def test_certain_appearances_respect_first_payout_delay(self):
        self.assertEqual(fresh_magpie_score(3,19),-1)
        self.assertEqual(fresh_magpie_score(4,19),1.25)
        self.assertAlmostEqual(fresh_magpie_score(5,19),0.8)
        self.assertEqual(fresh_magpie_score(8,19),1.25)

    def test_fractional_draw_probability_matches_exhaustive_sequences(self):
        for horizon in (1,4,7):
            p=0.5;expected=0.0
            for sequence in product((0,1),repeat=horizon):
                count=sum(sequence)
                expected += (p**horizon)*(-count+9*(count//4))
            self.assertAlmostEqual(fresh_magpie_score(horizon,39),expected/(horizon*p))

    def test_experiment_rejects_other_domains_and_bad_inputs(self):
        with self.assertRaises(ValueError):MagpieCycleAgent(GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1')).catalog)
        for horizon,size in ((True,10),(-1,10),(4,-1),(4,2.5)):
            with self.assertRaises(ValueError):fresh_magpie_score(horizon,size)

    def test_episode_actions_stay_legal_and_repeatable(self):
        config=EnvConfig(floor=1,rule_version='instance-magpie-v1')
        first,_=evaluate(3,'heuristic_magpie_cycle',0,config)
        second,_=evaluate(3,'heuristic_magpie_cycle',0,config)
        self.assertEqual(first,second)
        self.assertFalse(any(r['truncated'] for r in first))
