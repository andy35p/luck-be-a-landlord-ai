import unittest
from luck_agent.evaluation.compare_reroll import paired_stats


class ComparisonTests(unittest.TestCase):
    def row(self, seed, stage, truncated=0):
        return {"seed":seed,"stage":stage,"truncated":truncated,"rerolls_used":1}

    def test_identical_policies_not_promoted(self):
        rows = [self.row(0,3), self.row(1,5)]
        stats = paired_stats(rows, rows, 1, 100)
        self.assertEqual(stats["paired_bootstrap_95"], [0,0])
        self.assertFalse(stats["promotable_on_development"])

    def test_positive_difference_and_truncation_gate(self):
        a = [self.row(0,3),self.row(1,3)]
        b = [self.row(0,4),self.row(1,4)]
        self.assertTrue(paired_stats(a,b,1,100)["promotable_on_development"])
        b[0]["truncated"] = 1
        self.assertFalse(paired_stats(a,b,1,100)["promotable_on_development"])

    def test_mismatched_seeds_rejected(self):
        with self.assertRaises(ValueError):
            paired_stats([self.row(0,3)],[self.row(1,3)],1,100)

    def test_adjusted_confidence_label_and_validation(self):
        rows = [self.row(0,3),self.row(1,4)]
        result = paired_stats(rows,rows,1,100,confidence=.975)
        self.assertEqual(result["confidence"],.975)
        self.assertNotIn("paired_bootstrap_95",result)
        self.assertEqual(result["paired_bootstrap_interval"],[0,0])
        with self.assertRaises(ValueError):
            paired_stats(rows,rows,1,100,confidence=1)
