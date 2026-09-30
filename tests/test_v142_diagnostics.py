"""Diagnostic math and boundaries; no new seeds or policy fitting."""
import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Model runtime required')
class V142DiagnosticsTests(unittest.TestCase):
    def test_support_identity_and_monotonic_distances(self):
        from tools.analyze_bc_errors import support_similarity
        state=dict(histogram={'mouse':3,'cheese':2},items=['undertaker'],rent_stage=8,
                   deck_size=5,rent_pressure=.25)
        self.assertAlmostEqual(support_similarity(state,state)[0],1)
        for field,value in [('histogram',{'coin':5}),('items',[]),('rent_stage',12),
                            ('deck_size',20),('rent_pressure',2)]:
            changed={**state,field:value}
            self.assertLess(support_similarity(state,changed)[0],1)

    def test_schedule_boundaries(self):
        from tools.analyze_bc_errors import bucket
        self.assertEqual([bucket(s) for s in (0,5,6,9,10,12)],
                         ['early','early','mid','mid','late','late'])

    def test_candidate_set_is_order_independent(self):
        from tools.analyze_bc_errors import candidate_key
        actions=[dict(action_type=0,target_id='mouse'),dict(action_type=1,target_id=None)]
        self.assertEqual(candidate_key(actions),candidate_key(actions[::-1]))
        self.assertNotEqual(candidate_key(actions),candidate_key(actions[:1]))

    def test_context_audit_detects_unobserved_timer_assignment_loss(self):
        from tools.analyze_bc_errors import model_context_signature
        sample=dict(scalars=[0]*8,deck=[[1,0,1,1],[2,0,2,1]],items=[],
                    candidates=[[1,1,0,0]],board=[[0]*5 for _ in range(20)],
                    board_mask=[False]*20,board_observed=False)
        swapped={**sample,'deck':[[1,0,2,1],[2,0,1,1]]}
        self.assertEqual(model_context_signature(sample),model_context_signature(swapped))
        pointed={**sample,'candidates':[[5,1,0,1]]}
        other={**swapped,'candidates':[[5,1,0,1]]}
        self.assertNotEqual(model_context_signature(pointed),model_context_signature(other))
