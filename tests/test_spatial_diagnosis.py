import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'),'Optional PyTorch required')
class SpatialDiagnosisTests(unittest.TestCase):
    def test_directions_and_teacher_ties(self):
        from diagnose_spatial_bc import classify
        from luck_agent.agents.heuristic_agent import HeuristicAgent
        teacher=HeuristicAgent()
        state={'symbols':[],'coins':0,'items':[],'current_rent':25}
        def a(t,target=None):return {'action_type':t,'target_id':target,'secondary_target_id':None}
        self.assertEqual(classify(state,a(0,'coin'),a(1),teacher),'model_skips_teacher_pick')
        self.assertEqual(classify(state,a(1),a(0,'coin'),teacher),'model_picks_teacher_skip')
        self.assertEqual(classify(state,a(4,'id'),a(8),teacher),'model_misses_removal')
        self.assertEqual(classify(state,a(8),a(4,'id'),teacher),'model_adds_removal')
        self.assertEqual(classify(state,a(0,'coin'),a(0,'flower'),teacher),'equal_teacher_score')
        self.assertEqual(classify(state,a(0,'coal'),a(0,'coin'),teacher),'lower_teacher_score')
