import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
from luck_agent.evaluation.spatial_preprocessing import fit_spatial_scaler,validate_spatial_scaler,scale_spatial_sample,iter_spatial_batches


class SpatialPreprocessingTests(unittest.TestCase):
    def fixture(self,root):
        (root/'manifest.json').write_text('{}')
        samples=[{'scalars':[x]*8} for x in (2,4)]
        with patch('luck_agent.evaluation.spatial_preprocessing.iter_corpus',return_value=iter(samples)) as reader:
            scaler=fit_spatial_scaler(root,policies=['heuristic'])
            reader.assert_called_once_with(root,split='train',policies=['heuristic'])
        return scaler

    def test_training_only_stats_and_no_categorical_scaling(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);scaler=self.fixture(root)
            self.assertEqual(scaler['mean'],[3]*8);self.assertEqual(scaler['scale'],[1]*8)
            sample={'encoder_version':SpatialCandidateEncoder.version,'scalars':[4]*8,
                    'board':[[1,0,3,1,2]],'deck':[[1,0,3,1]],'reward':999,'label':2}
            before=copy.deepcopy(sample);frozen=copy.deepcopy(scaler)
            result=scale_spatial_sample(sample,scaler)
            self.assertEqual(result['scalars'],[1]*8)
            for key in ('board','deck','reward','label'):self.assertEqual(result[key],sample[key])
            self.assertEqual(sample,before);self.assertEqual(scaler,frozen)

    def test_provenance_and_validation_shuffle_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);scaler=self.fixture(root)
            validate_spatial_scaler(scaler,root,['heuristic'])
            with self.assertRaises(ValueError):validate_spatial_scaler(scaler,root,['random'])
            with self.assertRaises(ValueError):list(iter_spatial_batches(root,split='validation',policies=['heuristic'],scaler=scaler,shuffle_seed=1))
            (root/'manifest.json').write_text('{"changed":true}')
            with self.assertRaises(ValueError):validate_spatial_scaler(scaler,root,['heuristic'])

    def test_zero_variance_and_nonfinite_input(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'manifest.json').write_text('{}')
            with patch('luck_agent.evaluation.spatial_preprocessing.iter_corpus',return_value=iter([{'scalars':[0]*8}])):
                self.assertEqual(fit_spatial_scaler(root,policies=['heuristic'])['scale'],[1]*8)
            with patch('luck_agent.evaluation.spatial_preprocessing.iter_corpus',return_value=iter([{'scalars':[float('nan')]*8}])):
                with self.assertRaises(ValueError):fit_spatial_scaler(root,policies=['heuristic'])
