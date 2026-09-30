import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from luck_agent.evaluation.advice_display import publish, display_message


class AdviceDisplayTests(unittest.TestCase):
    def test_busy_reader_preserves_old_file_then_retries_latest_state(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'advice.json'
            path.write_text('old')
            with patch('luck_agent.evaluation.advice_display.os.replace', side_effect=PermissionError):
                self.assertIsNone(publish(path, {'status':'ready','action':{'action_type':1}}))
            self.assertEqual(path.read_text(),'old')
            publish(path, {'status':'unavailable','reasons':['feed_stalled']})
            self.assertEqual(json.loads(path.read_text())['message'],'建议助手已离线')

    def test_sidecar_identity_and_atomic_replace(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'advice.json'
            result = {'status':'ready','session_id':'new','sequence':3,'state_revision':7,
                      'action':{'action_type':0,'target_id':'mouse'}}
            publish(path,result,{'session_id':'old','sequence':2},wall_clock=lambda:123)
            payload=json.loads(path.read_text())
            self.assertEqual(payload['session_id'],'new')
            self.assertEqual(payload['sequence'],3)
            self.assertEqual(payload['message'],'建议：选择老鼠')
            self.assertEqual(payload['schema'],2)
            self.assertEqual(payload['state_revision'],7)
            result['sequence']=4
            publish(path,result,wall_clock=lambda:124)
            self.assertEqual(json.loads(path.read_text())['state_revision'],7)
            self.assertNotIn('action',payload)
            self.assertFalse(path.with_suffix('.json.tmp').exists())
            publish(path,{'status':'unavailable','reasons':['feed_stalled']})
            self.assertEqual(json.loads(path.read_text())['message'],'建议助手已离线')

    def test_rejection_is_not_rendered_as_advice(self):
        self.assertIn('尚未支持',display_message({'status':'unavailable','reasons':['unsupported_symbol']}))
        self.assertEqual(display_message({'status':'ready','action':{'action_type':1}}),'建议：跳过')
