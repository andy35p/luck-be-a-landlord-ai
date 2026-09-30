import copy
import unittest
import tempfile
from pathlib import Path
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.env.action import Action,ActionType as T
from luck_agent.evaluation.trajectory import normalized
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder,collate_spatial,iter_spatial_samples
from luck_agent.evaluation.batching import CandidateEncoder


class SpatialBatchingTests(unittest.TestCase):
    def test_reader_rejects_wrong_backend_and_requires_split(self):
        from luck_agent.evaluation.trajectory import TrajectoryWriter
        from luck_agent.evaluation.evaluator import evaluate
        from luck_agent.evaluation.dataset import split_for_seed
        with tempfile.TemporaryDirectory() as d:
            for version in ('instance-coal-v1','instance-goldfish-v1'):
                p=Path(d)/(version+'.gz');cfg=EnvConfig(floor=1,rule_version=version,max_decisions=2)
                with TrajectoryWriter(p,cfg,'random') as sink:
                    evaluate(1,'random',0,cfg,transition_sink=sink)
                if version=='instance-coal-v1':
                    with self.assertRaises(ValueError):list(iter_spatial_samples(p,split='train'))
                else:
                    self.assertEqual(len(list(iter_spatial_samples(p,split=split_for_seed(0)))),2)
                    with self.assertRaises(ValueError):list(iter_spatial_samples(p,split='all'))

    def env(self):return GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1'))
    def record(self,env):
        actions=normalized(env.legal_actions())
        return {'state':normalized(env.state),'legal_actions':actions,'action':actions[0],
                'action_mask':[True]*len(actions),'reward':0,'terminated':False,'truncated':False,
                'episode_seed':0,'step':0}

    def test_destroyed_snapshot_and_new_child_have_distinct_meaning(self):
        env=self.env();e=env._engine;e.choose('bar_of_soap');uid=e.instances.snapshot()[-1].instance_id
        e.instances.tick((uid,));e.instances.tick((uid,));e._sync_deck()
        e.pending_instance_ids=(uid,);e.pending_shown=['bar_of_soap']
        env.step(Action(T.SPIN))
        sample=SpatialCandidateEncoder().encode(self.record(env),'test')
        self.assertTrue(sample['board_observed']);self.assertEqual(sum(sample['board_mask']),1)
        self.assertEqual(sample['board'][0][2:],[1,1,0])
        self.assertEqual(len(sample['deck']),6)

    def test_transformed_identity_points_to_current_different_symbol(self):
        env=self.env();e=env._engine;e.choose('coal');uid=e.instances.snapshot()[-1].instance_id
        for _ in range(19):e.instances.tick((uid,))
        e._sync_deck();e.pending_instance_ids=(uid,);e.pending_shown=['coal'];env.step(Action(T.SPIN))
        enc=SpatialCandidateEncoder();sample=enc.encode(self.record(env),'test')
        cell=sample['board'][0]
        self.assertEqual(cell[0],enc.symbols['coal'])
        self.assertEqual(sample['deck'][cell[4]-1][0],enc.symbols['diamond'])

    def test_missing_board_padding_masks_and_feature_leakage(self):
        env=self.env();enc=SpatialCandidateEncoder();r=self.record(env);a=enc.encode(r,'test')
        self.assertFalse(a['board_observed']);self.assertEqual(sum(a['board_mask']),0)
        other=copy.deepcopy(r);other.update(reward=999,episode_seed=99,next_state={'coins':999})
        b=enc.encode(other,'other');self.assertEqual(enc.features(a),enc.features(b))
        batch=collate_spatial([a,b]);self.assertEqual(len(batch['board'][0]),20)
        with self.assertRaises(ValueError):collate_spatial([a,{'encoder_version':CandidateEncoder.version}])

    def test_bad_snapshot_and_duplicate_candidates_rejected(self):
        env=self.env();r=self.record(env);r['state']['visible_board_cells']=['missing']+[None]*19
        with self.assertRaises(ValueError):SpatialCandidateEncoder().encode(r,'test')
        r=self.record(env);r['legal_actions']*=2
        with self.assertRaises(ValueError):SpatialCandidateEncoder().encode(r,'test')
