"""V149 loss, leakage, determinism and frozen-contract regressions."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import torch
from tools.audit_label_smoothing import masked_label_smoothing_loss,read
from tools.v149_data import load_v149_data

OUT=ROOT/'logs/v149-label-smoothing'
CFG=ROOT/'configs/v149_label_smoothing.json'

class V149Tests(unittest.TestCase):
    def test_masked_label_smoothing_formula_ignores_padding(self):
        logits=torch.tensor([[2.,1.,0.,float('-inf')],[.2,.3,float('-inf'),float('-inf')]],requires_grad=True)
        labels=torch.tensor([0,1]);mask=torch.isfinite(logits);epsilon=.1
        actual=masked_label_smoothing_loss(logits,labels,mask,epsilon)
        logp=torch.log_softmax(logits,1);safe=logp.masked_fill(~mask,0.)
        hard=-logp.gather(1,labels[:,None]).squeeze(1)
        expected=((1-epsilon)*hard+epsilon*(-safe.sum(1)/mask.sum(1))).mean()
        self.assertTrue(torch.equal(actual,expected));actual.backward()
        self.assertTrue(torch.isfinite(logits.grad[mask]).all());self.assertEqual(logits.grad[~mask].abs().sum(),0)

    def test_epsilon_zero_is_exact_legacy_loss_and_gradient(self):
        a=torch.tensor([[.2,.8,-.1],[1.,0.,-.5]],requires_grad=True);b=a.detach().clone().requires_grad_(True)
        labels=torch.tensor([1,0]);mask=torch.ones_like(a,dtype=torch.bool)
        x=masked_label_smoothing_loss(a,labels,mask,0.);y=torch.nn.functional.cross_entropy(b,labels)
        self.assertTrue(torch.equal(x,y));x.backward();y.backward();self.assertTrue(torch.equal(a.grad,b.grad))

    def test_reader_never_opens_test_or_manifest(self):
        import tools.v149_data as module
        opened=[];original=module._digest
        def monitored(path):opened.append(Path(path).name);return original(path)
        with patch.object(module,'_digest',side_effect=monitored):data=load_v149_data()
        self.assertTrue(opened);self.assertFalse(any(x.startswith('test-') or x=='manifest.json' for x in opened))
        self.assertFalse(data['test_opened']);self.assertFalse(data['manifest_opened'])

    def test_epsilon_zero_bitwise_and_standard_ce_regression(self):
        regression=read(OUT/'epsilon_zero_regression.json');self.assertTrue(regression['all_five_bitwise'])
        for seed in (123,456,789,24680,13579):
            run=read(OUT/'runs/epsilon-0.00'/f'seed-{seed}/run.json')
            historical=read(ROOT/'logs/v147-generalization/seed_summaries'/str(seed)/'run.json')['budgets']['500']
            self.assertTrue(run['epsilon_zero_bitwise_historical'])
            self.assertEqual(run['metrics']['validation']['symbol']['ce'],historical['metrics']['validation']['symbol']['ce'])

    def test_seed_grid_is_complete_and_deterministic(self):
        cfg=read(CFG);analysis=read(OUT/'analysis.json')
        self.assertEqual(len(analysis['seed_rows']),len(cfg['epsilons'])*len(cfg['training_seeds']))
        self.assertEqual({(x['epsilon'],x['seed']) for x in analysis['seed_rows']},
            {(e,s) for e in cfg['epsilons'] for s in cfg['training_seeds']})
        for e in cfg['epsilons']:
            for s in cfg['training_seeds']:
                run=read(OUT/'runs'/f'epsilon-{e:.2f}'/f'seed-{s}/run.json')
                self.assertEqual(run['metrics']['validation']['symbol']['accuracy'],
                    next(x['val_symbol'] for x in analysis['seed_rows'] if x['epsilon']==e and x['seed']==s))

    def test_threshold_gate_and_no_online_contract(self):
        cfg=read(CFG);analysis=read(OUT/'analysis.json');status=read(OUT/'online_smoke/status.json')
        self.assertEqual(cfg['high_confidence_wrong_threshold'],.8)
        self.assertTrue(all(not x['passed'] for x in analysis['candidate_gate']))
        self.assertIsNone(analysis['selected_epsilon']);self.assertEqual(status['status'],'NOT TRIGGERED')
        self.assertEqual(analysis['test_access'],'SEALED')

    def test_historical_assets_preserved(self):
        frozen=read(OUT/'frozen_verification.json');self.assertEqual(frozen['changed'],[])
        self.assertFalse(frozen['test_shards_opened']);self.assertFalse(frozen['v128_manifest_opened'])

if __name__=='__main__':unittest.main()
