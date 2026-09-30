import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'),'Optional PyTorch required')
class SpatialCoverageTests(unittest.TestCase):
    def test_bucket_boundaries(self):
        from audit_spatial_coverage import deck_band,partner_band
        self.assertEqual([deck_band(n) for n in (0,17,18,19,20,24,25)],['<18','<18','18-19','18-19','20-24','20-24','25+'])
        self.assertEqual([partner_band(n) for n in (0,1,2,3,4)],['0','1','2-3','2-3','4+'])

    def test_partner_counts_use_deck_not_last_board(self):
        from audit_spatial_coverage import groups_for
        from luck_agent.agents.heuristic_agent import HeuristicAgent
        state={'symbols':[{'symbol_id':'mouse'}]*4,'visible_board':['mouse'],
               'rent_stage':6,'items':[],'coins':50,'current_rent':100,'candidates':['cheese','coal','coin']}
        groups=groups_for(state,{'action_type':0,'target_id':'cheese'},HeuristicAgent())
        self.assertIn(('synergy','cheese:4+'),groups)
        self.assertIn(('synergy_margin','>1'),groups)
