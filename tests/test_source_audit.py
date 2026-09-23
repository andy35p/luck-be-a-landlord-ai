import copy
import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Optional model environment')
class SourceAuditTests(unittest.TestCase):
    def test_input_identity_excludes_label_but_preserves_candidate_order(self):
        from audit_aggregation_sources import input_key
        s=dict(scalars=[1],deck=[[1,0,0,0]],items=[],candidates=[[1,1,0,0],[1,2,0,0]],label=0,metadata={'source':'a'})
        other=copy.deepcopy(s);other['label']=1;other['metadata']['source']='b'
        self.assertEqual(input_key(s),input_key(other))
        other['candidates'].reverse()
        self.assertNotEqual(input_key(s),input_key(other))
        other=copy.deepcopy(s);other['deck'][0][0]=2
        self.assertNotEqual(input_key(s),input_key(other))
