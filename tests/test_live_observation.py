import copy
import unittest
from luck_agent.evaluation.live_observation import observe_symbol_choice


class LiveObservationTests(unittest.TestCase):
    def record(self):
        return {'session_id': 'test', 'sequence': 1, 'kind': 'observation', 'state': {
            'prompt': {'type': 'add_tile', 'prompt': False},
            'cards': [{'active': True, 'data': {'type': 'cat'}}],
            'symbols': [{'type': 'empty'}, {'type': 'cat'}],
            'ui': {'closed': False, 'locked_in_position': True, 'delay_timer': -2, 'prompt_delay': 300},
            'board_status': {'effects_playing': False},
            'input_context': {'options_visible': False, 'title_visible': False, 'window_focused': True}}}

    def test_normal_prompt_delay_not_required_to_be_zero(self):
        r = self.record()
        result = observe_symbol_choice(r)
        self.assertTrue(result['readiness_hint'])
        self.assertEqual(len(result['nonempty_symbols']), 1)
        self.assertIsNone(result['recommendation'])
        r['sequence'] += 1
        self.assertNotEqual(result['observation_id'], observe_symbol_choice(r)['observation_id'])

    def test_context_fail_closed_and_no_input_mutation(self):
        for field in ('options_visible', 'title_visible', 'window_focused'):
            r = self.record()
            del r['state']['input_context'][field]
            original = copy.deepcopy(r)
            self.assertFalse(observe_symbol_choice(r)['readiness_hint'])
            self.assertEqual(r, original)
        for field in ('closed', 'locked_in_position'):
            r = self.record()
            del r['state']['ui'][field]
            self.assertFalse(observe_symbol_choice(r)['readiness_hint'])

    def test_action_attempt_and_inactive_card_rejected(self):
        r = self.record()
        r['kind'] = 'action_attempt'
        self.assertFalse(observe_symbol_choice(r)['readiness_hint'])
        r = self.record()
        r['state']['cards'][0]['active'] = False
        self.assertFalse(observe_symbol_choice(r)['readiness_hint'])
