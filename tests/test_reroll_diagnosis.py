import unittest
from luck_agent.evaluation.diagnose_reroll import classify, distribution


class DiagnosisTests(unittest.TestCase):
    def test_exclusive_reasons_and_threshold_equality(self):
        for gain,lower,expected in ((0,-1,"no_positive_mean_gain"),(.5,.4,"blocked_by_cost"),
                                    (1,.5,"blocked_by_uncertainty"),(1,.6,"reroll")):
            self.assertEqual(classify({"current_utility":0,"expected_offer_utility":gain,
                                      "token_cost_proxy":.5,"conservative_gain":lower}),expected)

    def test_empty_and_single_distribution(self):
        self.assertEqual(distribution([]),{"count":0})
        self.assertEqual(distribution([2])["median"],2)
