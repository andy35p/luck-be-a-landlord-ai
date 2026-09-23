import copy
import unittest
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType as T
from luck_agent.evaluation.trajectory import normalized
from luck_agent.evaluation.batching import CandidateEncoder, collate, masked_argmax


class BatchingTests(unittest.TestCase):
    def record(self, env, action=None):
        actions = normalized(env.legal_actions())
        return {"state": normalized(env.state), "legal_actions": actions,
                "action_mask": [True]*len(actions), "action": normalized(action) if action else actions[0],
                "reward": 0, "terminated": False, "truncated": False, "episode_seed": 1, "step": 0}

    def test_remove_copies_have_different_pointers(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))
        env._engine.choose("coal"); env._engine.choose("coal")
        env._engine.removals = 1; env._phase = "remove"
        uid = env.state.symbols[-1].instance_id
        sample = CandidateEncoder().encode(self.record(env, Action(T.REMOVE_SYMBOL, uid)), "test")
        chosen = sample["candidates"][sample["label"]]
        self.assertEqual(chosen[3], len(env.state.symbols))
        self.assertNotEqual(sample["candidates"][-3][3], sample["candidates"][-2][3])

    def test_padding_mask_blocks_highest_invalid_score(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))
        encoder = CandidateEncoder(); small = encoder.encode(self.record(env), "test")
        env._phase = "symbol"; env._options = ("coal", "coin", "flower")
        large = encoder.encode(self.record(env), "test")
        batch = collate([small, large])
        self.assertEqual(masked_argmax([0]+[999]*3, batch["candidates_mask"][0]), 0)
        for i, label in enumerate(batch["label"]): self.assertTrue(batch["candidates_mask"][i][label])
        with self.assertRaises(ValueError): masked_argmax([1], [False])

    def test_permutation_moves_label_and_preserves_action(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))
        env._phase = "symbol"; env._options = ("coal", "coin")
        r = self.record(env, Action(T.PICK_SYMBOL, "coin")); a = CandidateEncoder().encode(r, "test")
        r["legal_actions"].reverse(); b = CandidateEncoder().encode(r, "test")
        self.assertEqual(a["candidates"][a["label"]], b["candidates"][b["label"]])

    def test_future_reward_and_episode_number_not_features(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))
        r = self.record(env); other = copy.deepcopy(r)
        other.update(reward=999, episode_seed=999, next_state={"coins": 999})
        a = CandidateEncoder().encode(r, "test"); b = CandidateEncoder().encode(other, "test")
        for key in ("scalars", "deck", "items", "candidates"): self.assertEqual(a[key], b[key])

    def test_secondary_targets_rejected_in_bounded_scope(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))
        r = self.record(env); r["legal_actions"][0]["secondary_target_id"] = "x"
        with self.assertRaises(ValueError): CandidateEncoder().encode(r, "test")
