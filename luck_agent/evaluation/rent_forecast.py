"""Bounded cross-rent forecasts with explicit payments and death stops.

Future offered choices/items/resources are ignored. This is a conditional rollout,
not a calibrated survival probability or an agent policy.
"""
from dataclasses import dataclass
from luck_agent.evaluation.choice_forecast import validate_choices, public_engine
from luck_agent.legacy.fast_env import DEFAULT_RENTS


@dataclass(frozen=True)
class RentTrial:
    income: float
    cash: float
    rents_paid: int
    spins: int
    died: bool
    won: bool
    first_rent_paid: bool


@dataclass(frozen=True)
class RentForecast:
    action: object
    trials: tuple[RentTrial, ...]


def forecast_rents(state, actions, catalog, *, horizon=30, trials=8, seed=0):
    validate_choices(state, actions, catalog, trials=trials, seed=seed)
    if type(horizon) is not int or not 1 <= horizon <= 100:
        raise ValueError("Invalid cross-rent horizon")
    stage=state.rent_stage
    if (type(stage) is not int or not 0 <= stage < len(DEFAULT_RENTS)
            or state.current_rent != DEFAULT_RENTS[stage][0]
            or state.spins_until_rent > DEFAULT_RENTS[stage][1]):
        raise ValueError("Public rent state does not match the supported schedule")
    results=[]
    for action in actions:
        samples=[]
        for trial in range(trials):
            engine=public_engine(state,action,catalog,seed+trial)
            engine.rent_index=stage
            engine.spins_left=state.spins_until_rent
            income=0.0
            spins=0
            for _ in range(horizon):
                if engine.done: break
                income += engine.spin()
                spins += 1
            paid=engine.rent_index-stage
            samples.append(RentTrial(income,engine.coins,paid,spins,
                                     engine.done and not engine.won,engine.won,paid>0))
        results.append(RentForecast(action,tuple(samples)))
    return tuple(results)
