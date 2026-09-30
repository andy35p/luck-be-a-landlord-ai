import unittest

from luck_agent.env.action import Action, ActionType as T
from luck_agent.env.game_env import EnvConfig, GameEnv
from luck_agent.evaluation.decision_coverage import (finalize_diagnostics, new_diagnostics,
                                                     record_decision)


class DecisionCoverageTests(unittest.TestCase):
    def test_available_but_never_selected_is_distinct_from_never_available(self):
        result = new_diagnostics({"agent": "fixture"})
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-magpie-v1"))
        state = env.state
        actions = (Action(T.PICK_SYMBOL, "coin"), Action(T.SKIP_SYMBOL), Action(T.REROLL))
        self.assertTrue(record_decision(result, seed=1, step=0, state=state, actions=actions,
                                        chosen=actions[0]))
        result = finalize_diagnostics(result)
        self.assertEqual(result["coverage"]["REROLL"]["status"], "available_never_selected")
        self.assertEqual(result["coverage"]["SELECT_INTERACTION"]["status"], "never_available")
        self.assertEqual(result["coverage"]["PICK_SYMBOL"]["chosen_rate"], 1)

    def test_illegal_choice_is_counted_and_rejected(self):
        result = new_diagnostics({"agent": "fixture"})
        env = GameEnv(EnvConfig(floor=1, rule_version="instance-magpie-v1"))
        chosen = Action(T.SKIP_SYMBOL)
        self.assertFalse(record_decision(result, seed=1, step=0, state=env.state,
                                         actions=(Action(T.SPIN),), chosen=chosen))
        self.assertEqual(result["coverage"]["SKIP_SYMBOL"]["illegal_count"], 1)


if __name__ == "__main__":
    unittest.main()
