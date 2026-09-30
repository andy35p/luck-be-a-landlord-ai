import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Optional PyTorch required')
class SpatialFitTests(unittest.TestCase):
    def test_selection_is_order_independent_disjoint_and_rejects_duplicates(self):
        from diagnose_spatial_fit import select_samples, sample_group
        from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
        enc = SpatialCandidateEncoder()
        def sample(seed, target, partner, size):
            return {'metadata': {'seed': seed, 'step': 1, 'decision_type': 'symbol',
                                  'actions': [{'action_type': 0, 'target_id': target}]},
                    'label': 0, 'candidates': [[1], [2]],
                    'deck': [[enc.symbols[partner], 0, 0, 0]] + [[enc.symbols['coin'], 0, 0, 0]]*(size-1)}
        rows = [sample(i, target, partner, size) for i in range(8)
                for target, partner, size in [('mouse','cheese',18)] ]
        rows += [sample(10+i,'cheese','mouse',18) for i in range(8)]
        rows += [sample(20+i,'coin','coin',18) for i in range(8)]
        rows += [sample(30+i,'coin','coin',10) for i in range(8)]
        self.assertEqual(sample_group(rows[0]), 'mouse_with_cheese')
        selected, index = select_samples(rows, 2)
        self.assertEqual(index, select_samples(list(reversed(rows)), 2)[1])
        self.assertEqual(len(selected), 8)
        self.assertEqual(len({(r['seed'],r['step']) for r in index}), 8)
        with self.assertRaises(ValueError): select_samples(rows + rows[:1], 2)
        with self.assertRaises(ValueError): select_samples(rows[:8], 2)
