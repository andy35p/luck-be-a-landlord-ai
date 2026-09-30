"""Conditional fixed-deck forecasts from public state, never the live RNG.

All choices use the same instance engine and trial seed. Future picks, removals,
rerolls and rent payments are excluded; pass_fraction is not actual survival.
"""
from dataclasses import dataclass
import math
import statistics
from luck_agent.env.action import ActionType
from luck_agent.env.instance_magpie_engine import InstanceMagpieEngine
from luck_agent.env.instance_store import InstanceStore


@dataclass(frozen=True)
class ChoiceForecast:
    action: object
    incomes: tuple[float, ...]
    mean_income: float
    projected_cash_mean: float
    conditional_rent_coverage: float


def validate_choices(state, actions, catalog, *, trials, seed):
    if catalog.get('catalog_source') != 'recovered_catalog:instance-magpie-v1-subset':
        raise ValueError('Forecast requires instance-magpie-v1')
    if type(trials) is not int or not 1 <= trials <= 256 or type(seed) is not int:
        raise ValueError('Invalid independent simulation budget')
    horizon=state.spins_until_rent
    if type(horizon) is not int or not 1 <= horizon <= 100:
        raise ValueError('Invalid rent horizon')
    if (not state.supports_stable_instances or state.essences or state.is_terminal or state.is_truncated
            or state.decision_type not in ('symbol','forced_symbol')):
        raise ValueError('Unsupported public decision state')
    if not math.isfinite(state.coins) or type(state.current_rent) is not int or state.current_rent < 0:
        raise ValueError('Invalid public economy')
    identities=set()
    for symbol in state.symbols:
        if (symbol.identity_scope!='episode' or not symbol.instance_id or symbol.instance_id in identities
                or type(symbol.permanent_bonus) not in (int,float) or not math.isfinite(symbol.permanent_bonus)):
            raise ValueError('Incomplete public symbol identity or bonus')
        identities.add(symbol.instance_id)
    if not actions or len(set(actions))!=len(actions):raise ValueError('Missing or duplicate choices')
    for action in actions:
        if action.action_type==ActionType.PICK_SYMBOL:
            if action.target_id not in state.candidates:raise ValueError('Candidate not offered')
        elif action.action_type==ActionType.SKIP_SYMBOL:
            if state.forced_choice or action.target_id is not None:raise ValueError('Invalid skip')
        else:raise ValueError('Only symbol picks and skip can be forecast')
        if action.secondary_target_id is not None:raise ValueError('Unexpected secondary target')


def public_engine(state, action, catalog, seed):
    # Construct fresh engines with unrelated, explicit experimental seeds.
    # Never read effect_state, clone GameEnv, or copy its RNG.
    engine=InstanceMagpieEngine(catalog,seed=seed,floor=1)
    engine.instances=InstanceStore(engine.supported_symbols)
    engine.items=list(state.items)
    for symbol in state.symbols:
        expected=engine.initial_lifetime(symbol.symbol_id)
        remaining=symbol.remaining_appearances
        if expected is not None and (type(remaining) is not int or remaining <= 0):
            raise ValueError('Missing public timer')
        if expected is None and remaining is not None:raise ValueError('Unexpected public timer')
        engine.instances.add(symbol.symbol_id,permanent_bonus=symbol.permanent_bonus,
                             remaining_appearances=remaining)
    engine._sync_deck()
    engine._validate_supported_state()
    if action.action_type==ActionType.PICK_SYMBOL:engine.choose(action.target_id)
    engine.coins=state.coins
    return engine


def forecast_choices(state, actions, catalog, *, trials=16, seed=0):
    validate_choices(state, actions, catalog, trials=trials, seed=seed)
    horizon=state.spins_until_rent
    results=[]
    for action in actions:
        incomes=[]
        for trial in range(trials):
            engine=public_engine(state, action, catalog, seed+trial)
            engine.spins_left=horizon+1  # Project income without resolving rent.
            incomes.append(sum(engine.spin() for _ in range(horizon)))
        values=tuple(incomes);mean=statistics.mean(values)
        results.append(ChoiceForecast(action,values,mean,state.coins+mean,
            sum(state.coins+x>=state.current_rent for x in values)/trials))
    return tuple(results)
