import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from luck_agent.evaluation.batching import CandidateEncoder
from luck_agent.evaluation.preprocessing import shuffled, fit_scaler, validate_scaler, scale_sample


class PreprocessingTests(unittest.TestCase):
    def test_shuffle_reproducibility_and_coverage(self):
        a = list(shuffled(range(103), 17, 0, 8))
        self.assertEqual(a, list(shuffled(range(103), 17, 0, 8)))
        self.assertNotEqual(a, list(shuffled(range(103), 17, 1, 8)))
        self.assertEqual(sorted(a), list(range(103)))
        self.assertEqual(list(shuffled([], 17)), [])
        with self.assertRaises(ValueError): list(shuffled([1], 0, buffer_size=1))

    def test_fit_uses_train_only_and_constant_columns_safe(self):
        width = len(CandidateEncoder.scalar_fields)
        samples = [{"scalars": [1.0]+[4.0]*(width-1)}, {"scalars": [3.0]+[4.0]*(width-1)}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"index.json"; path.write_text("{}")
            with patch("luck_agent.evaluation.batching.iter_samples", return_value=iter(samples)) as reader:
                scaler = fit_scaler(path, ["teacher"])
                reader.assert_called_once_with(path, split="train", policies=["teacher"])
            self.assertEqual(scaler["mean"], [2.0]+[4.0]*(width-1))
            self.assertEqual(scaler["scale"], [1.0]*width)
            sample = {**samples[0], "candidates": [[1, 2, 3, 4]], "reward": 123, "metadata": {"seed": 3}}
            before = copy.deepcopy(sample); scaled = scale_sample(sample, scaler)
            self.assertEqual(sample, before)
            self.assertEqual(scaled["scalars"], [-1.0]+[0.0]*(width-1))
            for key in ("candidates", "reward", "metadata"): self.assertEqual(scaled[key], sample[key])
            validate_scaler(scaler, path, ["teacher"])
            with self.assertRaises(ValueError): validate_scaler(scaler, path, ["random"])
            path.write_text('{"changed":true}')
            with self.assertRaises(ValueError): validate_scaler(scaler, path, ["teacher"])
