import copy
import unittest
from test_live_advisor import observation
from luck_agent.agents.live_advisor import LiveAdvisor
from luck_agent.evaluation.live_collector_contract import collector_blockers


def current_record(seq=1):
    r=observation(seq);r['collector_version']='0.7.0'
    s=r['state'];s['symbols'][0].update(modded=False,inherit_effects=False)
    s['symbols'] += [{'type':'empty','instance_id':str(n),'modded':False,'inherit_effects':False} for n in range(19)]
    ids=[s['instance_id'] for s in s['symbols']]
    s['displayed_board']={'width':5,'height':4,'rows':[ids[i:i+5] for i in range(0,20,5)]}
    return r


class CollectorContractTests(unittest.TestCase):
    def test_current_complete_and_legacy_records_preserve_scoring(self):
        legacy=LiveAdvisor().update(observation(),fresh=True)
        r=current_record();before=copy.deepcopy(r)
        current=LiveAdvisor().update(r,fresh=True)
        self.assertEqual(current['status'],'ready')
        self.assertEqual(current['scores'],legacy['scores'])
        self.assertEqual(current['action'],legacy['action'])
        self.assertEqual(r,before)

    def test_incomplete_board_invalidates_ready_cache(self):
        advisor=LiveAdvisor();self.assertEqual(advisor.update(current_record(),fresh=True)['status'],'ready')
        r=current_record(2);r['state']['displayed_board']['rows'][0][0]='missing'
        result=advisor.update(r,fresh=True)
        self.assertIn('collector_board_displayed_symbol_missing_from_inventory',result['reasons'])
        self.assertIsNone(advisor.current()['action'])

    def test_rule_source_required_for_symbols_and_items(self):
        for collection in ('symbols','items'):
            for value in (True,None,'false',0):
                r=current_record();entry={'modded':value,'inherit_effects':False}
                if collection=='symbols':r['state'][collection][0].update(entry)
                else:r['state'][collection]=[entry]
                self.assertIn('collector_unverified_rule_source',collector_blockers(r))
        r=current_record();del r['state']['symbols'][0]['inherit_effects']
        self.assertIn('collector_unverified_rule_source',collector_blockers(r))

    def test_unknown_or_lost_version_does_not_bypass_new_checks(self):
        for version in ('0.8.0',None,{},'0.6.0'):
            r=current_record();r['collector_version']=version
            self.assertEqual(collector_blockers(r),['unsupported_collector_version'])
        r=current_record();del r['collector_version']
        self.assertEqual(collector_blockers(r),['collector_version_fields_mismatch'])
