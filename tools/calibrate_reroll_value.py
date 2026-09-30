"""V144 diagnostic only: frozen logs, public sampling, independent full rollouts.

No training dataset or policy is written. Each expensive task has an atomic cache.
Vector scores retain lexicographic units; outcome correlations are descriptive.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import replace
import gzip
import hashlib
import json
import math
import multiprocessing
import re
from pathlib import Path
from random import Random
from statistics import mean, pstdev, variance
import sys
from time import perf_counter
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.evaluate_reroll_teacher import restore, write_csv, ENV
from luck_agent.agents.rent_reroll_agent import RentRerollAgent, RentRerollConfig
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv
from luck_agent.env.action import Action, ActionType as T
from luck_agent.evaluation.trajectory import normalized

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'logs/v143-reroll'
OUT = ROOT / 'logs/v144-reroll-calibration'
NS = (8, 16, 32, 64, 128)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def dump(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def action(a):
    return Action(T(a['action_type']), a.get('target_id'), a.get('secondary_target_id'))


def trace(seed, mode='v143'):
    if mode == 'legacy' and seed < 16004:
        mode = 'shadow'
    with gzip.open(OLD / 'reroll_episode_traces' / f'{mode}-{seed}.jsonl.gz', 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def positive(vector):
    return tuple(vector) > (0, 0, 0)


def coordinate(vector):
    return next((i for i, x in enumerate(vector) if x != 0), None)


def pressure(x):
    return 'low' if x <= 0 else 'medium' if x < 1 else 'high'


def quantile(xs, q):
    xs = sorted(xs)
    p = q * (len(xs) - 1)
    lo, hi = math.floor(p), math.ceil(p)
    return xs[lo] + (xs[hi] - xs[lo]) * (p - lo)


def boundaries(rows):
    groups = defaultdict(list)
    for r in rows:
        v = r['reroll_advantage']; i = coordinate(v)
        if i is not None:
            groups[(i, positive(v))].append(abs(v[i]))
    return {f'{i}:{int(sign)}': [quantile(xs, 1/3), quantile(xs, 2/3)]
            for (i, sign), xs in groups.items()}


def bucket(v, limits):
    i = coordinate(v)
    if i is None:
        return 'exact_zero'
    sign = positive(v); lo, hi = limits[f'{i}:{int(sign)}']
    magnitude = abs(v[i])
    size = 'near_zero' if magnitude <= lo else 'moderate' if magnitude <= hi else 'strong'
    return f'axis{i}_{size}_{"positive" if sign else "negative"}'


def extract_episode(seed):
    part = load(OLD / f'v143-{seed}.json'); rows = trace(seed)
    proxy = {p['decision_id']: p for p in part['success_proxy']}
    opportunities = []
    for i, row in enumerate(rows):
        e = row.get('teacher')
        if not e or not e.get('reroll_available'):
            continue
        s = row['state']; p = proxy.get(row['step']); did = row['action']['action_type'] == T.REROLL
        following = rows[i+1]['state'] if i+1 < len(rows) else None
        if did and (p is None or following is None):
            raise ValueError('Selected reroll missing realized state')
        r = dict(e, episode_id=seed, seed=seed, decision_id=row['step'],
                 state_id=f'{seed}-{row["step"]}', rent_pressure=e['rent_pressure'],
                 pressure_group=pressure(e['rent_pressure']), reroll_tokens_before=s['reroll_tokens'],
                 deck_size=len(s['symbols']), items=s['items'], teacher_action=row['action'],
                 did_reroll=did, reroll_tokens_after=following['reroll_tokens'] if following else None,
                 new_candidates=following['candidates'] if did else None,
                 new_best_score=p['realized_after'] if did else None,
                 immediate_realized_gain=[b-a for a,b in zip(p['before'],p['realized_after'])] if did else None,
                 immediate_improved=p['improved'] if did else None,
                 final_stage=part['row']['stage'], final_reward=part['row']['reward'], win=part['row']['won'],
                 observed_offer=did, state_hash=digest(s))
        if did and r['reroll_tokens_after'] != r['reroll_tokens_before']-1:
            raise ValueError('Token decrement mismatch')
        if did != positive(e['reroll_advantage']):
            raise ValueError('Decision sign mismatch')
        opportunities.append((r,s))
    return opportunities


def freeze():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'protected_hashes.json'
    if path.exists():
        return verify()
    pins = load(OLD / 'protected_hashes.json')
    # Include all V143 artifacts, old rule/data/encoder source, and V128 shards.
    candidates = list(OLD.rglob('*')) + list((ROOT/'logs/v128-magpie-shards').rglob('*'))
    candidates += list((ROOT/'luck_agent').rglob('*.py')) + list((ROOT/'luck_agent/data').rglob('*.json'))
    candidates += list((ROOT/'reports').glob('v14[123]*'))
    for p in candidates:
        if p.is_file():
            pins[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    dump(path, pins)
    return verify()


def verify():
    pins = load(OUT / 'protected_hashes.json')
    errors = [name for name, sha in pins.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha]
    if errors:
        raise ValueError(f'Frozen assets changed: {errors}')
    return len(pins)


def select(rows):
    """Outcome strata descriptive only, deterministic pre-rollout budget of 20."""
    groups = defaultdict(list)
    for r in rows:
        groups[r['bucket']].append(r)
    selected = []
    # Systematic representation of all empirical buckets, then tokens/pressure.
    for name, group in sorted(groups.items()):
        group = sorted(group, key=lambda r: digest(r['state_id']))
        selected.extend(group[:2])
    for key in ('reroll_tokens_before', 'pressure_group'):
        for value in sorted({r[key] for r in rows}, key=str):
            eligible = [r for r in rows if r[key] == value and r not in selected]
            if eligible and len(selected)<20:
                selected.append(min(eligible,key=lambda r:digest(r['state_id'])))
    remaining = sorted((r for r in rows if r not in selected),key=lambda r:digest(r['state_id']))
    return (selected+remaining)[:20]


def cases(rows):
    outcomes = []
    byseed = defaultdict(list)
    for r in rows: byseed[r['seed']].append(r)
    for seed in range(16000,16064):
        a = load(OLD/f'legacy-{seed}.json')['row']; b = load(OLD/f'v143-{seed}.json')['row']
        outcomes.append((b['stage']-a['stage'],seed,a,b))
    for label, eligible in [('better',sorted((x for x in outcomes if x[0]>0),key=lambda x:(-x[0],x[1]))[:10]),
                            ('worse',sorted((x for x in outcomes if x[0]<0),key=lambda x:(x[0],x[1]))[:10])]:
        directory = OUT/f'{label}_cases'; directory.mkdir(exist_ok=True)
        for delta,seed,a,b in eligible:
            old,new=trace(seed,'legacy'),trace(seed)
            first=None
            for x,y in zip(old,new):
                if x['state']!=y['state']:
                    raise ValueError('Pre-divergence states unequal')
                if x['action']!=y['action']:
                    first=y['step'];break
            if first is None:
                if old!=new and delta: raise ValueError('Outcome changed without action divergence')
            episode_rows=byseed[seed]; decision=next((r for r in episode_rows if r['decision_id']==first),None)
            # A single realized gain cannot establish causality after random calls diverge.
            classification='POSSIBLY BENEFICIAL' if delta>0 and decision and decision['immediate_improved'] else 'RANDOMNESS DOMINATED'
            dump(directory/f'{seed}.json',dict(seed=seed,stage_delta=delta,legacy_outcome=a,v143_outcome=b,
                 first_divergence=first,strict_equal_prefix_decisions=first,reroll_decision=decision,
                 before_state=new[first]['state'] if first is not None else None,
                 classification=classification,causal_claim=False,
                 limitation='After the first reroll RNG consumption and trajectories diverge; paired episode outcome is not local causal evidence.',
                 legacy_trace=old,v143_trace=new,
                 later_key_decisions=[r for r in episode_rows if r['did_reroll']]))


def extract():
    freeze()
    if (OUT/'opportunities.json.gz').exists():
        return
    pairs=[p for seed in range(16000,16064) for p in extract_episode(seed)]
    rows=[p[0] for p in pairs]; limits=boundaries(rows)
    for r in rows:r['bucket']=bucket(r['reroll_advantage'],limits)
    if len(rows)!=1369 or sum(r['did_reroll'] for r in rows)!=125:
        raise ValueError('Frozen V143 count mismatch')
    with gzip.open(OUT/'opportunities.json.gz','wt',encoding='utf-8') as f:
        json.dump([dict(row=r,state=s) for r,s in pairs],f)
    write_csv(OUT/'reroll_opportunities.csv',rows)
    selected=select(rows)
    dump(OUT/'protocol.json',dict(version='V144',training_updates=0,online_episodes_added=0,
         selected_state_ids=[r['state_id'] for r in selected],bucket_limits=limits,N=list(NS),
         sampling_scope='all 1369 observed opportunities, nested public-offer samples',
         continuation_policy='frozen forecast_rents_v143 (16 samples, unchanged)',
         continuation_samples=32,branches=['current','reroll'],workers=3,
         resource_state_ids=[next(r['state_id'] for r in selected if r['reroll_tokens_before']==k) for k in (1,2)],
         continuation_seeds='sha256(v144-independent:state_id:branch:trial), disjoint independent branches; no CRN',
         primary_metrics=['final_stage','remaining_reward','win','next_rent_survival'],
         budget='20 states x 32 x 2 plus two resource states x 32; smoke 2 states x 2 trials before full execution',
         selection='empirical axis/sign tertile buckets, deterministic hashes plus token/pressure coverage; no rollout outcome selection',
         limitations='Development opportunities, conditional on observed trajectories; 20 states are not population-weighted; candidate forecasts exclude future choices.'))
    cases(rows)
    print(json.dumps(dict(opportunities=len(rows),selected=sum(r['did_reroll'] for r in rows),cf_states=len(selected))),flush=True)


def observations():
    with gzip.open(OUT/'opportunities.json.gz','rt',encoding='utf-8') as f:return json.load(f)


def sample_episode(seed):
    cache=OUT/f'sampling-{seed}.json'
    if cache.exists():return load(cache)
    agent=RentRerollAgent(GameEnv(ENV).catalog);results=[]
    for obj in observations():
        r=obj['row']
        if r['seed']!=seed:continue
        s=restore(obj['state']);acts=tuple(action(a) for a in trace_actions(s))
        # One cold catalog forecast shared across N. Hot times are not full latency.
        before=perf_counter();agent.candidate_values(s);cold=perf_counter()-before
        records=[]
        for n in NS:
            agent.config=RentRerollConfig(samples=n)
            before=perf_counter();chosen,e=agent.decide(s,acts);hot=perf_counter()-before
            if n==16 and e['reroll_advantage']!=r['reroll_advantage']:
                raise ValueError('Frozen N16 estimate mismatch')
            i=coordinate(e['reroll_advantage']);se=e['standard_error']
            ratio=abs(e['reroll_advantage'][i])/se[i] if i is not None and se[i]>0 else None
            records.append(dict(state_id=r['state_id'],seed=seed,N=n,bucket=r['bucket'],
                 advantage=e['reroll_advantage'],estimate=e['expected_best_after_reroll'],std=e['reroll_estimate_std'],
                 standard_error=se,ci95=[[x-1.96*y,x+1.96*y] for x,y in zip(e['reroll_advantage'],se)],
                 positive=e['positive_advantage'],confidence_ratio=ratio,
                 active_coordinate=i,hot_seconds=hot,shared_forecast_seconds=cold,
                 full_estimated_seconds=cold+hot,observed_improved=r['immediate_improved']))
        baseline=next(x for x in records if x['N']==16)
        for record in records:record['sign_flip_vs16']=record['positive']!=baseline['positive']
        results.extend(records)
    dump(cache,results)
    return results


def trace_actions(s):
    acts=[normalized(Action(T.PICK_SYMBOL,k)) for k in s.candidates]
    if not s.forced_choice:acts.append(normalized(Action(T.SKIP_SYMBOL)))
    if s.reroll_tokens:acts.append(normalized(Action(T.REROLL)))
    return acts


def reconstruct(state_id):
    seed,step=map(int,state_id.split('-'));env=GameEnv(ENV);env.reset(seed)
    rows=trace(seed)
    for r in rows[:step]:env.step(action(r['action']))
    if normalized(env.state)!=rows[step]['state']:
        raise ValueError('Targeted replay did not reconstruct exact state')
    if normalized(env.legal_actions())!=rows[step]['legal_actions']:
        raise ValueError('Targeted replay legal actions mismatch')
    return env,rows[step]


def independent_clone(env, state_id, branch, trial):
    snapshot=normalized(env.state);rng=env._engine.rng.getstate()
    fork=deepcopy(env)
    fork._engine.rng=Random(int(digest(['v144-independent',state_id,branch,trial]),16))
    if snapshot!=normalized(fork.state) or snapshot!=normalized(env.state) or rng!=env._engine.rng.getstate():
        raise ValueError('Clone changed public state or parent RNG')
    return fork


def rollout(env, initial, agent, start_stage):
    if initial not in env.legal_actions():raise ValueError('Illegal counterfactual branch')
    state,reward,_,_,_=env.step(initial);total=reward;steps=1;rerolls=int(initial.action_type==T.REROLL)
    while not(state.is_terminal or state.is_truncated):
        chosen=agent.choose(state,env.legal_actions())
        if chosen not in env.legal_actions():raise ValueError('Illegal continuation action')
        rerolls+=chosen.action_type==T.REROLL
        state,reward,_,_,_=env.step(chosen);total+=reward;steps+=1
    if state.is_truncated:raise ValueError('Truncated counterfactual')
    return dict(stage=state.rent_stage,reward=total,win=int(state.won),
                next_rent_survival=int(state.rent_stage>start_stage),steps=steps,rerolls=rerolls)


def counterfactual_task(state_id, branch, trial, smoke=False):
    directory=OUT/('smoke' if smoke else 'continuations');directory.mkdir(exist_ok=True)
    path=directory/f'{state_id}-{branch}-{trial}.json'
    if path.exists():return load(path)
    env,row=reconstruct(state_id);before=perf_counter()
    fork=independent_clone(env,state_id,branch,trial)
    if branch=='scarce':
        # Pure inventory intervention: same current action, one token removed.
        fork._engine.rerolls-=1
    initial=Action(T.REROLL) if branch=='reroll' else action(row['teacher']['current_best_action'])
    result=rollout(fork,initial,RentRerollAgent(fork.catalog),env.state.rent_stage)
    result.update(state_id=state_id,branch=branch,trial=trial,seconds=perf_counter()-before,
                  seed_digest=digest(['v144-independent',state_id,branch,trial]),
                  protocol_sha256=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest())
    dump(path,result)
    return result


def run_parallel(fn, tasks):
    with ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures=[pool.submit(fn,*task) for task in tasks]
        for i,future in enumerate(as_completed(futures),1):
            future.result()
            if i%8==0 or i==len(futures):print(f'{fn.__name__}: {i}/{len(futures)}',flush=True)


def run_cf(smoke=False):
    protocol=load(OUT/'protocol.json');ids=protocol['selected_state_ids']
    if smoke:
        ids=ids[:2];n=2
    else:
        gate=load(OUT/'smoke_gate.json')
        if not gate['passed']:raise ValueError('Smoke gate failed')
        n=protocol['continuation_samples']
    tasks=[(sid,b,t,smoke) for sid in ids for b in ('current','reroll') for t in range(n)]
    if not smoke:tasks += [(sid,'scarce',t,False) for sid in protocol['resource_state_ids'] for t in range(n)]
    started=perf_counter();run_parallel(counterfactual_task,tasks)
    if smoke:
        dump(OUT/'smoke_gate.json',dict(passed=True,tasks=len(tasks),seconds=perf_counter()-started,
             full_protocol_frozen_before_execution=True,checks=['exact public replay','legal actions','isolated clone RNG','full terminal outcome','no truncations']))
    else:
        rows=[load(p) for p in sorted((OUT/'continuations').glob('*.json'))]
        write_csv(OUT/'counterfactual_results.csv',rows)


def resource_addendum():
    """Frozen contextual coverage amendment; main CF protocol is untouched."""
    path=OUT/'resource_addendum.json'
    if not path.exists():
        protocol=load(OUT/'protocol.json');indexed={o['row']['state_id']:o['row'] for o in observations()}
        selected=[indexed[sid] for sid in protocol['selected_state_ids']]
        ids=[min((r for r in selected if r['reroll_tokens_before']==k),
                 key=lambda r:(r['rent_stage'],digest(r['state_id'])))['state_id'] for k in (1,2)]
        ids=[sid for sid in ids if sid not in protocol['resource_state_ids']]
        dump(path,dict(state_ids=ids,continuation_samples=32,branch='scarce',
            reason='Original resource probes are stages9/10; add earliest stage token1/2 from the existing20 to cover early reservation. No primary CF state/seed count or policy changed.',
            selector='minimum rent_stage among existing20 per token count; digest tie-break; no continuation outcome criterion',
            scope='Supplementary inventory audit, not significance-driven benchmark expansion'))
    amendment=load(path)
    run_parallel(counterfactual_task,[(sid,'scarce',t,False) for sid in amendment['state_ids'] for t in range(32)])
    rows=[load(p) for p in sorted((OUT/'continuations').glob('*.json'))]
    write_csv(OUT/'counterfactual_results.csv',rows)


def stats(x,y):
    if not x:return dict(n=0,correlation=None,mae=None,rmse=None,bias=None)
    errors=[a-b for a,b in zip(x,y)]
    sx=pstdev(x);sy=pstdev(y)
    corr=mean((a-mean(x))*(b-mean(y)) for a,b in zip(x,y))/(sx*sy) if sx and sy else None
    return dict(n=len(x),correlation=corr,mae=mean(abs(v) for v in errors),
                rmse=math.sqrt(mean(v*v for v in errors)),bias=mean(errors))


def difference(a,b,key):
    x=[r[key] for r in a];y=[r[key] for r in b]
    delta=mean(y)-mean(x)
    se=math.sqrt(variance(x)/len(x)+variance(y)/len(y))
    # A finite sample with no variation does NOT prove a deterministic outcome.
    # Use conservative bounded Hoeffding intervals instead of a spurious [0,0].
    ci=[delta-2.04*se,delta+2.04*se]
    method='approximate independent t (2.04); no multiplicity adjustment'
    if se==0:
        span=13 if key=='stage' else 1 if key in ('win','next_rent_survival') else None
        radius=span*(math.sqrt(math.log(80)/(2*len(x)))+math.sqrt(math.log(80)/(2*len(y)))) if span is not None else None
        ci=[max(-span,delta-radius),min(span,delta+radius)] if radius is not None else None
        method='bounded Hoeffding union interval; zero empirical variance' if radius is not None else 'N/A: zero variance, no verified reward bound'
    return dict(delta=delta,ci95=ci,ci_method=method,se=se,n_per_branch=[len(x),len(y)],
                branch_a_mean=mean(x),branch_b_mean=mean(y))


def build_audit():
    """Reuse existing contextual symbol scores, never interpret as causal value."""
    prior=HeuristicAgent(GameEnv(ENV).catalog).prior
    catalog=GameEnv(ENV).catalog
    rows=[]
    for label in ('better','worse'):
        for path in sorted((OUT/f'{label}_cases').glob('*.json')):
            case=load(path);state=case['before_state'];decision=case['reroll_decision']
            if state is None or decision is None:continue
            view=SimpleNamespace(catalog=catalog,deck=[s['symbol_id'] for s in state['symbols']],
                                 items=state['items'],coins=state['coins'],state=lambda:{'rent':state['current_rent']})
            neutral=SimpleNamespace(**{**vars(view),'deck':[]})
            for phase,candidates in [('current',decision['current_candidates']),('new',decision['new_candidates'])]:
                for symbol in candidates:
                    contextual=prior.score_symbol(view,symbol);empty=prior.score_symbol(neutral,symbol)
                    rows.append(dict(seed=case['seed'],group=label,offer=phase,symbol=symbol,
                        existing_heuristic_score=contextual,empty_deck_heuristic_score=empty,
                        context_contribution=contextual-empty,
                        contextual_bonus_present=contextual!=empty))
    write_csv(OUT/'build_context_scores.csv',rows)
    return {label:dict(candidate_rows=sum(r['group']==label for r in rows),
                      episodes_with_context_bonus=len({r['seed'] for r in rows if r['group']==label and r['contextual_bonus_present']}))
            for label in ('better','worse')}


def report():
    rows=[o['row'] for o in observations()];protocol=load(OUT/'protocol.json')
    sampling=[r for p in sorted(OUT.glob('sampling-*.json')) for r in load(p)]
    cf=[load(p) for p in sorted((OUT/'continuations').glob('*.json'))]
    amendment=load(OUT/'resource_addendum.json') if (OUT/'resource_addendum.json').exists() else dict(state_ids=[])
    resource_ids=protocol['resource_state_ids']+amendment['state_ids']
    if len(sampling)!=1369*len(NS) or len(cf)!=20*32*2+len(resource_ids)*32:
        raise ValueError('Incomplete frozen diagnostic protocol')
    protocol_sha=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest()
    if len({r['seed_digest'] for r in cf})!=len(cf) or any(r['protocol_sha256']!=protocol_sha for r in cf):
        raise ValueError('Continuation seed overlap or protocol mismatch')
    write_csv(OUT/'sampling_stability.csv',sampling)
    selected=[r for r in rows if r['did_reroll']];indexed={r['state_id']:r for r in rows}
    groups=defaultdict(list)
    for r in cf:groups[(r['state_id'],r['branch'])].append(r)
    results=[]
    for sid in protocol['selected_state_ids']:
        a,b=groups[(sid,'current')],groups[(sid,'reroll')]
        if len(a)!=32 or len(b)!=32:raise ValueError('Continuation count')
        results.append(dict(state_id=sid,bucket=indexed[sid]['bucket'],pressure=indexed[sid]['pressure_group'],
             tokens=indexed[sid]['reroll_tokens_before'],advantage=indexed[sid]['reroll_advantage'],
             did_reroll=indexed[sid]['did_reroll'],
             **{key:difference(a,b,key) for key in ('stage','reward','win','next_rent_survival')}))
    sample_map={(r['state_id'],r['N']):r for r in sampling}
    stability={str(n):dict(n=len(rows),sign_flip_rate=mean(sample_map[(r['state_id'],n)]['sign_flip_vs16'] for r in rows),
         selected_positive_to_negative=sum(not sample_map[(r['state_id'],n)]['positive'] for r in selected),selected_n=len(selected),
         hot_ms=1000*mean(sample_map[(r['state_id'],n)]['hot_seconds'] for r in rows),
         cold_plus_hot_ms=1000*mean(sample_map[(r['state_id'],n)]['full_estimated_seconds'] for r in rows)) for n in NS}
    immediate={str(i):stats([r['reroll_advantage'][i] for r in selected],
               [r['immediate_realized_gain'][i] for r in selected]) for i in range(3)}
    immediate['observed_sign_accuracy']=mean(r['immediate_improved'] for r in selected)
    immediate['cost_adjusted_sign_accuracy']=mean(positive([x-y for x,y in zip(r['immediate_realized_gain'],r['resource_cost'])]) for r in selected)
    immediate['gross_offer_gain_component_errors']={str(i):stats(
        [r['expected_best_after_reroll'][i]-r['current_best_score'][i] for r in selected],
        [r['immediate_realized_gain'][i] for r in selected]) for i in range(3)}
    table=[]
    for name in sorted({r['bucket'] for r in rows}):
        subset=[r for r in rows if r['bucket']==name];actual=[r for r in subset if r['did_reroll']]
        counter=[r for r in results if r['bucket']==name]
        table.append(dict(bucket=name,count=len(subset),reroll_rate=mean(r['did_reroll'] for r in subset),
             immediate_n=len(actual),immediate_improve=mean(r['immediate_improved'] for r in actual) if actual else None,
             sign_stability=1-mean(sample_map[(r['state_id'],128)]['sign_flip_vs16'] for r in subset),
             final_stage=mean(r['final_stage'] for r in subset),win_rate=mean(r['win'] for r in subset),
             mean_std=[mean(r['reroll_estimate_std'][i] for r in subset) for i in range(3)],
             cf_states=len(counter),cf_stage=mean(r['stage']['delta'] for r in counter) if counter else None,
             cf_reward=mean(r['reward']['delta'] for r in counter) if counter else None))
    resource=[]
    for sid in resource_ids:
        # Cost of losing one token without new offer: full vs scarce branch.
        d=difference(groups[(sid,'scarce')],groups[(sid,'current')],'stage')
        resource.append(dict(state_id=sid,tokens=indexed[sid]['reroll_tokens_before'],
             estimated_reservation=indexed[sid]['resource_cost'],pure_inventory_stage_value=d,
             pure_inventory_reward_value=difference(groups[(sid,'scarce')],groups[(sid,'current')],'reward'),
             pure_inventory_win_value=difference(groups[(sid,'scarce')],groups[(sid,'current')],'win'),
             pure_inventory_next_rent_value=difference(groups[(sid,'scarce')],groups[(sid,'current')],'next_rent_survival')))
    attribution=[]
    for r in selected:
        if r['immediate_improved']:continue
        flip=not sample_map[(r['state_id'],128)]['positive']
        cf_state=next((c for c in results if c['state_id']==r['state_id']),None)
        category='SAMPLING NOISE' if flip else 'NO CLEAR ERROR'
        if cf_state and cf_state['stage']['ci95'][1]<0:category='SHORT-HORIZON VALUE ERROR'
        elif cf_state and cf_state['stage']['ci95'][0]>0:category='RANDOM OUTCOME'
        attribution.append(dict(state_id=r['state_id'],category=category,
           evidence='N128 sign reversal' if flip else 'Single worse offer; no demonstrated systematic error',
           confidence='candidate explanation, not causal classification'))
    pressures={p:dict(count=sum(r['pressure_group']==p for r in rows),
          selected=sum(r['pressure_group']==p and r['did_reroll'] for r in rows),
          cf_states=sum(r['pressure']==p for r in results)) for p in ('low','medium','high')}
    confidence=[]
    for label,condition in [('ratio_le1',lambda v:v is not None and v<=1),('ratio_gt1',lambda v:v is not None and v>1),('zero_SE',lambda v:v is None)]:
        subset=[r for r in selected if condition(sample_map[(r['state_id'],16)]['confidence_ratio'])]
        confidence.append(dict(group=label,n=len(subset),failure_rate=mean(not r['immediate_improved'] for r in subset) if subset else None))
    adaptive={}
    # Research-only marginal normal intervals, not a validated lexicographic CI.
    for r in rows:
        chosen=128
        for n in (16,32,64):
            s=sample_map[(r['state_id'],n)];i=s['active_coordinate']
            if i is not None and abs(s['advantage'][i])>1.96*s['standard_error'][i] and all(s['standard_error'][j]==0 for j in range(i)):
                chosen=n;break
        adaptive[r['state_id']]=chosen
    longterm={str(i):stats([r['advantage'][i] for r in results],[r['stage']['delta'] for r in results])['correlation'] for i in range(3)}
    active_longterm={}
    for i in range(3):
        subset=[r for r in results if coordinate(r['advantage'])==i]
        active_longterm[str(i)]=dict(n=len(subset),
            stage_correlation=stats([r['advantage'][i] for r in subset],[r['stage']['delta'] for r in subset])['correlation'],
            reward_correlation=stats([r['advantage'][i] for r in subset],[r['reward']['delta'] for r in subset])['correlation'])
    flipped=stability['128']['selected_positive_to_negative']
    # No gate outcome tuning: sampling inconsistency takes precedence as diagnostic next step.
    interpretation_path=OUT/'interpretation.json'
    interpretation=load(interpretation_path) if interpretation_path.exists() else {}
    decision=interpretation.get('v145_decision','UNRESOLVED: choose V145 only after assessing the completed independent rollouts; no automatic gate from one sign flip')
    categories=('SAMPLING NOISE','RESOURCE COST ERROR','SHORT-HORIZON VALUE ERROR',
                'BUILD / SYNERGY ERROR','RANDOM OUTCOME','NO CLEAR ERROR')
    counts=Counter(r['category'] for r in attribution)
    tests_text=(OUT/'tests.txt').read_text(encoding='utf-8-sig',errors='replace')
    match=re.search(r'Ran (\d+) tests',tests_text)
    tests=dict(count=int(match.group(1)) if match else None,passed=bool(match and re.search(r'\nOK\s*$',tests_text)))
    if not tests['passed']:raise ValueError('Full test suite result missing or failed')
    result=dict(version='V144 Reroll Value Calibration',training_updates=0,
        tests=tests,
        frozen_assets_verified=verify(),opportunities=len(rows),selected=len(selected),rejected=len(rows)-len(selected),
        immediate=immediate,sampling_stability=stability,calibration_table=table,counterfactual=results,
        longterm_component_correlations=longterm,resource_cost=resource,pressure=pressures,
        longterm_active_axis_correlations=active_longterm,
        confidence_groups=confidence,adaptive_research=dict(mean_samples=mean(adaptive.values()),
            allocation=dict(Counter(adaptive.values())),disagreements_vs128=sum(sample_map[(r['state_id'],adaptive[r['state_id']])]['positive']!=sample_map[(r['state_id'],128)]['positive'] for r in rows)),
        failure_attribution=attribution,failure_counts={k:counts[k] for k in categories},
        v145_decision=decision,protocol=protocol,
        build_context=build_audit(),
        interpretation=interpretation,
        resource_addendum=amendment,
        limitations=['Observed immediate calibration covers 125 selected offers; rejected offers are N/A, not assumed failures.',
          'Three score axes are lexicographic; correlations/errors cannot be collapsed to one scalar.',
          '20 stratified states, 32 independent seeds per branch; not new holdout or population policy improvement estimate.',
          'Normal marginal sampling intervals omit inner 8-trial forecast error; nested N comparisons are correlated.',
          'Resource probe has only one state per token count; stage value and forecast rents have different horizons.',
          'Zero offer variance at a leading coordinate does not establish zero population probability.',
          'No online benchmark, parameter changes or training.'])
    dump(ROOT/'reports/v144_reroll_value_calibration.json',result)
    dump(OUT/'counterfactual_summary.json',results);dump(OUT/'failure_attribution.json',attribution)
    write_report(result)
    print(json.dumps(dict(opportunities=len(rows),sampling_flips=flipped,v145=decision)),flush=True)


def write_report(r):
    sections=[]
    def add(name,text):sections.append(f'## 【{name}】\n\n{text}\n')
    def fmt(x):return 'N/A' if x is None else f'{x:.4f}'
    add('当前版本',r['version'])
    add('本轮目标','估计是否可信；Training Updates = 0。没有新增在线 benchmark、训练或阈值调整。')
    add('冻结资产',f"核验 {r['frozen_assets_verified']} 个历史文件：Legacy/V143、V128、V130、V141–143及规则/编码源文件。hash 清单在 logs/v144-reroll-calibration/protected_hashes.json。")
    add('新增工具','tools/calibrate_reroll_value.py：完整机会提取、分量校准、嵌套样本分析、严格前缀案例、独立终局反事实和纯资源干预；每个任务缓存，支持中断后续跑。')
    add('测试结果',f"完整历史规则及现有接口测试 {r['tests']['count']} 项通过，0 Failed；新增9项V144测试覆盖全机会提取、缺失offer、lex桶、采样前缀、N16重现、signflip、clone/RNG隔离、资源补充抽样及历史hash。见 logs/v144-reroll-calibration/tests.txt。")
    add('Opportunity Dataset',f"所有 {r['opportunities']} 个机会；选择 {r['selected']}，拒绝 {r['rejected']}。拒绝状态的新候选/实际收益留空；不是失败样本。按首个非零分量、正负分别用经验三分位数分桶，不混合不同单位。")
    add('Sampling Stability',json.dumps(r['sampling_stability'],ensure_ascii=False,indent=2)+'\n\nN16→N128 正转负是决策不稳定，不是128真值；95%为逐分量正态近似区间，未计入内部8trial预测误差。')
    add('Immediate Calibration',json.dumps(r['immediate'],indent=2)+'\n\nMAE/RMSE/Bias 按概率/租金/现金独立报告。估计减成本，observed gain未减成本，两种sign accuracy分开。只覆盖selected125；立即新候选分数仍然不是实际长期因果收益。')
    add('Counterfactual Calibration',f"20个经验分层状态，每个current/reroll分支32条独立终局continuation；后续策略均为冻结V143。另{len(r['resource_cost'])}个既有状态做同动作减少1token的scarce分支各32次，共{1280+32*len(r['resource_cost'])}条正式续局，smoke8条另存。使用不同SHA种子，未假装CRN；targeted replay精确核对公开状态和legal actions，deepcopy不修改原RNG。ΔReward是决策后剩余reward，比较在同状态抵消相同历史。\n\n"+json.dumps(r['longterm_component_correlations'],indent=2)+'\n\n按实际决定分量分别分析：\n\n'+json.dumps(r['longterm_active_axis_correlations'],indent=2)+'\n\n逐状态差值与独立样本95%区间见counterfactual_summary.json。非零经验方差使用独立样本t近似，零方差用保守Hoeffding范围（无reward已验证界时N/A）；非同时区间，未校正多重比较。相关性只做描述，不证明proxy可用于排序。')
    lines=['| Advantage Bucket | Count | Immediate Improve | Sign Stability | CF ΔStage | CF ΔReward |','|---|---:|---:|---:|---:|---:|']
    for x in r['calibration_table']:lines.append(f"| {x['bucket']} | {x['count']} | {fmt(x['immediate_improve'])} (n={x['immediate_n']}) | {fmt(x['sign_stability'])} | {fmt(x['cf_stage'])} | {fmt(x['cf_reward'])} |")
    add('Advantage Buckets','\n'.join(lines)+'\n\nCF为桶内所选状态等权均值，不是总体效果；axis不同不能宣称跨桶单调。每桶终局stage/win、std和reroll率在JSON。观察终局指标按机会计权，同episode重复且机会数受存活影响，不能当成独立episode比较。')
    for name,label in [('Better Cases','better'),('Worse Cases','worse')]:
        cs=[load(p) for p in sorted((OUT/f'{label}_cases').glob('*.json'))]
        add(name,'\n'.join(f"- seed{x['seed']}: ΔStage={x['stage_delta']:+}, first divergence={x['first_divergence']}; {x['classification']}" for x in cs)+'\n\n完整两条轨迹、首分歧前state、估值、新候选、后续重掷及outcome在对应目录。只在首分歧前声称严格同轨迹。')
    add('Resource Cost',json.dumps(r['resource_cost'],indent=2)+'\n\n纯inventory probe不是reroll效果；按token数量、早/晚期分开，少量状态无法检验系统偏差。实际3+token机会不存在，N/A。cost中租金分量非零会在firstpass相等、rents相等时拒绝任意cash收益：这是词典序结构效应，不能凭此认定成本错误。\n\n'+json.dumps(r['resource_addendum'],ensure_ascii=False,indent=2))
    add('Rent Pressure',json.dumps(r['pressure'],indent=2)+'\n\n保持V142 signed gap/rent：low≤0，medium(0,1)，high≥1。high无在线机会，拒绝后死亡案例N/A，不用人工fixture替代自然证据。')
    add('Build / Synergy',json.dumps(r['build_context'],indent=2)+'\n\n直接复用已有Heuristic score_symbol，记录当前deck与empty deck评分差；这是旧启发式context贡献，不是新Build Score，也不是Teacher长期synergy真值。逐候选见build_context_scores.csv。BUILD/SYNERGY ERROR因果计数N/A，不能由长期失败反推build破坏。')
    add('Compute Tradeoff','catalog预测共享给8/16/32/64/128；hot_ms仅抽offer与汇总，cold_plus_hot_ms（历史字段名）包含首次forecast或cache lookup成本，连续重掷可能命中已有cache，不能视为严格全冷计时。不同N并非重算所有候选。\n\n'+json.dumps(r['adaptive_research'],indent=2)+'\n\n自适应仅研究：领先分量SE为0时的置信比可能虚高，未替换policy。')
    add('Failure Attribution',json.dumps(r['failure_counts'],indent=2)+'\n\n仅37个立即未改善offer；sampling flip是候选解释，不能证明该offer由采样噪声造成。RESOURCE COST ERROR / BUILD ERROR未被证实；随机坏offer不等于错误动作。逐例证据与不确定性在failure_attribution.json。')
    add('结论',f"立即改善88/125=70.4%，受选择偏差，不能回答所有机会的校准。长期只做20状态独立反事实，不能宣称V143更强或无效。N16正转负={r['sampling_stability']['128']['selected_positive_to_negative']}/125；先审查采样可靠性。资源偏差没有充分证据。危险候选包括低有效分量margin、领先分量零样本方差、连续消耗最后token；属于待验证风险，非已证明错误。V143保持冻结作为审计参照，暂不认定可靠的新标签教师。")
    add('V145 决策',r['v145_decision']+'。BC train符号fit≈72.9%问题继续保留，本轮未训练；不根据终局结果手调成本。')
    if r['interpretation']:
        add('七项问题与证据边界',json.dumps(r['interpretation'],ensure_ascii=False,indent=2))
    (ROOT/'reports/v144_reroll_value_calibration.md').write_text('\n'.join(sections),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['extract','sample','smoke','cf','resource','report','verify'])
    args=parser.parse_args()
    if args.mode=='extract':extract()
    elif args.mode=='sample':run_parallel(sample_episode,[(seed,) for seed in range(16000,16064)])
    elif args.mode=='smoke':run_cf(True)
    elif args.mode=='cf':run_cf()
    elif args.mode=='resource':resource_addendum()
    elif args.mode=='report':report()
    else:print(verify())
