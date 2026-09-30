import copy
import json
from pathlib import Path
import unittest

from test_live_advisor import observation
from luck_agent.agents.live_advisor import LiveAdvisor
from luck_agent.evaluation.live_item_scope import item_scope_blockers


ITEMS = json.loads((Path(__file__).parent/'fixtures/live_items.json').read_text(encoding='utf-8'))['items']


class LiveItemScopeTests(unittest.TestCase):
    def test_observed_items_with_synthetic_decks_preserve_preferences(self):
        # Item state is real; these assembled decks are deliberately synthetic.
        for kind in sorted(LiveAdvisor.supported):
            r = observation()
            kinds = [kind] + [s for s in ('coin','pearl','flower') if s != kind][:2]
            r['state']['cards'] = [{'active':True,'data':{'type':s}} for s in kinds]
            baseline = LiveAdvisor().update(r, fresh=True)
            for items in ([ITEMS[0]], [ITEMS[1]], ITEMS):
                r['state']['items'] = copy.deepcopy(items)
                original = copy.deepcopy(r)
                result = LiveAdvisor().update(r, fresh=True)
                self.assertEqual(result['status'], 'ready')
                self.assertEqual(result['action'], baseline['action'])
                self.assertEqual(result['scores'], baseline['scores'])
                self.assertEqual(r, original)

    def test_missing_or_altered_observed_fields_reject(self):
        required = ('type','instance_id','values','item_count','saved_value','saved_values',
                    'value','destroy_counters','active','destroyed','destroyable','symbol_trigger')
        for original in ITEMS:
            for field in required:
                item = copy.deepcopy(original); del item[field]
                with self.subTest(item=original['type'], missing=field):
                    self.assertTrue(item_scope_blockers([item], ['coin']))
            for field, value in [('values',[True]), ('item_count',2), ('saved_value',True),
                                 ('saved_value',7), ('active',True), ('value',1),
                                 ('destroy_counters',1), ('saved_values',{'unknown':1})]:
                item = copy.deepcopy(original); item[field] = value
                self.assertTrue(item_scope_blockers([item], ['coin']))

    def test_effectful_partners_and_item_stacking_reject(self):
        for kind in ('egg','magpie','geologist','unknown'):
            self.assertTrue(item_scope_blockers(ITEMS, ['coin',kind]))
            r = observation(); r['state']['items'] = copy.deepcopy(ITEMS)
            r['state']['cards'][0]['data']['type'] = kind
            self.assertEqual(LiveAdvisor().update(r,fresh=True)['status'],'unavailable')
        for item in ITEMS:
            second = dict(item,instance_id='duplicate-kind')
            self.assertTrue(item_scope_blockers([item, second], ['coin']))

    def test_egg_storage_bounds_and_negative_symbol_policy_are_explicit(self):
        egg = next(i for i in ITEMS if i['type']=='egg_carton')
        for count in range(7):
            self.assertEqual(item_scope_blockers([dict(egg,saved_value=count)], ['coin']), [])
        self.assertTrue(item_scope_blockers([dict(egg,saved_value=-1)], ['coin']))
        tax = next(i for i in ITEMS if i['type']=='tax_evasion')
        self.assertTrue(item_scope_blockers([dict(tax,saved_value=1)], ['coin']))
