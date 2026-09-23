"""Conservative reroll extension; estimates use only a public-state reconstruction."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from random import Random
import statistics
from types import SimpleNamespace
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.action import Action, ActionType as T
from luck_agent.env.game_state import GameState
from luck_agent.env.rule_engine import RuleEngine
from luck_agent.env.offer_sampler import PreparedSymbolOffers


@dataclass(frozen=True)
class RerollConfig:
    trials: int = 16
    token_margin: float = 0.5
    uncertainty_multiplier: float = 1.96

    def __post_init__(self) -> None:
        if self.trials < 2 or self.token_margin < 0 or self.uncertainty_multiplier < 0:
            raise ValueError("Invalid reroll configuration")


class RerollHeuristicAgent(HeuristicAgent):
    def __init__(self, catalog: dict | None = None, config: RerollConfig = RerollConfig(),
                 sampler_backend: str = "prepared") -> None:
        super().__init__(catalog)
        if sampler_backend not in {"reference", "prepared"}:
            raise ValueError("Unknown sampler backend")
        self.sampler_backend = sampler_backend
        self.config = config
        self.last_evidence: dict | None = None

    def estimate(self, state: GameState) -> dict:
        # A fresh simulation, never a copy of the live engine or its RNG.
        sim = RuleEngine(self.catalog, seed=0)
        for name, value in state.effect_state.items():
            if name not in {"seed", "rng", "catalog"}:
                setattr(sim, name, deepcopy(value))
        material = json.dumps(state.effect_state, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(("reroll-v02:" + material + repr(state.candidates)).encode()).digest()
        sim.rng = Random(int.from_bytes(digest[:16], "big"))
        view = SimpleNamespace(catalog=self.catalog, deck=[s.symbol_id for s in state.symbols],
                               items=state.items, coins=state.coins,
                               state=lambda: {"rent": state.current_rent})
        threshold = 0.8 if len(state.symbols) < 20 else 2.0
        def utility(offer: tuple[str, ...] | list[str]) -> float:
            best = max((self.prior.score_symbol(view, x) for x in offer), default=threshold)
            return best - threshold if state.forced_choice else max(0.0, best - threshold)
        current = utility(state.candidates)
        if self.sampler_backend == "prepared":
            prepared = PreparedSymbolOffers(sim)
            samples = [utility(prepared.sample()) for _ in range(self.config.trials)]
        else:
            samples = [utility(sim.candidates("symbol")) for _ in range(self.config.trials)]
        expected = statistics.mean(samples)
        se = statistics.stdev(samples) / math.sqrt(len(samples))
        margin = self.config.token_margin + 0.5 / max(1, state.reroll_tokens)
        lower_gain = expected - current - self.config.uncertainty_multiplier * se
        return {"current_utility": current, "expected_offer_utility": expected,
                "standard_error": se, "token_cost_proxy": margin,
                "conservative_gain": lower_gain, "reroll": lower_gain > margin,
                "trials": self.config.trials,
                "note": "Heuristic score utility, not coin EV; Monte Carlo SE is approximate."}

    def choose(self, state: GameState, actions: tuple[Action, ...]) -> Action:
        self.last_evidence = None
        reroll = Action(T.REROLL)
        if reroll in actions:
            self.last_evidence = self.estimate(state)
            if self.last_evidence["reroll"]:
                return reroll
        return super().choose(state, actions)
