import json
from pathlib import Path
import unittest
from luck_agent.evaluation.live_board import displayed_ids
from luck_agent.evaluation.live_timer_state import parse_timer

FIXTURE=json.loads((Path(__file__).parent/'fixtures/controlled_timer_trace.json').read_text(encoding='utf-8'))


class ControlledOffboardTimerTests(unittest.TestCase):
    def test_real_nonempty_offboard_instances_do_not_increment(self):
        self.assertEqual(FIXTURE['test_fixture'],'controlled-timer-v103')
        cases=FIXTURE['cases']
        self.assertEqual([c['spin'] for c in cases],[18,19,20])
        for before,after in zip(cases,cases[1:]):
            old={s['instance_id']:parse_timer(s) for s in before['state']['symbols']}
            new={s['instance_id']:parse_timer(s) for s in after['state']['symbols']}
            shown=set(displayed_ids(after['state']))
            self.assertEqual(set(old),set(new))
            self.assertEqual(len(new),25)
            self.assertEqual(len(set(new)-shown),5)
            for uid,symbol in new.items():
                self.assertEqual(symbol.symbol_type,'magpie')
                self.assertEqual(symbol.times_displayed,old[uid].times_displayed+int(uid in shown))

    def test_offboard_instances_can_reenter_with_retained_state(self):
        before,after=FIXTURE['cases'][1:]
        entering=set(displayed_ids(after['state']))-set(displayed_ids(before['state']))
        self.assertEqual(len(entering),5)
        old={s['instance_id']:s['times_displayed'] for s in before['state']['symbols']}
        new={s['instance_id']:s['times_displayed'] for s in after['state']['symbols']}
        self.assertTrue(all(old[i]==0 and new[i]==1 for i in entering))
