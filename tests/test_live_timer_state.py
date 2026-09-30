import copy
import json
from pathlib import Path
import unittest

from luck_agent.evaluation.live_timer_state import parse_timer

TRACE=json.loads((Path(__file__).parent/'fixtures/live_timer_trace.json').read_text(encoding='utf-8'))['trace']


class LiveTimerStateTests(unittest.TestCase):
    def test_real_trace_preserves_counts_and_raw_values(self):
        for row in TRACE:
            for symbol in row['symbols']:
                before=copy.deepcopy(symbol)
                parsed=parse_timer(symbol)
                self.assertEqual(parsed.times_displayed,symbol['times_displayed'])
                self.assertEqual(parsed.raw_values,tuple(symbol['values']))
                self.assertEqual(parsed.parameters,tuple(symbol['values'][:2]))
                self.assertEqual(symbol,before)

    def test_display_text_never_reconstructs_missing_state(self):
        source=TRACE[0]['symbols'][0]
        for field in ('times_displayed','values','modded','inherit_effects'):
            symbol=copy.deepcopy(source);symbol.pop(field);symbol['displayed_text_value']='2'
            with self.subTest(field=field), self.assertRaises(ValueError):parse_timer(symbol)

    def test_changed_parameters_and_nonzero_padding_rejected(self):
        source=TRACE[0]['symbols'][0]
        for values in ([9,3],[10,4],[9,4,0],[9,4,0,1],[9,4,0,0,0],
                       [9.0,4],[True,4],None,'9,4'):
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_timer(dict(source,values=values))

    def test_bad_counts_and_changed_rule_source_rejected(self):
        source=TRACE[0]['symbols'][0]
        for changes in ({'times_displayed':True},{'times_displayed':-1},
                        {'times_displayed':2.0},{'times_displayed':None},
                        {'modded':True},{'inherit_effects':True},{'type':'owl'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_timer(dict(source,**changes))
        # Raw parsing must not silently wrap transient or accumulated counters.
        self.assertEqual(parse_timer(dict(source,times_displayed=4)).times_displayed,4)
