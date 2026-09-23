import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optional model environment")
class BCDiagnosisTests(unittest.TestCase):
    def test_equal_score_is_not_exact_match(self):
        from diagnose_bc import classify_disagreement
        from luck_agent.agents.heuristic_agent import HeuristicAgent
        from luck_agent.env.game_env import GameEnv, EnvConfig
        from luck_agent.evaluation.trajectory import normalized
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-coal-v1"))
        teacher=HeuristicAgent(env.catalog,coal_score_adjustment=-1.2)
        a={"action_type":0,"target_id":"coin","secondary_target_id":None}
        b={**a,"target_id":"cat"}
        self.assertEqual(classify_disagreement(normalized(env.state),a,b,teacher),"equal_teacher_score")
        self.assertEqual(classify_disagreement(normalized(env.state),a,a,teacher),"exact_match")
        self.assertEqual(classify_disagreement(normalized(env.state),a,{**a,"target_id":"coal"},teacher),"lower_teacher_score")
        self.assertEqual(classify_disagreement(normalized(env.state),a,{**a,"action_type":1,"target_id":None},teacher),"pick_skip_disagreement")
