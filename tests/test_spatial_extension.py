import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Optional PyTorch required')
class SpatialExtensionTests(unittest.TestCase):
    def test_grouped_skip_errors_have_correct_direction_and_denominators(self):
        import torch
        from extend_spatial_bc import grouped_metrics
        from luck_agent.env.game_env import GameEnv, EnvConfig
        from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder
        from luck_agent.evaluation.trajectory import normalized
        env = GameEnv(EnvConfig(floor=1, rule_version='instance-goldfish-v1'))
        env.reset(0)
        env._phase = 'symbol'
        env._options = ('coin', 'coal')
        enc = SpatialCandidateEncoder()
        actions = normalized(env.legal_actions())
        skip = next(i for i, a in enumerate(actions) if a['action_type'] == 1)
        pick = next(i for i, a in enumerate(actions) if a['action_type'] == 0)
        def sample(label):
            result = enc.encode({'state': normalized(env.state), 'legal_actions': actions,
                'action_mask': [True]*len(actions), 'action': actions[label], 'reward': 0,
                'terminated': False, 'truncated': False, 'episode_seed': 0, 'step': label}, 'test')
            result['deck'] = [result['deck'][0]]*18
            return result
        class Always(torch.nn.Module):
            def __init__(self, choice):
                super().__init__()
                self.choice = choice
            def forward(self, batch):
                logits = torch.zeros_like(batch['candidates_mask'], dtype=torch.float32)
                logits[:, self.choice] = 1
                return logits.masked_fill(~batch['candidates_mask'], float('-inf'))
        rows = [sample(pick), sample(skip)]
        result = grouped_metrics(Always(skip), rows, 1)
        for name in ('all', 'deck_18_19', 'all_symbol_deck_18_19'):
            self.assertEqual(result[name]['multi_candidate_decisions'], 2)
            self.assertEqual(result[name]['accuracy'], 0.5)
            self.assertEqual(result[name]['teacher_picks'], 1)
            self.assertEqual(result[name]['teacher_skips'], 1)
            self.assertEqual(result[name]['model_skips_teacher_pick'], 1)
            self.assertEqual(result[name].get('model_picks_teacher_skip', 0), 0)
        result = grouped_metrics(Always(pick), rows)['all']
        self.assertEqual(result.get('model_skips_teacher_pick', 0), 0)
        self.assertEqual(result['model_picks_teacher_skip'], 1)
