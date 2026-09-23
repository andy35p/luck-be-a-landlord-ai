import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optional model environment requires PyTorch")
class CandidateModelTests(unittest.TestCase):
    def test_count_feature_and_shared_initialization(self):
        import torch
        from luck_agent.agents.candidate_model import CandidateModel
        torch.manual_seed(36);base=CandidateModel()
        torch.manual_seed(36);count=CandidateModel(deck_count=True)
        for key,value in base.state_dict().items():
            other=count.state_dict()[key]
            if key=="head.0.weight":
                self.assertTrue(torch.equal(value,other[:,:-1]))
                self.assertEqual(other[:,-1].abs().sum().item(),0)
            else:self.assertTrue(torch.equal(value,other))
        feature=count.count_feature({"deck_mask":torch.tensor([[True,False],[True,True]])})
        self.assertAlmostEqual(feature[0].item(),.05)
        self.assertAlmostEqual(feature[1].item(),.1)

    def test_masked_loss_matches_reference_and_gradients(self):
        import torch
        from luck_agent.agents.candidate_model import masked_bc_loss
        from luck_agent.evaluation.bc_contract import masked_bc_metrics
        scores = [[1000., 999., 1e6], [3., 1e6, 1e6]]
        mask = [[True, True, False], [True, False, False]]
        x = torch.tensor(scores, dtype=torch.float64, requires_grad=True)
        loss = masked_bc_loss(x, torch.tensor([1, 0]), torch.tensor(mask))
        self.assertAlmostEqual(loss.item(), masked_bc_metrics(scores, [1, 0], mask)["mean_nll"])
        loss.backward()
        self.assertEqual(x.grad[0, 2].item(), 0)
        self.assertEqual(x.grad[1].abs().sum().item(), 0)
        self.assertIsNone(masked_bc_loss(x[1:], torch.tensor([0]), torch.tensor(mask[1:])))

    def test_forward_padding_and_candidate_permutation(self):
        import torch
        from luck_agent.agents.candidate_model import CandidateModel, tensor_batch
        from luck_agent.evaluation.batching import CandidateEncoder, collate
        from luck_agent.evaluation.trajectory import normalized
        from luck_agent.env.game_env import GameEnv, EnvConfig
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-coal-v1"))
        def sample():
            a=normalized(env.legal_actions())
            return CandidateEncoder().encode(dict(state=normalized(env.state),legal_actions=a,action_mask=[True]*len(a),
                action=a[0],reward=0,terminated=False,truncated=False,episode_seed=0,step=0),"test")
        small=sample();env._phase="symbol";env._options=("coal","coin");large=sample()
        model=CandidateModel().eval(); batch=tensor_batch(collate([small,large]))
        with torch.no_grad():
            logits=model(batch)
            self.assertTrue(torch.isneginf(logits[0,1:]).all())
            single=model(tensor_batch(collate([small])))[0,0]
            self.assertTrue(torch.allclose(single,logits[0,0],atol=1e-6))
            batch["candidates"]=batch["candidates"].flip(1);batch["candidates_mask"]=batch["candidates_mask"].flip(1)
            self.assertTrue(torch.allclose(model(batch),logits.flip(1),atol=1e-6))
