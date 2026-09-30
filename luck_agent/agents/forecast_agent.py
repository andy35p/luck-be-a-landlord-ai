"""Experimental fixed-horizon income policy; never enabled in live advice."""
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.action import ActionType
from luck_agent.evaluation.choice_forecast import forecast_choices


class ForecastAgent(HeuristicAgent):
    def __init__(self, catalog, *, trials=8, seed=20270927):
        if catalog.get("catalog_source") != "recovered_catalog:instance-magpie-v1-subset":
            raise ValueError("Forecast agent requires instance-magpie-v1")
        if type(trials) is not int or not 1 <= trials <= 256 or type(seed) is not int:
            raise ValueError("Invalid forecast budget")
        super().__init__(catalog)
        self.trials, self.seed = trials, seed

    def choose(self, state, actions):
        if state.decision_type not in ("symbol", "forced_symbol"):
            return super().choose(state, actions)
        choices = tuple(a for a in actions if a.action_type in
                        (ActionType.PICK_SYMBOL, ActionType.SKIP_SYMBOL))
        forecasts = forecast_choices(state, choices, self.catalog,
                                     trials=self.trials, seed=self.seed)
        # One comparable objective for every candidate. Exact ties prefer skip,
        # then the stable symbol identifier, independently of input ordering.
        return min(forecasts, key=lambda r: (-r.mean_income,
                   r.action.action_type != ActionType.SKIP_SYMBOL,
                   r.action.target_id or "")).action
