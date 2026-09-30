import copy
import unittest
from luck_agent.agents.live_advisor import LiveAdvisor


def observation(seq=1, session='live'):
    return {'schema_version': '0.2', 'session_id': session, 'sequence': seq, 'ticks_ms': seq*250,
        'kind': 'observation', 'state': {
            'prompt': {'type': 'add_tile', 'prompt': False},
            'cards': [{'active': True, 'data': {'type': s}} for s in ('mouse', 'coin', 'flower')],
            'symbols': [{'type': 'cheese', 'instance_id': 's1', 'destroyed': False,
                         'being_destroyed': False, 'permanent_bonus': 0, 'permanent_multiplier': 1}],
            'items': [], 'progress': {'current_floor': 1, 'hex_of_emptiness_trigger': False,
                                      'hex_of_hoarding_trigger': False},
            'buttons': [{'active': True, 'disabled': False, 'call': 'resolve_event', 'args': ['skip']}],
            'ui': {'closed': False, 'locked_in_position': True},
            'board_status': {'effects_playing': False},
            'input_context': {'window_focused': True, 'options_visible': False, 'title_visible': False}}}


class LiveAdvisorTests(unittest.TestCase):
    def test_reuses_synergy_and_does_not_mutate_or_expose_cache(self):
        advisor = LiveAdvisor(); r = observation(); original = copy.deepcopy(r)
        result = advisor.update(r, fresh=True)
        self.assertEqual(result['action']['target_id'], 'mouse')
        self.assertEqual(r, original)
        result['action']['target_id'] = 'bad'
        self.assertEqual(advisor.current()['action']['target_id'], 'mouse')

    def test_expiry_and_duplicate_cannot_extend_lifetime(self):
        now = [0.0]; advisor = LiveAdvisor(clock=lambda: now[0])
        advisor.update(observation(), fresh=True); now[0] = 2
        self.assertEqual(advisor.current()['reasons'], ['expired'])
        self.assertEqual(advisor.update(observation(), fresh=True)['status'], 'unavailable')

    def test_focus_change_invalidates_and_new_session_retires_old(self):
        advisor = LiveAdvisor(); advisor.update(observation(), fresh=True)
        r = observation(2); r['state']['input_context']['window_focused'] = False
        self.assertIsNone(advisor.update(r, fresh=True)['action'])
        self.assertEqual(advisor.update(observation(1, 'new'), fresh=True)['status'], 'ready')
        self.assertEqual(advisor.update(observation(3), fresh=True)['reasons'], ['retired_session'])

    def test_scope_unknown_and_malformed_invalidate(self):
        for mutate in (lambda s: s['progress'].update(current_floor=20),
                       lambda s: s.update(items=[{'type': 'tax_evasion'}]),
                       lambda s: s['cards'][0]['data'].update(type='coal'),
                       lambda s: s['symbols'][0].update(permanent_bonus=1),
                       lambda s: s.pop('symbols'), lambda s: s.update(buttons=[])):
            advisor = LiveAdvisor(); advisor.update(observation(), fresh=True)
            r = observation(2); mutate(r['state'])
            self.assertEqual(advisor.update(r, fresh=True)['status'], 'unavailable')
            self.assertIsNone(advisor.current()['action'])
        self.assertEqual(LiveAdvisor().update({'bad': 1}, fresh=True)['status'], 'unavailable')

    def test_history_rejected_by_default_and_observed_skip_only(self):
        advisor = LiveAdvisor()
        self.assertEqual(advisor.update(observation())['reasons'], ['live_freshness_unconfirmed'])
        r = observation()
        r['state']['symbols'] = [dict(r['state']['symbols'][0], type='coin', instance_id=str(i)) for i in range(20)]
        r['state']['cards'] = [{'active': True, 'data': {'type': 'coin'}}]
        self.assertEqual(advisor.update(r, fresh=True)['action']['action_type'], 1)
