import unittest
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate, evaluate_parallel


class ParallelEvaluationTests(unittest.TestCase):
    def test_full_episodes_match_in_seed_order(self):
        cfg=EnvConfig(floor=1,rule_version='instance-goldfish-v1')
        for mode in ('random','heuristic'):
            expected,_=evaluate(5,mode,91,cfg)
            actual,elapsed=evaluate_parallel(5,mode,91,cfg,workers=2)
            self.assertEqual(actual,expected)
            self.assertGreater(elapsed,0)
            self.assertEqual([r['seed'] for r in actual],list(range(91,96)))

    def test_truncation_and_more_workers_than_games(self):
        cfg=EnvConfig(floor=1,rule_version='instance-goldfish-v1',max_decisions=2)
        expected,_=evaluate(2,'heuristic_reroll',7,cfg)
        actual,_=evaluate_parallel(2,'heuristic_reroll',7,cfg,workers=3)
        self.assertEqual(actual,expected)
        self.assertTrue(all(r['truncated'] for r in actual))

    def test_cross_rent_policy_matches_with_uneven_batches(self):
        cfg=EnvConfig(floor=1,rule_version='instance-magpie-v1',max_decisions=10)
        expected,_=evaluate(3,'forecast_rents',6000,cfg)
        actual,_=evaluate_parallel(3,'forecast_rents',6000,cfg,workers=2)
        self.assertEqual(actual,expected)
        self.assertEqual([r['seed'] for r in actual],[6000,6001,6002])

    def test_invalid_arguments_and_child_failure(self):
        cfg=EnvConfig(floor=1,rule_version='instance-goldfish-v1')
        for workers in (0,-1,True,1.5):
            with self.assertRaises(ValueError):
                evaluate_parallel(2,'random',0,cfg,workers=workers)
        with self.assertRaises(ValueError):
            evaluate_parallel(0,'random',0,cfg,workers=2)
        with self.assertRaises(ValueError):
            evaluate_parallel(2,'invalid',0,cfg,workers=2)
