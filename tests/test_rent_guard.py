from dataclasses import replace
import unittest
from luck_agent.agents.rent_guard_agent import RentGuardAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.env.action import Action,ActionType as T


class RentGuardTests(unittest.TestCase):
    def env(self):return GameEnv(EnvConfig(floor=1,rule_version='instance-goldfish-v1'))

    def test_gate_equality_and_other_choices(self):
        env=self.env();agent=RentGuardAgent(env.catalog)
        env._phase='symbol';env._options=('coal','coin','flower')
        state=replace(env.state,coins=0,current_rent=26,spins_until_rent=5)
        self.assertEqual(agent.projected_cash(state),25)
        self.assertEqual(agent.choose(state,env.legal_actions()),Action(T.PICK_SYMBOL,'coin'))
        state=replace(state,current_rent=25)
        self.assertEqual(agent.choose(state,env.legal_actions()),Action(T.PICK_SYMBOL,'coal'))
        env._options=('mouse','cheese','goldfish')
        self.assertEqual(agent.choose(env.state,env.legal_actions()),HeuristicAgent(env.catalog).choose(env.state,env.legal_actions()))

    def test_lower_bound_with_soap_dilution_and_large_decks(self):
        for seed in range(30):
            env=self.env();e=env._engine
            for _ in range(seed%5):e.choose('bar_of_soap')
            for _ in range(seed%23):e.choose('coin')
            state=replace(env.state,spins_until_rent=5)
            bound=RentGuardAgent(env.catalog).projected_cash(state)-state.coins
            e.choose('coal');e.rng.seed(seed);e.spins_left=100
            income=sum(e.spin() for _ in range(5))
            self.assertLessEqual(bound,income)

    def test_wrong_backend_rejected(self):
        with self.assertRaises(ValueError):RentGuardAgent(GameEnv().catalog)
