import gzip
import json
import tempfile
import unittest
from pathlib import Path
from luck_agent.env.game_env import EnvConfig
from luck_agent.env.rule_revision import rule_identity, validate_rule_identity
from luck_agent.evaluation.trajectory import TrajectoryWriter, replay
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.evaluator import evaluate


class RevisionTests(unittest.TestCase):
    def test_magpie_trace_requires_explicit_identity_and_replays(self):
        cfg=EnvConfig(floor=1,rule_version='instance-magpie-v1',max_decisions=25)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'magpie.gz'
            with TrajectoryWriter(path,cfg,'random') as sink:
                evaluate(1,'random',0,cfg,transition_sink=sink)
            self.assertTrue(replay(path)['exact_replay'])
            header,_=next(read_episodes(path))
            self.assertEqual(header['rule_identity'],{'rule_version':'instance-magpie-v1','revision':1})
            del header['rule_identity']
            with self.assertRaises(ValueError):validate_rule_identity(header)

    def test_new_milk_roundtrip_and_bad_identity_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'trace.gz'
            cfg = EnvConfig(floor=1, rule_version='instance-milk-v1', max_decisions=3)
            with TrajectoryWriter(path,cfg,'random') as sink:
                evaluate(1,'random',0,cfg,transition_sink=sink)
            self.assertTrue(replay(path)['exact_replay'])
            header, episode = next(read_episodes(path))
            self.assertEqual(header['rule_identity'],rule_identity('instance-milk-v1'))
            for identity in [None, {'rule_version':'instance-milk-v1','revision':1},
                             {'rule_version':'instance-cheese-v1','revision':2}]:
                changed = dict(header)
                if identity is None:
                    del changed['rule_identity']
                else:
                    changed['rule_identity'] = identity
                with gzip.open(path,'wt') as stream:
                    stream.writelines(json.dumps(r)+'\n' for r in [changed,*episode])
                for reader in (replay, lambda p:list(read_episodes(p))):
                    with self.assertRaises(ValueError):
                        reader(path)

    def test_historical_coal_without_identity_remains_readable(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'old.gz'
            cfg = EnvConfig(floor=1,rule_version='instance-coal-v1',max_decisions=2)
            with TrajectoryWriter(path,cfg,'random') as sink:
                evaluate(1,'random',0,cfg,transition_sink=sink)
            with gzip.open(path,'rt') as stream:
                records = [json.loads(line) for line in stream]
            del records[0]['rule_identity']
            with gzip.open(path,'wt') as stream:
                stream.writelines(json.dumps(r)+'\n' for r in records)
            self.assertTrue(replay(path)['exact_replay'])
            self.assertEqual(len(list(read_episodes(path))),1)

    def test_unknown_and_invalid_revision_rejected(self):
        for identity in [None, {}, {'rule_version':'instance-coal-v1','revision':True},
                         {'rule_version':'instance-coal-v1','revision':99}]:
            with self.assertRaises(ValueError):
                validate_rule_identity({'config':{'rule_version':'instance-coal-v1'},'rule_identity':identity})
        with self.assertRaises(ValueError):
            rule_identity('unknown')
