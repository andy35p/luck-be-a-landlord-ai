import unittest
from test_live_advisor import observation
from luck_agent.agents.live_advisor import LiveAdvisor
from luck_agent.evaluation.advice_display import display_message


class SimpleSymbolScopeTests(unittest.TestCase):
    def record(self,kind):
        r=observation()
        r['state']['cards']=[{'active':True,'data':{'type':x}} for x in (kind,'coin','flower')]
        r['state']['symbols'][0]['type']=kind
        return r

    def test_verified_base_two_symbols_use_existing_scoring(self):
        for kind,name in [('sapphire','蓝宝石'),('sand_dollar','沙钱')]:
            with self.subTest(symbol=kind):
                result=LiveAdvisor().update(self.record(kind),fresh=True)
                self.assertEqual(result['policy'],'restricted_heuristic_v3')
                self.assertEqual(result['scores'][kind],2)
                self.assertEqual(result['action']['target_id'],kind)
                self.assertIn(name,display_message(result))

    def test_full_deck_threshold_and_non_choice_remain_restricted(self):
        for kind in ('sapphire','sand_dollar'):
            r=self.record(kind)
            r['state']['symbols']=[dict(r['state']['symbols'][0],instance_id=str(i)) for i in range(20)]
            result=LiveAdvisor().update(r,fresh=True)
            self.assertEqual(result['action']['action_type'],0)
            self.assertEqual(result['action']['target_id'],kind)
            r['state']['cards']=[{'active':True,'data':{'type':x}} for x in ('coin','pearl','flower')]
            self.assertEqual(LiveAdvisor().update(r,fresh=True)['action']['action_type'],1)
            r['state']['prompt']['type']='remove'
            self.assertIsNone(LiveAdvisor().update(r,fresh=True)['action'])

    def test_items_growth_and_unknown_partners_still_rejected(self):
        for kind in ('sapphire','sand_dollar'):
            for mutate in (lambda s:s.update(items=[{'type':'egg_carton'}]),
                           lambda s:s['symbols'][0].update(permanent_bonus=1),
                           lambda s:s['symbols'].append(dict(s['symbols'][0],type='geologist',instance_id='other'))):
                r=self.record(kind); mutate(r['state'])
                self.assertEqual(LiveAdvisor().update(r,fresh=True)['status'],'unavailable')
