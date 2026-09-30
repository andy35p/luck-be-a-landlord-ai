import csv
import json
import tempfile
import unittest
from pathlib import Path
from compare_baselines import compare, load_run


class BaselineAuditTests(unittest.TestCase):
    def write(self,path,seeds=(1,2),revision=1):
        path.mkdir()
        manifest={'seed_start':1,'games':2,'effective_env_config':{},
                  'rule_identity':{'revision':revision},'source_hash':'a',
                  'effective_catalog_hash':'b','agent':'fixture'}
        (path/'manifest.json').write_text(json.dumps(manifest))
        with (path/'episodes.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['seed','won','stage','spins','coins','reward','decisions','truncated','rerolls_used'])
            writer.writeheader()
            for seed in seeds:
                writer.writerow(dict(seed=seed,won=0,stage=2,spins=10,coins=5,reward=-50,decisions=20,truncated=0,rerolls_used=0))

    def test_equal_runs_and_no_promotion_claim(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b';self.write(a);self.write(b)
            result=compare(a,b,samples=20)
            self.assertEqual(result['paired']['paired_bootstrap_95'],[0,0])
            self.assertNotIn('promotable_on_development',result['paired'])
            self.assertEqual(len(result['failure_seeds']),2)

    def test_rule_mismatch_and_duplicate_seeds_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b';c=Path(d)/'c'
            self.write(a);self.write(b,revision=2);self.write(c,seeds=(1,1))
            with self.assertRaises(ValueError):compare(a,b,samples=20)
            with self.assertRaises(ValueError):load_run(c)
