import unittest

from luck_agent.evaluation.metrics import summarize


class MetricsUncertaintyTests(unittest.TestCase):
    def test_reports_sample_std_and_mean_interval_without_changing_means(self):
        rows = [
            {"won": 0, "stage": 1, "spins": 10, "coins": 2, "reward": -1,
             "truncated": 0, "decisions": 4},
            {"won": 1, "stage": 3, "spins": 20, "coins": 6, "reward": 3,
             "truncated": 0, "decisions": 6},
        ]
        result = summarize(rows, 2.0, 3)
        self.assertEqual(result["average_stage"], 2)
        self.assertAlmostEqual(result["std"]["stage"], 2**0.5)
        self.assertLess(result["mean_95_ci"]["stage"][0], 2)
        self.assertGreater(result["mean_95_ci"]["stage"][1], 2)
        self.assertEqual(result["rent_survival"], {"1": 1, "2": .5, "3": .5})
        self.assertEqual(set(result["rent_survival_95_ci"]), {"1", "2", "3"})
        self.assertLess(result["win_rate_95_ci"][0], .5)
        self.assertGreater(result["win_rate_95_ci"][1], .5)

    def test_single_episode_has_zero_std_and_finite_intervals(self):
        row = {"won": 0, "stage": 2, "spins": 12, "coins": 4, "reward": 1,
               "truncated": 0, "decisions": 5}
        result = summarize([row], 1.0, 2)
        self.assertEqual(result["std"], {"stage": 0.0, "spins": 0.0,
                                         "coins": 0.0, "reward": 0.0})
        self.assertEqual(result["mean_95_ci"]["reward"], [1.0, 1.0])
        self.assertGreater(result["win_rate_95_ci"][1], 0)


if __name__ == "__main__":
    unittest.main()
