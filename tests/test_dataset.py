import gzip
import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.trajectory import TrajectoryWriter
from luck_agent.evaluation.dataset import read_episodes, split_for_seed
from prepare_dataset import prepare


class DatasetTests(unittest.TestCase):
    def fixture(self, root):
        config = EnvConfig(floor=1, rule_version="instance-coal-v1", max_decisions=2)
        files = {}
        for policy in ("random", "heuristic"):
            path = root/f"{policy}.jsonl.gz"
            with TrajectoryWriter(path, config, policy) as writer:
                evaluate(3, policy, 0, config, transition_sink=writer)
            files[path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = {"config": asdict(config), "policies": {"random": {}, "heuristic": {}},
                    "seed_start": 0, "games": 3, "files": files}
        (root/"manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_seed_grouping_reproducible_and_truncation_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            a = prepare(root, root/"a.json"); b = prepare(root, root/"b.json")
            self.assertEqual(a, b)
            self.assertEqual(len(a["episodes"]), 6)
            for seed in range(3):
                rows = [r for r in a["episodes"] if r["episode_seed"] == seed]
                self.assertEqual({r["split"] for r in rows}, {split_for_seed(seed)})
                self.assertTrue(all(r["truncated"] for r in rows))

    def test_hash_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            with (root/"random.jsonl.gz").open("ab") as stream: stream.write(b"bad")
            with self.assertRaisesRegex(ValueError, "hash mismatch"): prepare(root, root/"a.json")
            self.assertFalse((root/"a.json").exists())

    def test_missing_episode_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            p = root/"manifest.json"; manifest = json.loads(p.read_text()); manifest["games"] = 4
            p.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Missing"): prepare(root, root/"a.json")

    def test_reader_rejects_broken_continuity_and_invalid_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            p = root/"random.jsonl.gz"
            with gzip.open(p, "rt") as stream: original = [json.loads(line) for line in stream]
            for mutation in ("continuity", "action", "duplicate"):
                rows = json.loads(json.dumps(original))
                if mutation == "continuity": rows[2]["state"]["coins"] += 1
                if mutation == "action": rows[1]["action"]["action_type"] = 999
                if mutation == "duplicate": rows.extend(rows[1:3])
                with gzip.open(p, "wt") as stream:
                    for r in rows: stream.write(json.dumps(r)+"\n")
                with self.assertRaises(ValueError): list(read_episodes(p))
