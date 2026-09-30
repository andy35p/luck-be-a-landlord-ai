import json
from pathlib import Path
import unittest
from luck_agent.evaluation.live_board import displayed_ids

CASES=json.loads((Path(__file__).parent/'fixtures/live_board_trace.json').read_text(encoding='utf-8'))['cases']


class RealBoardTraceTests(unittest.TestCase):
    def test_row_order_matches_observed_screen_before_and_after_spin(self):
        expected=[
            [['empty','magpie','cherry','crab','anchor'],['hearts','empty','ninja','cherry','sand_dollar'],
             ['sapphire','flower','lockbox','cat','empty'],['pearl','empty','gambler','rain','coin']],
            [['cat','lockbox','coin','cherry','ninja'],['rain','gambler','magpie','crab','anchor'],
             ['sand_dollar','hearts','cherry','empty','empty'],['sapphire','flower','empty','empty','pearl']]]
        self.assertEqual([c['spin'] for c in CASES],[18,19])
        for case,rows in zip(CASES,expected):
            state=case['state'];inventory={s['instance_id']:s for s in state['symbols']}
            displayed=displayed_ids(state)
            self.assertEqual([inventory[i]['type'] for i in displayed],[s for row in rows for s in row])
            self.assertEqual(len(inventory),25)
            offboard=set(inventory)-set(displayed)
            self.assertEqual(len(offboard),5)
            self.assertTrue(all(inventory[i]['type']=='empty' for i in offboard))

    def test_instance_identity_survives_shuffle_and_timers_advance(self):
        before,after=[{s['instance_id']:s for s in c['state']['symbols']} for c in CASES]
        self.assertEqual(set(before),set(after))
        self.assertNotEqual(displayed_ids(CASES[0]['state']),displayed_ids(CASES[1]['state']))
        for uid,symbol in before.items():
            if symbol['type'] in ('magpie','gambler'):
                self.assertEqual(after[uid]['times_displayed'],symbol['times_displayed']+1)
