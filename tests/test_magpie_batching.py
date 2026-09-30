import unittest
from dataclasses import replace,asdict
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.env.game_state import SymbolInstance
from luck_agent.env.action import Action,ActionType as T
from luck_agent.evaluation.trajectory import normalized
from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder,collate_magpie
from luck_agent.evaluation.spatial_batching import SpatialCandidateEncoder,collate_spatial


class MagpieBatchingTests(unittest.TestCase):
    def test_timer_and_separate_vocabulary_contract(self):
        env=GameEnv(EnvConfig(floor=1,rule_version='instance-magpie-v1'))
        state=replace(env.state,symbols=(SymbolInstance('x','magpie',0,3,'episode'),))
        observation=normalized(state);actions=[asdict(Action(T.PICK_SYMBOL,'magpie'))]
        encoder=MagpieCandidateEncoder();sample=encoder.encode_observation(observation,actions)
        self.assertEqual(sample['deck'][0],[encoder.symbols['magpie'],0,3,1])
        self.assertEqual(sample['candidates'][0][1],encoder.symbols['magpie'])
        self.assertEqual(encoder.features(sample)['candidate_mask'],[True])
        with self.assertRaises(ValueError):SpatialCandidateEncoder.features(sample)
        with self.assertRaises(ValueError):collate_spatial([sample])
        old={'encoder_version':SpatialCandidateEncoder.version}
        with self.assertRaises(ValueError):collate_magpie([old])
        with self.assertRaises(ValueError):encoder.features(old)
