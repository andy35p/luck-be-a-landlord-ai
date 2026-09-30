import json
from pathlib import Path
import tempfile
import unittest
from tools.audit_timer_capture import audit


class TimerCaptureAuditTests(unittest.TestCase):
    def run_records(self, symbols):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'capture.jsonl'
            records=[{'session_id':'test','state':{'symbols':[s]}} for s in symbols]
            path.write_text('\n'.join(json.dumps(r) for r in records),encoding='utf-8')
            return audit([path])

    def test_old_display_text_does_not_supply_missing_timer(self):
        result=self.run_records([{'type':'magpie','instance_id':'one','displayed_text_value':'2'}])
        self.assertEqual(result['counts']['missing_timer_state'],1)
        self.assertEqual(result['missing_fields']['times_displayed'],1)
        self.assertNotIn('readable_timer_state',result['counts'])

    def test_raw_timer_changes_are_counted_per_instance(self):
        base={'type':'magpie','instance_id':'one','values':[9,4],'modded':False,'inherit_effects':False}
        result=self.run_records([dict(base,times_displayed=n) for n in (0,0,1,2,0)])
        self.assertEqual(result['counts']['readable_timer_state'],5)
        self.assertEqual(result['unique_instances'],1)
        self.assertEqual(result['instances_with_multiple_timer_values'],1)

    def test_missing_and_invalid_are_not_converted_to_zero(self):
        base={'type':'gambler','instance_id':'one','values':[1,2],'modded':False,'inherit_effects':False}
        result=self.run_records([dict(base,times_displayed=n) for n in (None,True,-1,'2')])
        self.assertEqual(result['counts']['invalid_timer_state'],4)
        self.assertNotIn('readable_timer_state',result['counts'])
