"""V147 provenance, paired statistics and strict offline candidate gate."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.validate_multiseed_budget import bootstrap, sha

OUT=ROOT/'logs/v147-generalization'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

class V147Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=read(ROOT/'configs/v147_multiseed_generalization.json')
        cls.analysis=read(OUT/'analysis.json')

    def test_preregistered_grid_and_no_test_metrics(self):
        a=self.analysis;c=self.config
        self.assertEqual(c['budgets'],[200,300,500,750,1000]);self.assertEqual(len(set(c['training_seeds'])),5)
        self.assertEqual(a['registry']['config_sha256'],sha(ROOT/'configs/v147_multiseed_generalization.json'))
        self.assertEqual(a['registry']['manifest_sha256'],sha(ROOT/'logs/v128-magpie-shards/manifest.json'))
        self.assertEqual(a['test_metrics'],'SEALED')
        self.assertEqual(len(a['seed_rows']),25)
        self.assertTrue(all(r['parameters']==28785 and r['test_metrics']=='SEALED'
                            for r in (read(OUT/'seed_summaries'/str(seed)/'run.json') for seed in c['training_seeds'])))

    def test_reused_continuations_exact(self):
        for seed in (123,456,789):
            run=read(OUT/'seed_summaries'/str(seed)/'run.json')
            self.assertTrue(run['budgets']['200']['checkpoint']['exact_weights'])
            self.assertTrue(run['budgets']['500']['checkpoint']['exact_weights'])
        run=read(OUT/'seed_summaries/123/run.json')
        self.assertTrue(run['budgets']['1000']['checkpoint']['exact_weights'])
        self.assertEqual(run['budgets']['200']['metrics']['train']['symbol']['correct'],2072)

    def test_paired_comparison_not_unpaired_means(self):
        a=self.analysis;rows={(r['seed'],r['updates']):r for r in a['seed_rows']}
        for pair in a['paired_comparison']:
            vals=[rows[(s,pair['higher'])]['val_symbol_fit']-rows[(s,pair['lower'])]['val_symbol_fit']
                  for s in self.config['training_seeds']]
            self.assertAlmostEqual(sum(vals)/5,pair['mean_delta'])
            self.assertEqual(sum(v>0 for v in vals),pair['better'])
            expected=bootstrap(vals,self.config['bootstrap_seed']+pair['higher']*1000+pair['lower'],10000)
            self.assertEqual(expected,pair['bootstrap_ci95'])

    def test_strict_near_threshold_no_online(self):
        a=self.analysis
        candidate=next(x for x in a['candidate_gate'] if x['updates']==500)
        self.assertLess(candidate['mean_gain_pp'],2.)
        self.assertGreater(candidate['mean_gain_pp'],1.99)
        self.assertEqual((candidate['eligible'],a['selected_budget'],a['canonical_seed']),(False,None,None))
        self.assertTrue(all(not x['eligible'] for x in a['candidate_gate']))

    def test_frequency_and_curve_coverage(self):
        a=self.analysis;c=self.config
        self.assertEqual(len(a['frequency_bucket_metrics']),5*5*2*4)
        for seed in c['training_seeds']:
            curve=read(OUT/'seed_summaries'/str(seed)/'training_curve.json')
            self.assertEqual(sorted(x['update'] for x in curve),c['curve_updates'])
            self.assertIn(a['best_curve_points'][str(seed)]['ce_update'],c['curve_updates'])
        self.assertEqual(a['frozen_files'],read(OUT/'frozen_verification.json')['files'])

    def test_report_does_not_promote(self):
        p=ROOT/'reports/v147_multiseed_generalization.json'
        if not p.exists():return
        report=read(p)
        self.assertEqual(report['online_smoke'],'NOT TRIGGERED')
        self.assertIsNone(report['candidate_budget'])
        self.assertEqual(report['test_metrics'],'SEALED')

if __name__=='__main__':unittest.main()
