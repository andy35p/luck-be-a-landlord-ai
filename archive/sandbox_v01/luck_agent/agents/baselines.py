from collections import Counter
from random import Random
from luck_agent.env.action_space import Action, ActionType as T
from luck_agent.env.state_encoder import State
from luck_agent.knowledge import Knowledge


class Agent:
    """Agents receive public State and legal candidates, never the environment."""
    def __init__(self, mode: str, seed: int = 0, synergy_weight: float = 1.0) -> None:
        if mode not in {"random", "greedy", "heuristic"}:
            raise ValueError(mode)
        self.mode, self.rng, self.db = mode, Random(seed), Knowledge()
        self.synergy_weight = synergy_weight

    def score(self, s: State, a: Action) -> float:
        if a.action_type == T.SPIN:
            return 0.0
        if a.action_type == T.REMOVE_SYMBOL:
            # v0.1 conservative heuristic; removal effects need a later ablation.
            return -1.0
        if a.action_type == T.REROLL:
            return -0.5
        if a.action_type in {T.SKIP_SYMBOL, T.SKIP_ITEM}:
            return 0.0
        counts = Counter(x.kind for x in s.deck)
        if a.action_type == T.PICK_ITEM:
            item = self.db.items[s.options[a.target]]
            return float(item["amount"] if item["effect"] == "flat" else item["amount"] * sum(bool(set(self.db.symbols[x.kind]["tags"]) & set(item["targets"])) for x in s.deck))
        kind = s.options[a.target]
        income = self.db.symbols[kind]["base_income"]
        if self.mode == "greedy":
            return float(income)
        average = sum(self.db.symbols[x.kind]["base_income"] for x in s.deck) / max(1, len(s.deck))
        synergy = sum(edge["amount"] * (counts[edge["target"]] if kind == edge["source"] else counts[edge["source"]] if kind == edge["target"] else 0)
                      for edge in self.db.interactions if edge["relation"] == "adjacent_bonus") * 0.25
        # These are ranking proxies, not calibrated EV or survival probabilities.
        pollution = average if len(s.deck) >= len(s.board) else 0.0
        shortfall = max(0, s.rent - s.coins)
        survival = income * min(1, shortfall / max(1, s.rent)) / max(1, s.spins_to_rent)
        future = 0.25 if kind == "seed" and s.spins_to_rent > 1 else 0.0
        return income + self.synergy_weight * synergy + future + 0.5 * survival - pollution

    def distribution(self, state: State, actions: tuple[Action, ...]) -> tuple[float, ...]:
        if not actions:
            raise ValueError("No legal action")
        if self.mode == "random":
            return tuple(1 / len(actions) for _ in actions)
        scores = [self.score(state, a) for a in actions]
        best = max(scores)
        ties = scores.count(best)
        return tuple(1 / ties if v == best else 0.0 for v in scores)

    def choose(self, state: State, actions: tuple[Action, ...]) -> tuple[Action, float, float]:
        p = self.distribution(state, actions)
        index = self.rng.choices(range(len(actions)), weights=p, k=1)[0]
        return actions[index], p[index], self.score(state, actions[index])
