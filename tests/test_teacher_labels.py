import importlib.util
import tempfile
import unittest
from pathlib import Path
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.trajectory import TrajectoryWriter, replay
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.batching import CandidateEncoder


class TeacherLabelTests(unittest.TestCase):
    def test_replay_executes_action_not_teacher_label(self):
        config=EnvConfig(floor=1,rule_version="instance-coal-v1",max_decisions=3)
        env=GameEnv(config);state=env.reset(0)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"trace.gz"
            with TrajectoryWriter(path,config,"test") as writer:
                step=0
                while not(state.is_terminal or state.is_truncated):
                    actions=env.legal_actions();executed=actions[0];teacher=actions[-1]
                    next_state,reward,term,trunc,info=env.step(executed)
                    writer(0,step,state,actions,executed,reward,next_state,term,trunc,info,teacher_action=teacher)
                    state=next_state;step+=1
            self.assertTrue(replay(path)["exact_replay"])
            records=list(read_episodes(path))[0][1]
            self.assertTrue(any(r["action"]!=r["teacher_action"] for r in records))
            with self.assertRaisesRegex(ValueError,"supervision adapter"):CandidateEncoder().encode(records[0],"test")

    @unittest.skipUnless(importlib.util.find_spec("torch"), "Optional model environment")
    def test_seed_overlap_rejected(self):
        from collect_teacher_labels import training_seeds
        from luck_agent.evaluation.dataset import split_for_seed
        seed=next(s for s in range(100) if split_for_seed(s)=="train")
        index={"salt":"luck-behavior-v1","episodes":[{"policy":"teacher","episode_seed":seed,"split":"train"}]}
        self.assertEqual(training_seeds(index,"teacher"),[seed])
        index["episodes"].append({"policy":"random","episode_seed":seed,"split":"test"})
        with self.assertRaises(ValueError):training_seeds(index,"teacher")
