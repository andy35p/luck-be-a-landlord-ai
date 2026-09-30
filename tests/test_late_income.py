import unittest
from audit_late_income import spin_accounting, summarize_spins


class LateIncomeTests(unittest.TestCase):
    def test_payouts_count_once_and_maturation_has_no_same_spin_diamond_income(self):
        r={'state':{'rent_stage':0,'coins':20,'current_rent':25,'spins_until_rent':1},
           'next_state':{'spin_count':5,'last_spin_income':8,'visible_board_instances':[
               {'instance_id':'a','symbol_id':'diamond'},{'instance_id':'b','symbol_id':'diamond'},
               {'instance_id':'c','symbol_id':'coal'}]},
           'info':{'instance_events':[{'type':'payout','instance_id':'a','amount':4},
               {'type':'payout','instance_id':'b','amount':4},{'type':'payout','instance_id':'c','amount':0},
               {'type':'transform','instance_id':'c','reason':'coal_matured'}]}}
        s=spin_accounting(r)
        self.assertEqual(s['diamond_synergy'],2)
        self.assertEqual(s['matured'],1)
        self.assertEqual(s['rent_margin'],3)
        self.assertEqual(summarize_spins([s])['diamond_income'],8)
        self.assertEqual(s['coal_derived_diamond_income'],0)
        self.assertEqual(spin_accounting(r,{'a','c'})['coal_derived_diamond_income'],4)
        r['next_state']['last_spin_income']=9
        with self.assertRaises(ValueError):spin_accounting(r)

    def test_empty_summary(self):
        self.assertEqual(summarize_spins([])['diamond_income_share'],0)
