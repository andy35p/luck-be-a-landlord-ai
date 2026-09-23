import unittest
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.trajectory import normalized
from luck_agent.evaluation.teacher_dataset import teacher_example, mixed_decision_batches, collate_supervision


class TeacherDatasetTests(unittest.TestCase):
    def test_teacher_label_not_executed_target(self):
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-coal-v1"));env._phase="symbol";env._options=("coin","coal")
        actions=normalized(env.legal_actions())
        record=dict(state=normalized(env.state),legal_actions=actions,action=actions[0],teacher_action=actions[1],
                    episode_seed=0,step=2,reward=999,next_state={"coins":999})
        sample=teacher_example(record,"source")
        self.assertEqual(sample["label"],1)
        self.assertEqual(sample["metadata"]["executed_action"],actions[0])
        self.assertNotIn("reward",sample);self.assertNotIn("next_state",sample)
        batch=collate_supervision([sample])
        self.assertEqual(batch["label"],[1])
        self.assertTrue(batch["candidates_mask"][0][1])
        self.assertNotIn("reward",batch);self.assertNotIn("next_state",batch)
        record["teacher_action"]={}
        with self.assertRaises(ValueError):teacher_example(record,"source")

    def test_mixture_cycles_reproducibly_and_excludes_forced(self):
        a=[dict(candidates=[0,1],label=0,identity=i) for i in range(10)]
        b=[dict(candidates=[0,1],label=1,identity=i) for i in range(20,30)]
        b.append(dict(candidates=[0],identity=999))
        rows=list(mixed_decision_batches(a,b,steps=2,batch_size=4,seed=42,annotated_per_batch=2))
        self.assertEqual(rows,list(mixed_decision_batches(a,b,steps=2,batch_size=4,seed=42,annotated_per_batch=2)))
        for row in rows:self.assertEqual(sum(i for i,_ in row),2)
        self.assertEqual(len({(i,s["identity"]) for row in rows for i,s in row}),8)

    def test_quarter_mixture_budget(self):
        pool=[dict(candidates=[0,1],label=0,identity=i) for i in range(100)]
        batches=list(mixed_decision_batches(pool,pool,steps=3,batch_size=64,annotated_per_batch=16))
        self.assertEqual([sum(source==1 for source,_ in b) for b in batches],[16,16,16])
        self.assertEqual(sum(len(b) for b in batches),192)
