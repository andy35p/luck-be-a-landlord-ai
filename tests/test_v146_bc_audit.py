"""V146 audit invariants: exact baseline, split discipline and no false promotion."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_bc_optimization import summarize

OUT=ROOT/'logs/v146-bc-audit'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

class AuditContractTests(unittest.TestCase):
    def test_frozen_baseline_exact_counts(self):
        baseline=read(OUT/'baseline_metrics.json')
        train=baseline['metrics']['train']['phases']['symbol']
        val=baseline['metrics']['validation']['phases']['symbol']
        self.assertEqual((train['correct'],train['n']), (2072,2843))
        self.assertEqual((val['correct'],val['n']), (578,762))
        self.assertTrue(baseline['v130_exact_phase_accuracy'])

    def test_split_coverage_and_tensor_collision(self):
        baseline=read(OUT/'baseline_metrics.json')
        self.assertEqual((baseline['coverage']['train']['episodes'],baseline['coverage']['validation']['episodes']),(32,8))
        train=set(baseline['coverage']['train']['shards']);val=set(baseline['coverage']['validation']['shards'])
        self.assertFalse(train&val)
        self.assertEqual((len(train),len(val)),(32,8))
        for p in ('train','validation'):
            self.assertEqual(baseline['collisions'][p]['input_label_conflicts'],0)
            self.assertEqual(baseline['collisions'][p]['samples'],baseline['collisions'][p]['unique_inputs'])

    def test_exact_200_weight_reproduction(self):
        run=read(OUT/'budget_scaling/seed123/result.json')
        self.assertTrue(run['exact_v130_weights'])
        self.assertTrue(read(OUT/'budget_scaling/seed123/exact_v130_reproduction.json')['all_weights_bitwise_equal'])

    def test_tiny_set_stop_and_budget_gate(self):
        for size in (32,128,512):
            run=read(OUT/f'tiny_overfit/{size}/result.json')
            last=list(run['checkpoints'].values())[-1]['metrics']['train']['all']
            self.assertEqual(last['accuracy'],1)
            self.assertLessEqual(last['ce'],.05)
            self.assertEqual(read(OUT/f'tiny_overfit/{size}/input_collisions.json')['input_label_conflicts'],0)
        self.assertIsNone(read(OUT/'candidate_gate.json')['chosen_updates'])
        self.assertFalse(read(OUT/'capacity/gate.json')['run'])

    def test_metrics_distinguish_zero_coverage(self):
        self.assertIsNone(summarize([])['accuracy'])
        self.assertEqual(summarize([{'correct':True,'ce':0.1,'top2':True,'teacher_rank':1,
            'teacher_margin':1.,'high_confidence_wrong':False,'candidate_count':4}])['candidate_buckets']['4+']['n'],1)

    def test_no_test_metric_or_online_promotion(self):
        protocol=read(OUT/'protocol.json')
        self.assertNotIn('test',protocol['splits_read_for_metrics'])
        self.assertIn('SEALED',protocol['test_metrics'])
        result=read(OUT/'candidate_gate.json')
        self.assertIsNone(result['chosen_updates'])

if __name__=='__main__':unittest.main()
