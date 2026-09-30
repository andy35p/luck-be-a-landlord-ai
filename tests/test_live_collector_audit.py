import copy
import unittest
from audit_live_collector import inspect_record


class LiveCollectorAuditTests(unittest.TestCase):
    def test_missing_flags_fail_closed_and_empty_slots_are_not_deck(self):
        r = {'kind': 'observation', 'state': {'symbols': [{'type': 'empty'}, {'type': 'cat'}],
             'cards': [{'active': True, 'data': {'type': 'coin'}}], 'items': [],
             'progress': {'current_floor': 1}, 'prompt': {'type': 'add_tile'},
             'ui': {'closed': False, 'delay_timer': 0, 'prompt_delay': 0},
             'board_status': {'effects_playing': False}}}
        result = inspect_record(r, {'cat', 'coin'}, set())
        self.assertTrue(result['readiness_hint'])
        self.assertEqual(result['nonempty_symbol_slots'], 1)
        self.assertEqual(result['scope_blockers'], [])
        for section, field in [('ui', 'closed'), ('ui', 'delay_timer'), ('ui', 'prompt_delay'),
                               ('board_status', 'effects_playing')]:
            changed = copy.deepcopy(r)
            del changed['state'][section][field]
            self.assertFalse(inspect_record(changed, {'cat', 'coin'}, set())['readiness_hint'])
        r['state']['progress']['current_floor'] = 20
        r['state']['symbols'].append({'type': 'dud'})
        result = inspect_record(r, {'cat', 'coin'}, set())
        self.assertEqual(result['scope_blockers'], ['floor_not_supported', 'symbols_not_supported'])
        r['kind'] = 'action_attempt'
        self.assertFalse(inspect_record(r, {'cat', 'coin'}, set())['readiness_hint'])
