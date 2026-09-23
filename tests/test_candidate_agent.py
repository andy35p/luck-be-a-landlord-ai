import unittest
from luck_agent.agents.candidate_agent import CandidateAgent, first_candidate_scores
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import Action, ActionType as T
from luck_agent.evaluation.batching import CandidateEncoder
from luck_agent.evaluation.trajectory import normalized


class CandidateAgentTests(unittest.TestCase):
    def env(self): return GameEnv(EnvConfig(floor=1, rule_version="instance-coal-v1"))

    def test_single_action_bypasses_scorer(self):
        def fail(_): self.fail("Scorer called for sole action")
        env = self.env(); agent = CandidateAgent(fail, rule_version="instance-coal-v1")
        self.assertEqual(agent.choose(env.state, env.legal_actions()), Action(T.SPIN))

    def test_exact_instance_mapping_and_feature_boundary(self):
        env = self.env(); env._engine.choose("coal"); env._engine.choose("coal")
        env._engine.removals=1; env._phase="remove"
        target = env.state.symbols[-1].instance_id
        def score(f):
            self.assertEqual(set(f), {"scalars", "deck", "items", "candidates", "candidate_mask"})
            return [a[3] for a in f["candidates"]]
        agent = CandidateAgent(score, rule_version="instance-coal-v1")
        rng=env._engine.rng.getstate()
        action=agent.choose(env.state, env.legal_actions())
        self.assertEqual(action, Action(T.REMOVE_SYMBOL, target))
        self.assertEqual(env._engine.rng.getstate(), rng)
        env.step(action)
        self.assertNotIn(target, {s.instance_id for s in env.state.symbols})

    def test_online_offline_encoding_equal(self):
        env=self.env(); env._phase="symbol"; env._options=("coal","coin")
        state, actions=normalized(env.state),normalized(env.legal_actions())
        encoder=CandidateEncoder()
        online=encoder.encode_observation(state,actions)
        offline=encoder.encode({"state":state,"legal_actions":actions,"action_mask":[True]*len(actions),
            "action":actions[1],"reward":999,"terminated":False,"truncated":False,"episode_seed":10,"step":4},"test")
        for k in ("scalars","deck","items","candidates"): self.assertEqual(online[k],offline[k])

    def test_bad_scorer_rejected(self):
        env=self.env();env._phase="symbol";env._options=("coal","coin")
        for scorer in (lambda f: [], lambda f: [float("nan")]*len(f["candidates"])):
            with self.assertRaises(ValueError): CandidateAgent(scorer,rule_version="instance-coal-v1").choose(env.state,env.legal_actions())

    def test_complete_episode_matches_direct_first_action(self):
        for seed in range(5):
            a,b=self.env(),self.env();a.reset(seed);b.reset(seed)
            agent=CandidateAgent(first_candidate_scores,rule_version="instance-coal-v1")
            while not(a.state.is_terminal or a.state.is_truncated):
                self.assertEqual(a.step(agent.choose(a.state,a.legal_actions())),b.step(b.legal_actions()[0]))
