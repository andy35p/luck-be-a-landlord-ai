import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'),'Optional PyTorch required')
class SpatialModelTests(unittest.TestCase):
    def sample(self,env):
        from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
        from luck_agent.evaluation.trajectory import normalized
        actions=normalized(env.legal_actions())
        return SpatialCandidateEncoder().encode({'state':normalized(env.state),'legal_actions':actions,
            'action':actions[0],'action_mask':[True]*len(actions),'reward':0,'terminated':False,
            'truncated':False,'episode_seed':0,'step':0},'test')

    def env(self):
        from luck_agent.env.game_env import GameEnv,EnvConfig
        return GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1'))

    def scaler(self,root):
        from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder as E
        (root/'manifest.json').write_text('{}')
        return {'version':'spatial-train-zscore-v1','encoder':E.version,'fit_split':'train',
                'manifest_sha256':hashlib.sha256(b'{}').hexdigest(),'policies':['heuristic'],
                'samples':1,'fields':list(E.scalar_fields),'mean':[0]*8,'scale':[1]*8}

    def test_padding_permutation_and_empty_deck(self):
        import torch
        from luck_agent.agents.spatial_model import SpatialCandidateModel,spatial_tensors
        from luck_agent.evaluation.spatial_batching import collate_spatial
        env=self.env();small=self.sample(env);env._phase='symbol';env._options=('coal','goldfish')
        large=self.sample(env);model=SpatialCandidateModel().eval();b=spatial_tensors(collate_spatial([small,large]))
        scores=model(b)
        self.assertTrue(torch.isneginf(scores[0,1:]).all())
        self.assertTrue(torch.allclose(scores[0,0],model(spatial_tensors(collate_spatial([small])))[0,0],atol=1e-6))
        b['candidates']=b['candidates'].flip(1);b['candidates_mask']=b['candidates_mask'].flip(1)
        self.assertTrue(torch.allclose(model(b),scores.flip(1),atol=1e-6))
        for s in env._engine.instances.snapshot():env._engine.instances.remove(s.instance_id)
        env._engine._sync_deck()
        self.assertTrue(torch.isfinite(model(spatial_tensors(collate_spatial([self.sample(env)])))).all())

    def test_board_affects_output_and_gradients(self):
        import torch
        from luck_agent.agents.spatial_model import SpatialCandidateModel,spatial_tensors
        from luck_agent.agents.candidate_model import masked_bc_loss
        from luck_agent.evaluation.spatial_batching import collate_spatial
        from luck_agent.env.action import Action,ActionType
        env=self.env();env.step(Action(ActionType.SPIN));env._phase='symbol';env._options=('coal','coin')
        sample=self.sample(env);torch.manual_seed(65);model=SpatialCandidateModel()
        b=spatial_tensors(collate_spatial([sample]));scores=model(b)
        loss=masked_bc_loss(scores,torch.tensor([0]),b['candidates_mask']);loss.backward()
        self.assertGreater(model.board_cell[0].weight.grad.abs().sum().item(),0)
        changed=copy.deepcopy(b);changed['board_mask'].zero_()
        self.assertFalse(torch.allclose(scores,model(changed)))

    def test_checkpoint_and_live_adapter_contract(self):
        import torch
        from luck_agent.agents.spatial_model import SpatialCandidateModel,SpatialTorchScorer,save_spatial_checkpoint,load_spatial_checkpoint
        from luck_agent.agents.spatial_agent import SpatialCandidateAgent
        from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
        env=self.env();env._phase='symbol';env._options=('coal','coin')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);scaler=self.scaler(root);model=SpatialCandidateModel();path=root/'model.pt'
            save_spatial_checkpoint(path,model,scaler,directory=root,policies=['heuristic'])
            restored,_=load_spatial_checkpoint(path,directory=root,policies=['heuristic'])
            features=SpatialCandidateEncoder.features(self.sample(env))
            self.assertEqual(SpatialTorchScorer(model)(features),SpatialTorchScorer(restored)(features))
            observed=[]
            def score(f):observed.append(f);return list(range(len(f['candidates'])))
            agent=SpatialCandidateAgent(score,rule_version='instance-goldfish-v1',scaler=scaler,directory=root,policies=['heuristic'])
            rng=env._engine.rng.getstate()
            self.assertEqual(agent.choose(env.state,env.legal_actions()),env.legal_actions()[-1])
            self.assertEqual(rng,env._engine.rng.getstate())
            self.assertFalse({'label','reward','metadata','next_state'} & observed[0].keys())
            agent.scorer=lambda f:[float('nan')]*len(f['candidates'])
            with self.assertRaises(ValueError):agent.choose(env.state,env.legal_actions())
            payload=torch.load(path,weights_only=True);payload['encoder_version']='coal-candidates-v1';torch.save(payload,path)
            with self.assertRaises(ValueError):load_spatial_checkpoint(path,directory=root,policies=['heuristic'])
