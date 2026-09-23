from random import Random
from luck_agent.env.action import Action
from luck_agent.env.game_state import GameState


class RandomAgent:
    def __init__(self, seed: int = 0) -> None:
        self.rng = Random(seed)

    def choose(self, state: GameState, actions: tuple[Action, ...]) -> Action:
        return self.rng.choice(actions)

    def probabilities(self, state: GameState, actions: tuple[Action, ...]) -> tuple[float, ...]:
        return tuple(1 / len(actions) for _ in actions)
