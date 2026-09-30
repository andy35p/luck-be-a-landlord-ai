import unittest
from diagnose_baseline_failures import first_divergence, episode_summary


class FailureDiagnosisTests(unittest.TestCase):
    def test_first_action_difference_requires_same_state(self):
        a={'step':0,'state':{'candidates':['a']},'legal_actions':[1,2],'action':1}
        b={**a,'action':2}
        self.assertTrue(first_divergence([a],[b])['same_state'])
        b['state']={'candidates':['b']}
        self.assertFalse(first_divergence([a],[b])['same_state'])
        self.assertIsNone(first_divergence([a],[a]))

    def test_rent_margin_uses_income_before_rent_payment(self):
        for passed in (True,False):
            before={'spin_count':4,'spins_until_rent':1,'coins':20,'current_rent':25,'rent_stage':0}
            income=7 if passed else 3
            after={'spin_count':5,'last_spin_income':income,'coins':2 if passed else 23,
                   'rent_stage':int(passed),'symbols':[]}
            record={'episode_seed':0,'step':0,'state':before,'next_state':after,
                    'action':{'action_type':7},'info':{}}
            result=episode_summary([record],{})
            self.assertEqual(result['rents'][0]['margin'],2 if passed else -2)
            self.assertEqual(result['rents'][0]['passed'],passed)
