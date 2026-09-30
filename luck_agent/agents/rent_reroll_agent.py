"""Versioned public-state reroll integration; legacy teacher stays untouched."""
from collections import Counter, OrderedDict
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import math
from random import Random
from statistics import mean, pstdev
from time import perf_counter

from luck_agent.agents.rent_forecast_agent import RentForecastAgent, rent_rank
from luck_agent.env.action import Action, ActionType as T
from luck_agent.env.offer_sampler import PreparedSymbolOffers
from luck_agent.evaluation.choice_forecast import public_engine
from luck_agent.evaluation.rent_forecast import forecast_rents
from luck_agent.evaluation.trajectory import normalized
from luck_agent.legacy.fast_env import DEFAULT_RENTS


@dataclass(frozen=True)
class RentRerollConfig:
    samples: int = 16
    cost_model: str = 'token_aware'
    # Reserve one forecast-trial resolution of future rents and one coin.
    # No first-rent penalty: a future token cannot undo an immediate payment.
    # Explicit reservation proxy, not fitted token value.
    base_cost: tuple = (0.0, .125, 1.0)
    threshold: float = 0.0
    sampling_seed: int = 20260929

    def __post_init__(self):
        if type(self.samples) is not int or not 2 <= self.samples <= 256:
            raise ValueError('Invalid candidate sample budget')
        if self.cost_model not in ('zero','constant','token_aware'):
            raise ValueError('Invalid resource cost model')
        if len(self.base_cost)!=3 or any(not math.isfinite(x) or x<0 for x in self.base_cost):
            raise ValueError('Invalid resource cost vector')
        if self.threshold!=0 or type(self.sampling_seed) is not int:
            raise ValueError('V143 fixes zero threshold and explicit independent seed')


def value(result):
    return (mean(t.first_rent_paid for t in result.trials),
            mean(t.rents_paid for t in result.trials),
            mean(t.cash for t in result.trials))


def token_cost(state, config):
    if state.reroll_tokens<=0:raise ValueError('No reroll resources')
    if config.cost_model=='zero':return (0.,0.,0.)
    if config.cost_model=='constant':return tuple(config.base_cost)
    # Reuse V142 pressure: signed gap/current rent. Urgency discounts reserving
    # a future token; remaining schedule discounts future opportunities.
    pressure=(state.current_rent-state.coins)/state.current_rent
    remaining=(len(DEFAULT_RENTS)-1-state.rent_stage)/(len(DEFAULT_RENTS)-1)
    factor=max(0,remaining)/state.reroll_tokens/(1+max(0,pressure))
    return tuple(x*factor for x in config.base_cost)


def sample_offers(state, catalog, *, samples, seed):
    if state.decision_type!='symbol' or state.reroll_tokens<=0 or not state.candidates:
        raise ValueError('Reroll not applicable')
    # Fresh public engine; never receives GameEnv or live RNG. Whitelisted
    # public counters are exactly those consumed by PreparedSymbolOffers.
    sim=public_engine(state,Action(T.SKIP_SYMBOL),catalog,0)
    for field in ('force_skip_next_choice','pending_symbol_groups',
                  'pending_symbol_rarities','rare_candidate_slots','last_shown'):
        if field in state.effect_state:setattr(sim,field,deepcopy(state.effect_state[field]))
    sim.item_counters=Counter(state.effect_state.get('item_counters',{}))
    sim.rent_index=state.rent_stage
    material=json.dumps(normalized(state),sort_keys=True,separators=(',',':'))
    fork=int.from_bytes(hashlib.sha256((str(seed)+':v143:'+material).encode()).digest()[:16],'big')
    sim.rng=Random(fork)
    sampler=PreparedSymbolOffers(sim)
    return tuple(tuple(sampler.sample()) for _ in range(samples))


class RentRerollAgent(RentForecastAgent):
    version='forecast_rents_v143'

    def __init__(self,catalog,*,config=RentRerollConfig(),**kwargs):
        super().__init__(catalog,**kwargs)
        self.config=config;self.last_evidence=None;self.cache=OrderedDict()

    def candidate_values(self,state):
        # Candidate choice forecasts are independent of which other cards were
        # offered. Score each symbol once and share across all sampled offers.
        pool=tuple(sorted(self.catalog['symbol_pool']))
        key=json.dumps(normalized((state.symbols,state.items,state.coins,state.current_rent,
             state.spins_until_rent,state.rent_stage,state.supports_stable_instances,
             state.essences,state.is_terminal,state.is_truncated,state.forced_choice,
             self.trials,self.seed,self.horizon,
             hashlib.sha256(json.dumps(self.catalog,sort_keys=True).encode()).hexdigest())),sort_keys=True)
        if key in self.cache:
            self.cache.move_to_end(key);return self.cache[key]
        expanded=replace(state,candidates=pool)
        actions=tuple(Action(T.PICK_SYMBOL,s) for s in pool)
        if not state.forced_choice:actions+=(Action(T.SKIP_SYMBOL),)
        results=forecast_rents(expanded,actions,self.catalog,horizon=self.horizon,
                               trials=self.trials,seed=self.seed)
        values={result.action:result for result in results}
        self.cache[key]=values
        if len(self.cache)>256:self.cache.popitem(last=False)
        return values

    def decide(self,state,actions):
        started=perf_counter();reroll=Action(T.REROLL)
        if reroll not in actions:
            chosen=super().choose(state,actions)
            return chosen,dict(version=self.version,reroll_available=False,
                               latency_seconds=perf_counter()-started)
        if state.decision_type!='symbol' or state.reroll_tokens<=0:
            raise ValueError('Invalid caller legal action set')
        values=self.candidate_values(state)
        current=[values[a] for a in actions if a.action_type in (T.PICK_SYMBOL,T.SKIP_SYMBOL)]
        best=min(current,key=rent_rank);current_value=value(best)
        offers=sample_offers(state,self.catalog,samples=self.config.samples,seed=self.config.sampling_seed)
        samples=[]
        for offer in offers:
            candidates=[values[Action(T.PICK_SYMBOL,s)] for s in offer]
            if Action(T.SKIP_SYMBOL) in values:candidates.append(values[Action(T.SKIP_SYMBOL)])
            samples.append(value(min(candidates,key=rent_rank)))
        expected=tuple(mean(s[i] for s in samples) for i in range(3))
        std=tuple(pstdev(s[i] for s in samples) for i in range(3))
        cost=token_cost(state,self.config)
        score=tuple(expected[i]-cost[i] for i in range(3))
        advantage=tuple(score[i]-current_value[i] for i in range(3))
        # Preserve legacy lexicographic survival/rents/cash preference.
        choose_reroll=advantage>(0.,0.,0.)
        chosen=reroll if choose_reroll else best.action
        quantiles={str(q):[sorted(s[i] for s in samples)[int(q*(len(samples)-1))] for i in range(3)] for q in (.1,.5,.9)}
        trace=dict(version=self.version,reroll_available=True,rent_stage=state.rent_stage,
            coins=state.coins,rent=state.current_rent,spins_until_rent=state.spins_until_rent,
            reroll_tokens=state.reroll_tokens,current_candidates=list(state.candidates),
            rent_pressure=(state.current_rent-state.coins)/state.current_rent,
            current_best_action=normalized(best.action),current_best_score=list(current_value),
            expected_best_after_reroll=list(expected),reroll_estimate_std=list(std),
            standard_error=[s/math.sqrt(len(samples)) for s in std],quantiles=quantiles,
            resource_cost=list(cost),cost_model=self.config.cost_model,
            reroll_score=list(score),reroll_advantage=list(advantage),
            final_teacher_action=normalized(chosen),positive_advantage=choose_reroll,
            sample_count=len(samples),sampled_offers=[list(s) for s in offers],
            latency_seconds=perf_counter()-started,
            score_units=['first_rent_pass_fraction','mean_rents_paid','mean_cash'],
            limitation='Conditional horizon30 forecast excludes future choices; vector reservation proxy is not learned/optimal token value.')
        return chosen,trace

    def choose(self,state,actions):
        chosen,self.last_evidence=self.decide(state,actions)
        return chosen
