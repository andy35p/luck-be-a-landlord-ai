"""Experimental public-state cross-rent policy, with no live defaults."""
from statistics import mean
from luck_agent.agents.forecast_agent import ForecastAgent
from luck_agent.env.action import ActionType as T
from luck_agent.evaluation.rent_forecast import forecast_rents


def rent_rank(result):
    # Lexicographic risk preference, not an estimated optimal Q function.
    return (-mean(t.first_rent_paid for t in result.trials),
            -mean(t.rents_paid for t in result.trials),
            -mean(t.cash for t in result.trials),
            result.action.action_type != T.SKIP_SYMBOL,
            result.action.target_id or "")


class RentForecastAgent(ForecastAgent):
    def __init__(self,catalog,*,trials=8,seed=20270927,horizon=30):
        super().__init__(catalog,trials=trials,seed=seed)
        if type(horizon) is not int or not 10 <= horizon <= 100:
            raise ValueError("Policy horizon must cover every current rent interval")
        self.horizon=horizon

    def choose(self,state,actions):
        if state.decision_type not in ("symbol","forced_symbol"):
            return super().choose(state,actions)
        choices=tuple(a for a in actions if a.action_type in (T.PICK_SYMBOL,T.SKIP_SYMBOL))
        results=forecast_rents(state,choices,self.catalog,horizon=self.horizon,
                               trials=self.trials,seed=self.seed)
        return min(results,key=rent_rank).action
