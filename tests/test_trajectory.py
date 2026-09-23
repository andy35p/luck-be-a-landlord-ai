import gzip
import json
import tempfile
import unittest
from pathlib import Path
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.trajectory import TrajectoryWriter, replay


class TrajectoryTests(unittest.TestCase):
    def test_additive_board_field_compatibility_and_validation(self):
        config = EnvConfig(floor=1, rule_version="instance-coal-v1")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"board.gz"
            with TrajectoryWriter(path, config, "random") as sink:
                evaluate(1, "random", 0, config, transition_sink=sink)
            with gzip.open(path, "rt") as stream:
                records = [json.loads(line) for line in stream]
            records[1]["next_state"]["visible_board_cells"] = ["invalid"]
            with gzip.open(path, "wt") as stream:
                stream.writelines(json.dumps(r)+"\n" for r in records)
            with self.assertRaisesRegex(ValueError, "Replay mismatch"):
                replay(path)
            for record in records[1:]:
                for key in ("state", "next_state"):
                    del record[key]["visible_board_cells"]
            with gzip.open(path, "wt") as stream:
                stream.writelines(json.dumps(r)+"\n" for r in records)
            self.assertTrue(replay(path)["exact_replay"])
            records[1]["next_state"]["coins"] += 1
            with gzip.open(path, "wt") as stream:
                stream.writelines(json.dumps(r)+"\n" for r in records)
            with self.assertRaisesRegex(ValueError, "Replay mismatch"):
                replay(path)

    def test_validated_policy_metadata_and_replay(self):
        config = EnvConfig(floor=1, rule_version="instance-coal-v1")
        policy = {"coal_score_adjustment": -1.2}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"candidate.gz"
            with TrajectoryWriter(path, config, "heuristic_coal_v029", policy_config=policy) as sink:
                actual, _ = evaluate(3, "heuristic", 0, config, transition_sink=sink, **policy)
            expected, _ = evaluate(3, "heuristic", 0, config, **policy)
            self.assertEqual(actual, expected)
            with gzip.open(path, "rt") as stream: header = json.loads(next(stream))
            self.assertEqual(header["policy_config"], policy)
            self.assertEqual(header["agent"], "heuristic_coal_v029")
            self.assertTrue(replay(path)["exact_replay"])

    def test_recording_does_not_change_results_and_replays(self):
        config = EnvConfig(floor=1, rule_version="instance-coal-v1")
        for mode in ("random", "heuristic"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/"trace.gz"
                expected, _ = evaluate(3, mode, 0, config)
                with TrajectoryWriter(path, config, mode) as sink:
                    actual, _ = evaluate(3, mode, 0, config, transition_sink=sink)
                self.assertEqual(expected, actual)
                self.assertEqual(replay(path), {"episodes": 3,
                    "transitions": sum(r["decisions"] for r in actual), "exact_replay": True})
                with gzip.open(path, "rt") as stream:
                    records = [json.loads(line) for line in stream]
                self.assertNotIn("seed", records[1]["state"]["effect_state"])
                self.assertIn("secondary_target_id", records[1]["action"])

    def test_corruption_and_incomplete_episode_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"trace.gz"
            config = EnvConfig(floor=1, rule_version="instance-coal-v1")
            with TrajectoryWriter(path, config, "random") as sink:
                evaluate(1, "random", 0, config, transition_sink=sink)
            with gzip.open(path, "rt") as stream: lines = list(stream)
            record = json.loads(lines[1]); record["reward"] += 1
            with gzip.open(path, "wt") as stream:
                stream.writelines([lines[0], json.dumps(record)+"\n", *lines[2:]])
            with self.assertRaisesRegex(ValueError, "Replay mismatch"): replay(path)
            with gzip.open(path, "wt") as stream: stream.writelines(lines[:-1])
            with self.assertRaisesRegex(ValueError, "incomplete"): replay(path)

    def test_truncation_replays_as_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"trace.gz"
            config = EnvConfig(floor=1, rule_version="instance-coal-v1", max_decisions=1)
            with TrajectoryWriter(path, config, "random") as sink:
                rows, _ = evaluate(1, "random", 0, config, transition_sink=sink)
            self.assertEqual(rows[0]["truncated"], 1)
            self.assertTrue(replay(path)["exact_replay"])
