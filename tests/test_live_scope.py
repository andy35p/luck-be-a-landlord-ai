import copy
import json
from pathlib import Path
import tempfile
import unittest

from audit_live_scope import audit
from test_live_advisor import observation


class LiveScopeTests(unittest.TestCase):
    def test_heartbeat_dedup_controlled_exclusion_and_malformed(self):
        base=observation()
        base['state']['progress'].update(spins=1,times_rent_paid=0)
        repeated=copy.deepcopy(base); repeated['sequence']=2
        controlled=copy.deepcopy(base); controlled['test_fixture']='fixture'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'records.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in [base,repeated,controlled])+ '\ninvalid\n',encoding='utf-8')
            result=audit([path,path])
        self.assertEqual(result['counts']['unique_symbol_decisions'],1)
        self.assertEqual(result['counts']['policy_ready'],1)
        self.assertEqual(result['counts']['controlled_excluded'],2)
        self.assertEqual(result['counts']['malformed'],2)

    def test_blockers_count_per_decision_not_per_instance(self):
        record=observation()
        record['state']['progress'].update(spins=1,times_rent_paid=0)
        record['state']['items']=[{'type':'egg_carton'}]
        record['state']['symbols']=[dict(record['state']['symbols'][0],type='crow',instance_id=str(i)) for i in range(3)]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'records.jsonl'; path.write_text(json.dumps(record)+'\n')
            result=audit([path])
        self.assertEqual(result['unsupported_inventory_symbols'],{'crow':1})
        self.assertEqual(result['owned_items'],{'egg_carton':1})
        self.assertEqual(result['counts']['policy_rejected'],1)
