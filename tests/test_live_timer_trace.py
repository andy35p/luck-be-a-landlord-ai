import json
from pathlib import Path
import tempfile
import unittest
from tools.audit_timer_capture import audit

TRACE = json.loads((Path(__file__).parent/'fixtures/live_timer_trace.json').read_text(encoding='utf-8'))


class LiveTimerTraceTests(unittest.TestCase):
    def test_real_spin_progression_and_period_reset(self):
        rows = TRACE['trace']
        self.assertEqual([r['spin'] for r in rows], [18,19,20])
        self.assertEqual([r['coins'] for r in rows], [54,74,102])
        for kind, expected in [('magpie',[2,3,0]),('gambler',[5,6,7])]:
            symbols = [next(s for s in r['symbols'] if s['type']==kind) for r in rows]
            self.assertEqual([s['times_displayed'] for s in symbols], expected)
            self.assertTrue(all(s['modded'] is False and s['inherit_effects'] is False for s in symbols))
            self.assertTrue(all(0 <= s['grid_position'][0] < 5 and 0 <= s['grid_position'][1] < 4 for s in symbols))
        self.assertTrue(all(a['sequence'] < b['sequence'] and a['ticks_ms'] < b['ticks_ms']
                            for a,b in zip(rows,rows[1:])))

    def test_real_variable_length_values_are_readable_without_guessing(self):
        rows = TRACE['trace']
        self.assertEqual([len(next(s for s in r['symbols'] if s['type']=='magpie')['values']) for r in rows], [4,2,2])
        records=[]
        for row in rows:
            symbols=[dict(s,instance_id=s['type']) for s in row['symbols']]
            records.append({'session_id':'fixture','state':{'symbols':symbols}})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trace.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in records),encoding='utf-8')
            result=audit([path])
        self.assertEqual(result['counts']['readable_timer_state'],6)
        self.assertEqual(result['counts']['verified_format_timer_state'],6)
        self.assertEqual(result['format_rejections'],{})
        self.assertEqual(result['instances_with_multiple_timer_values'],2)
        self.assertEqual(result['missing_fields'],{})
