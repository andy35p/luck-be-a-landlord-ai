from types import SimpleNamespace
from math import isfinite
from luck_agent.env.action import Action, ActionType as T
from luck_agent.env.game_state import GameState
from luck_agent.env.rule_engine import load_catalog
from luck_agent.legacy.fast_env import HeuristicAgent as PriorHeuristic


class CoalScoreHeuristic(PriorHeuristic):
    def __init__(self, adjustment):
        self.adjustment = adjustment

    def score_symbol(self, env, candidate):
        return super().score_symbol(env, candidate) + (self.adjustment if candidate == "coal" else 0)


class HeuristicAgent:
    """Reuse prior public-state scoring, without exposing engine or its RNG.

    Prior choose_position deep-copied live RNG; deliberately excluded here.
    Position actions conservatively skip until a public-state evaluator exists.
    """
    def __init__(self, catalog: dict | None = None, *, coal_score_adjustment: float = 0.0) -> None:
        if not isfinite(coal_score_adjustment):
            raise ValueError("Coal score adjustment must be finite")
        self.catalog = catalog if catalog is not None else load_catalog()
        self.prior = CoalScoreHeuristic(coal_score_adjustment)

    def choose(self, state: GameState, actions: tuple[Action, ...]) -> Action:
        if not actions:
            raise ValueError("No legal action")
        view = SimpleNamespace(catalog=self.catalog, deck=[s.symbol_id for s in state.symbols],
                               items=state.items, coins=state.coins,
                               force_add_next_choice=state.forced_choice,
                               state=lambda: {"rent": state.current_rent})
        phase = state.decision_type
        if phase in {"symbol", "forced_symbol"}:
            choice = self.prior.choose_symbol(view, state.candidates)
            desired = Action(T.SKIP_SYMBOL) if choice == "skip" else Action(T.PICK_SYMBOL, choice)
        elif phase == "item":
            choice = self.prior.choose_item(view, state.candidates)
            desired = Action(T.SKIP_ITEM) if choice == "skip" else Action(T.PICK_ITEM, choice)
        elif phase == "essence":
            desired = Action(T.PICK_ESSENCE, self.prior.choose_essence(view, state.candidates))
        elif phase == "remove":
            removals = [a for a in actions if a.action_type == T.REMOVE_SYMBOL]
            # Resolve actual IDs through this observation, never parse type names.
            kinds = {s.instance_id:s.symbol_id for s in state.symbols}
            value = lambda a: self.catalog["symbol_values"].get(kinds[a.target_id], 0)
            worst = min(removals, key=value, default=None)
            desired = worst if worst and value(worst) < 1 else Action(T.KEEP_OPTIONS)
        elif phase == "interact":
            desired = next((a for a in actions if a.action_type == T.SELECT_INTERACTION and
                            (a.target_id != "use:comfy_pillow" or state.coins >= state.current_rent)), Action(T.KEEP_OPTIONS))
        elif phase == "position":
            desired = Action(T.SELECT_INTERACTION, "skip")
        else:
            desired = Action(T.SPIN)
        return desired if desired in actions else actions[0]

    def probabilities(self, state: GameState, actions: tuple[Action, ...]) -> tuple[float, ...]:
        chosen = self.choose(state, actions)
        return tuple(float(a == chosen) for a in actions)
