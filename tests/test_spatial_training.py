import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'),'Optional PyTorch required')
class SpatialTrainingTests(unittest.TestCase):
    def test_offline_metrics_exclude_forced_actions_and_weight_decisions(self):
        import torch
        from train_spatial_bc_smoke import offline
        from luck_agent.env.game_env import GameEnv,EnvConfig
        from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
        from luck_agent.evaluation.trajectory import normalized
        env=GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1'));enc=SpatialCandidateEncoder()
        def sample():
            a=normalized(env.legal_actions())
            return enc.encode({'state':normalized(env.state),'legal_actions':a,'action_mask':[True]*len(a),
                               'action':a[0],'reward':999,'terminated':False,'truncated':False,
                               'episode_seed':0,'step':0},'test')
        forced=sample();env._phase='symbol';env._options=('coin','coal');decision=sample()
        class Uniform(torch.nn.Module):
            def forward(self,b):
                return torch.zeros_like(b['candidates_mask'],dtype=torch.float32).masked_fill(~b['candidates_mask'],float('-inf'))
        result=offline(Uniform(),[forced,decision,decision],2)
        self.assertEqual(result['forced_decisions'],1)
        self.assertEqual(result['multi_candidate_decisions'],2)
        self.assertEqual(result['accuracy'],1)
        self.assertAlmostEqual(result['mean_nll'],float(torch.log(torch.tensor(3.0))),places=6)
