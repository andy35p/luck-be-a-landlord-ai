import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from collect_spatial_dataset import collect
from luck_agent.evaluation.spatial_dataset import iter_corpus
from luck_agent.evaluation.dataset import split_for_seed


class SpatialDatasetTests(unittest.TestCase):
    def fixture(self,root):
        spec={'environment':{'floor':1,'rule_version':'instance-goldfish-v1'},
              'policies':['random','heuristic'],'seed_start':0,'games_per_policy':1,
              'split_salt':'luck-behavior-v1'}
        # Writer stores all EnvConfig defaults, as does the production protocol.
        from dataclasses import asdict
        from luck_agent.env.game_env import EnvConfig
        spec['environment']=asdict(EnvConfig(**spec['environment']))
        config=root/'config.json';config.write_text(json.dumps(spec))
        out=root/'data'
        with contextlib.redirect_stdout(io.StringIO()):collect(config,out)
        return out

    def test_grouped_split_and_policy_selection(self):
        with tempfile.TemporaryDirectory() as d:
            out=self.fixture(Path(d));split=split_for_seed(0)
            samples=list(iter_corpus(out,split=split,policies=['heuristic']))
            self.assertTrue(samples)
            self.assertEqual({s['metadata']['seed'] for s in samples},{0})
            self.assertEqual({s['metadata']['policy'] for s in samples},{'heuristic'})
            other=next(s for s in ('train','validation','test') if s!=split)
            self.assertEqual(list(iter_corpus(out,split=other,policies=['heuristic'])),[])

    def test_changed_file_and_unknown_policy_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=self.fixture(Path(d))
            with self.assertRaises(ValueError):list(iter_corpus(out,split='train',policies=['unknown']))
            (out/'vocabulary.json').write_text('{}')
            with self.assertRaises(ValueError):list(iter_corpus(out,split='train',policies=['random']))
