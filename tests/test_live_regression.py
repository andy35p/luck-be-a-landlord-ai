"""Replay projected real-game snapshots without connecting to a running game."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from luck_agent.agents.live_advisor import LiveAdvisor
from luck_agent.evaluation.live_feed import LiveFeed
from luck_agent.evaluation.live_observation import observe_symbol_choice


CASES = {c['id']: c for c in json.loads(
    (Path(__file__).parent/'fixtures/live_records.json').read_text(encoding='utf-8'))['cases']}


class RealSnapshotRegressionTests(unittest.TestCase):
    def test_historical_cases_never_become_live_advice(self):
        for label, case in CASES.items():
            with self.subTest(case=label):
                self.assertEqual(LiveAdvisor().update(case['record'])['reasons'],
                                 ['live_freshness_unconfirmed'])

    def test_current_scope_rejects_every_natural_case(self):
        for label, case in CASES.items():
            if case['provenance']['controlled']:
                continue
            with self.subTest(case=label):
                original = copy.deepcopy(case['record'])
                # Explicit offline policy-unit evaluation, not freshness evidence.
                result = LiveAdvisor().update(case['record'], fresh=True)
                self.assertEqual(result['status'], 'unavailable')
                self.assertIsNone(result['action'])
                self.assertEqual(case['record'], original)
                if label != 'natural_choice':
                    self.assertFalse(observe_symbol_choice(case['record'])['readiness_hint'])

    def test_controlled_positive_cases_keep_provenance_and_synergy(self):
        for label, target in [('controlled_cheese', 'cheese'), ('controlled_mouse', 'mouse')]:
            case = CASES[label]
            self.assertTrue(case['provenance']['controlled'])
            self.assertEqual(case['record']['test_fixture'], 'controlled-choice-v080')
            result = LiveAdvisor(allow_test_fixtures=True).update(case['record'], fresh=True)
            self.assertEqual(result['action']['target_id'], target)
        self.assertEqual(result['scores']['mouse'], 2.8)

    def test_real_choice_followed_by_rent_invalidates_cached_action(self):
        advisor = LiveAdvisor(allow_test_fixtures=True)
        self.assertEqual(advisor.update(CASES['controlled_mouse']['record'], fresh=True)['status'], 'ready')
        result = advisor.update(CASES['rent_due']['record'], fresh=True)
        self.assertIn('not_ordinary_symbol_choice', result['reasons'])
        self.assertIsNone(advisor.current()['action'])

    def test_success_failure_and_item_transitions(self):
        state = lambda name: CASES[name]['record']['state']
        before, after = state('rent_due'), state('rent_increase')
        self.assertEqual(before['economy']['coins']-after['economy']['coins'], 150)
        self.assertEqual(after['progress']['times_rent_paid']-before['progress']['times_rent_paid'], 1)
        self.assertEqual(after['progress']['rent_values'], [225, 7])
        failed = state('game_over')
        self.assertLess(failed['economy']['coins'], failed['progress']['rent_values'][0])
        self.assertEqual(failed['prompt']['type'], 'game_over')
        self.assertNotIn('yellow_pepper', [i['type'] for i in state('item_choice')['items']])
        self.assertIn('yellow_pepper', [i['type'] for i in state('item_owned')['items']])

    def test_positive_historical_record_appended_to_live_feed_is_stale(self):
        record = CASES['controlled_mouse']['record']
        with tempfile.TemporaryDirectory() as folder:
            feed = LiveFeed(folder, wall_clock=lambda:record['captured_unix_seconds']+100)
            (Path(folder)/'history.jsonl').write_text(json.dumps(record)+'\n', encoding='utf-8')
            self.assertEqual(feed.poll()['reasons'], ['missing_or_stale_capture_time'])
