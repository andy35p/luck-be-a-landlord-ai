import json
from pathlib import Path
import tempfile
import unittest
from test_live_advisor import observation
from luck_agent.agents.live_advisor import LiveAdvisor
from luck_agent.evaluation.live_feed import LiveFeed


class FixtureIsolationTests(unittest.TestCase):
    def test_marker_presence_rejects_and_invalidates_previous_advice(self):
        for fields in ({'test_fixture':'controlled'}, {'test_fixture':None}, {'fixture_applied':False}):
            advisor=LiveAdvisor()
            self.assertEqual(advisor.update(observation(),fresh=True)['status'],'ready')
            record=observation(2);record.update(fields)
            self.assertEqual(advisor.update(record,fresh=True)['reasons'],['controlled_test_record'])
            self.assertIsNone(advisor.current()['action'])

    def test_explicit_offline_opt_in_retains_controlled_provenance(self):
        record=observation();record['test_fixture']='controlled-choice-v080'
        result=LiveAdvisor(allow_test_fixtures=True).update(record,fresh=True)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['test_fixture'],record['test_fixture'])
        self.assertIn('Controlled test only',result['scope'])
        with self.assertRaises(ValueError):LiveAdvisor(allow_test_fixtures='yes')

    def test_live_feed_never_enables_fixture_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            feed=LiveFeed(folder,wall_clock=lambda:1000)
            record=observation();record.update(test_fixture='controlled',captured_unix_seconds=1000)
            (Path(folder)/'test.jsonl').write_text(json.dumps(record)+'\n',encoding='utf-8')
            self.assertEqual(feed.poll()['reasons'],['controlled_test_record'])
