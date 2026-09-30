import hashlib
import importlib.util
from pathlib import Path
import unittest

from luck_agent.env.game_env import EnvConfig, GameEnv
from luck_agent.evaluation.evaluator import BCSpec, evaluate


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "outputs/v130-magpie-corpus-training/research-200-updates.pt"
CORPUS = ROOT / "logs/v128-magpie-shards"
AVAILABLE = importlib.util.find_spec("torch") is not None and CHECKPOINT.is_file() and CORPUS.is_dir()


@unittest.skipUnless(AVAILABLE, "V130 model environment and artifacts are required")
class BCUnifiedEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from luck_agent.agents.bc_policy import BCPolicyAdapter
        cls.digest = hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()
        cls.policy = BCPolicyAdapter(CHECKPOINT, expected_sha256=cls.digest,
                                     dataset_dir=CORPUS,
                                     rule_version="instance-magpie-v1")

    def test_policy_is_deterministic_and_legal(self):
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-magpie-v1"))
        state = env.reset(14100)
        while len(env.legal_actions()) == 1:
            state, *_ = env.step(env.legal_actions()[0])
        actions = env.legal_actions()
        first = self.policy.choose(state, actions)
        second = self.policy.choose(state, actions)
        self.assertEqual(first, second)
        self.assertIn(first, actions)

    def test_wrong_hash_and_rule_are_rejected(self):
        from luck_agent.agents.bc_policy import BCPolicyAdapter
        with self.assertRaises(ValueError):
            BCPolicyAdapter(CHECKPOINT, expected_sha256="0" * 64,
                            dataset_dir=CORPUS, rule_version="instance-magpie-v1")
        with self.assertRaises(ValueError):
            BCPolicyAdapter(CHECKPOINT, expected_sha256=self.digest,
                            dataset_dir=CORPUS, rule_version="legacy")

    def test_evaluator_accepts_bc_with_existing_episode_schema(self):
        rows, _ = evaluate(1, "bc", 14101,
                           EnvConfig(floor=1, rule_version="instance-magpie-v1"),
                           bc_spec=BCSpec(str(CHECKPOINT), self.digest, str(CORPUS)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["agent"], "bc")
        self.assertEqual(rows[0]["invalid_actions"], 0)
        self.assertEqual(rows[0]["stage"], rows[0]["final_stage"])
