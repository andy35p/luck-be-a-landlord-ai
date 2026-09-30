import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder
from luck_agent.evaluation.magpie_preprocessing import fit_magpie_scaler,validate_magpie_scaler,scale_magpie_sample


class MagpiePreprocessingTests(unittest.TestCase):
    def test_train_only_moments_and_tamper_rejection(self):
        rows=[{'scalars':[x]*8,'metadata':{'split':'train'}} for x in (1,3)]
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'manifest.json').write_text('{}')
            with patch('luck_agent.evaluation.magpie_preprocessing.load_smoke_samples',return_value=rows) as loader:
                scaler=fit_magpie_scaler(tmp)
                loader.assert_called_once_with(tmp,split='train')
                self.assertEqual(scaler['mean'],[2]*8);self.assertEqual(scaler['scale'],[1]*8)
                validate_magpie_scaler(scaler,tmp)
                bad=deepcopy(scaler);bad['mean'][0]+=1
                with self.assertRaises(ValueError):validate_magpie_scaler(bad,tmp)
                rows[0]['metadata']['split']='validation'
                with self.assertRaises(ValueError):fit_magpie_scaler(tmp)

    def test_only_scalars_change_and_bad_width_rejects(self):
        sample={'encoder_version':MagpieCandidateEncoder.version,'scalars':[3]*8,'deck':[[1,0,4,1]],'metadata':{'split':'test'}}
        scaler={'version':'magpie-smoke-zscore-v1','encoder':MagpieCandidateEncoder.version,'mean':[2]*8,'scale':[2]*8}
        original=deepcopy(sample);scaled=scale_magpie_sample(sample,scaler)
        self.assertEqual(scaled['scalars'],[.5]*8);self.assertEqual(scaled['deck'],sample['deck']);self.assertEqual(sample,original)
        scaler['scale']=[1]
        with self.assertRaises(ValueError):scale_magpie_sample(sample,scaler)
