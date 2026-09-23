import math
import unittest
from luck_agent.evaluation.bc_contract import masked_bc_metrics, decision_mask


class BCContractTests(unittest.TestCase):
    def test_padding_excluded_and_forced_rows_not_in_denominator(self):
        result = masked_bc_metrics([[0, 0, float("inf")], [0, 999, 999]], [1, 0],
                                   [[True, True, False], [True, False, False]])
        self.assertAlmostEqual(result["mean_nll"], math.log(2))
        self.assertEqual(result["decision_count"], 1)
        self.assertEqual(result["forced_count"], 1)
        self.assertEqual(result["decision_accuracy"], 0)

    def test_empty_decision_batch_undefined_metrics(self):
        result = masked_bc_metrics([[5]], [0], [[True]])
        self.assertIsNone(result["mean_nll"])
        self.assertIsNone(result["decision_accuracy"])
        self.assertEqual(decision_mask([[True], [True, True, False]]), [False, True])

    def test_large_logits_and_permutation(self):
        a = masked_bc_metrics([[10000, 9999]], [0], [[True, True]])
        b = masked_bc_metrics([[9999, 10000]], [1], [[True, True]])
        self.assertEqual(a, b)
        self.assertAlmostEqual(a["mean_nll"], math.log1p(math.exp(-1)))

    def test_invalid_labels_and_nonfinite_legal_logits_rejected(self):
        for scores, label, mask in [([1, 2], 1, [True, False]), ([float("nan")], 0, [True]), ([0], 0, [False])]:
            with self.assertRaises(ValueError): masked_bc_metrics([scores], [label], [mask])
