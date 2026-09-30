"""V145: opt-in diagnostic rollouts, never an online policy or training source."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import pickle
import re
from random import Random
from statistics import mean, variance, pstdev
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.calibrate_reroll_value import (ROOT, OUT as V144, OLD as V143, load, dump,
    digest, action, coordinate, positive, observations, reconstruct, stats, difference)
from tools.evaluate_reroll_teacher import ENV, write_csv
from luck_agent.env.game_env import GameEnv
from luck_agent.env.action import Action, ActionType as T
from luck_agent.agents.rent_reroll_agent import RentRerollAgent
from luck_agent.evaluation.trajectory import normalized

OUT=ROOT/'logs/v145-rollout'
HORIZONS=(1,2,3,'end')
WORKER_PARENTS={}
WORKER_AGENTS={}


def sign(x):return (x>0)-(x<0)


def classify(local,longterm):
    if longterm==0:return 'ZERO LONG-TERM PROXY'
    return ('TRUE POSITIVE PROXY' if local>0 else 'FALSE NEGATIVE PROXY') if longterm>0 else ('FALSE POSITIVE PROXY' if local>0 else 'TRUE NEGATIVE PROXY')


def rank(xs):
    ordered=sorted(range(len(xs)),key=lambda i:xs[i]);result=[0.]*len(xs);j=0
    while j<len(xs):
        k=j+1
        while k<len(xs) and xs[ordered[k]]==xs[ordered[j]]:k+=1
        for index in ordered[j:k]:result[index]=(j+k-1)/2
        j=k
    return result


def relationships(x,y):
    n=len(x)
    return dict(n=n,pearson=stats(x,y)['correlation'] if n>=3 else None,
        spearman=stats(rank(x),rank(y))['correlation'] if n>=3 else None,
        sign_agreement=mean(sign(a)==sign(b) for a,b in zip(x,y)) if n else None,
        decisive_n=sum(b!=0 for b in y),
        decisive_sign_agreement=mean(sign(a)==sign(b) for a,b in zip(x,y) if b!=0) if any(y) else None)


def frozen_check():
    pins=load(OUT/'protected_hashes.json')
    changed=[name for name,sha in pins.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
    if changed:raise ValueError(f'Historical asset changed: {changed}')
    return len(pins)


def setup():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protocol.json').exists():frozen_check();return
    pins=load(V144/'protected_hashes.json')
    for p in list(V144.rglob('*'))+[ROOT/'reports/v144_reroll_value_calibration.md',ROOT/'reports/v144_reroll_value_calibration.json',ROOT/'tools/calibrate_reroll_value.py']:
        if p.is_file():pins[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    dump(OUT/'protected_hashes.json',pins);frozen_check()
    allrows=[o['row'] for o in observations()]
    main=sorted({r['bucket'] for r in allrows if coordinate(r['reroll_advantage'])==1})
    if len(main)!=6:raise ValueError('Unexpected primary strata')
    selected=[];seen=set()
    for depth in range(6):
        for name in main:
            eligible=sorted((r for r in allrows if r['bucket']==name and r not in selected),key=lambda r:digest(['v145-selection',r['state_id']]))
            chosen=next((r for r in eligible if r['seed'] not in seen),eligible[0])
            selected.append(chosen);seen.add(chosen['seed'])
    # Represent rare probability/cash coordinates without mixing their units.
    for axis in (0,2):
        eligible=sorted((r for r in allrows if coordinate(r['reroll_advantage'])==axis),key=lambda r:digest(['v145-selection',r['state_id']]))
        selected.extend(eligible[:2])
    pilot=[next(r['state_id'] for r in selected if r['bucket']==name) for name in main]
    pilot += [next(r['state_id'] for r in selected if r['bucket']==name and r['state_id'] not in pilot) for name in main]
    convergence=[next(r['state_id'] for r in selected if r['bucket']==name) for name in main if 'near_zero' in name or 'strong' in name]
    dump(OUT/'selected_states.json',dict(source_opportunities=len(allrows),selection='6 states per six primary rent-axis strata, two per rare axis; independent SHA order, prefer distinct episodes; no continuation outcome criterion',
        selected=selected,pilot_state_ids=pilot,convergence_state_ids=convergence))
    protocol=dict(version='V145',training_updates=0,online_benchmark_added=0,continuation='frozen forecast_rents_v143',
        horizons=list(HORIZONS),pilot_states=12,pilot_K=8,convergence_states=4,convergence_K=[8,16,32,64],
        formal_states=40,formal_K=32,workers=3,
        seed_namespace='sha256([v145-independent,state_id,branch,continuation_id])',
        pairing='trial labels match, engine seeds differ across branches; no semantic CRN',
        primary='stage gain',secondary='remaining reward',
        sampling_gate='K32 is a frozen measurement budget, not automatically increased. K32/64 directional agreement>=75% for stage AND reward across4 pilot states is evidence of point-sign stability; CI crossing zero is separately reported. If insufficient, retain32 with uncertainty and assess stopping Reroll research; never automatically use maximumK.',
        workflow='pilot only one rent, then extend four pilot states through full episode for convergence; reuse snapshots and already sampled paths in formal40x32.',
        hard_stop='Unless finite lookahead yields repeatable stronger long-horizon signal, freeze reroll and prioritize BC fit. No policy revision, training or parameter fitting in V145.')
    dump(OUT/'protocol.json',protocol)
    (OUT/'clones').mkdir(exist_ok=True);(OUT/'continuations').mkdir(exist_ok=True)
    # Local pickle is trusted diagnostic transport of complete engine/RNG state.
    for r in selected:
        env,row=reconstruct(r['state_id'])
        payload=dict(env=env,state=normalized(env.state),rng_state=env._engine.rng.getstate(),
                     legal_actions=normalized(env.legal_actions()),teacher=row['teacher'],row=r,
                     catalog_sha=digest(env.catalog),python=sys.version)
        path=OUT/'clones'/f"{r['state_id']}.pkl"
        path.write_bytes(pickle.dumps(payload,protocol=pickle.HIGHEST_PROTOCOL))
    dump(OUT/'clone_hashes.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'clones').glob('*.pkl')})
    print(json.dumps(dict(states=len(selected),pilot=len(pilot),convergence=len(convergence))),flush=True)


def parent(state_id):
    if state_id not in WORKER_PARENTS:
        path=OUT/'clones'/f'{state_id}.pkl'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=load(OUT/'clone_hashes.json')[path.name]:raise ValueError('Clone artifact hash')
        payload=pickle.loads(path.read_bytes())
        if normalized(payload['env'].state)!=payload['state'] or payload['env']._engine.rng.getstate()!=payload['rng_state']:raise ValueError('Clone transport changed state')
        WORKER_PARENTS[state_id]=payload
    return WORKER_PARENTS[state_id]


def fork_env(env,state_id,branch,trial):
    before=normalized(env.state);rng=env._engine.rng.getstate();fork=deepcopy(env)
    fork._engine.rng=Random(int(digest(['v145-independent',state_id,branch,trial]),16))
    if normalized(fork.state)!=before or normalized(env.state)!=before or env._engine.rng.getstate()!=rng:
        raise ValueError('Parent state or RNG mutated')
    return fork


def reproducibility_probe(state_id):
    """Read-only one-rent probe for executor independence tests."""
    base=parent(state_id)['env'];env=fork_env(base,state_id,'reroll',0)
    acc,_,_,_=walk(env,Action(T.REROLL),RentRerollAgent(env.catalog),1)
    return dict(state_sha=digest(normalized(env.state)),rng_sha=digest(env._engine.rng.getstate()),metrics=acc)


def reached(state,start,horizon):
    return state.is_terminal or state.is_truncated or (horizon!='end' and state.rent_stage>=min(start+int(horizon),13))


def metric(env,start,initial_coins,acc,horizon,elapsed):
    s=env.state;target=13 if horizon=='end' else min(start+int(horizon),13)
    return dict(horizon=horizon,stage_gain=s.rent_stage-start,stage_at_cut=s.rent_stage,
        reward_gain=acc['reward'],net_coins_gained=s.coins-initial_coins,spin_income=acc['income'],
        rent_survival=int(s.rent_stage>=target),final_stage=s.rent_stage if s.is_terminal else None,
        final_reward=acc['reward'] if s.is_terminal else None,win=int(s.won) if s.is_terminal else None,
        terminal=s.is_terminal,truncated=s.is_truncated,reached_requested_boundary=s.rent_stage>=target,
        elapsed_seconds=elapsed,decisions=acc['decisions'],rerolls_used=acc['rerolls'],
        future_reroll_opportunities=acc['opportunities'],tokens_after=s.reroll_tokens,
        deck_counts=dict(Counter(x.symbol_id for x in s.symbols)),items=list(s.items))


def walk(env,first,agent,max_horizon,acc=None,checkpoints=None,elapsed_before=0,initial_state=None,trace_rows=None):
    initial_state=initial_state or env.state;start=initial_state.rent_stage;coins=initial_state.coins
    acc=acc or dict(reward=0.,income=0.,decisions=0,rerolls=0,opportunities=0)
    checkpoints=checkpoints or {};trace_rows=trace_rows if trace_rows is not None else []
    started=perf_counter();chosen=first
    if env.state.is_terminal:
        for h in HORIZONS:
            if str(h) not in checkpoints:checkpoints[str(h)]=metric(env,start,coins,acc,h,elapsed_before)
    while not reached(env.state,start,max_horizon):
        s=env.state;acts=env.legal_actions()
        if chosen is None:chosen=agent.choose(s,acts)
        if chosen not in acts:raise ValueError('Illegal rollout action')
        if acc['decisions']>0:acc['opportunities']+=int(Action(T.REROLL) in acts)
        acc['rerolls']+=int(chosen.action_type==T.REROLL)
        new,reward,_,truncated,info=env.step(chosen)
        acc['reward']+=reward;acc['income']+=info.get('spin_income',0);acc['decisions']+=1
        if trace_rows is not None and getattr(agent,'record_trace',False):
            trace_rows.append(dict(step=acc['decisions'],stage=s.rent_stage,candidates=list(s.candidates),
                action=normalized(chosen),coins=new.coins,tokens=new.reroll_tokens,reward=reward,
                deck_counts=dict(Counter(x.symbol_id for x in new.symbols)),terminal=new.is_terminal))
        if truncated:raise ValueError('Truncated long-horizon rollout')
        elapsed=elapsed_before+perf_counter()-started
        for h in HORIZONS:
            if str(h) not in checkpoints and reached(new,start,h):checkpoints[str(h)]=metric(env,start,coins,acc,h,elapsed)
        chosen=None
    return acc,checkpoints,trace_rows,elapsed_before+perf_counter()-started


def task(state_id,branch,trial,mode):
    directory=OUT/'continuations';path=directory/f'{state_id}-{branch}-{trial}.json';resume=path.with_suffix('.pkl')
    contract=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest()
    previous=load(path) if path.exists() else None
    if previous and previous['protocol_sha256']!=contract:raise ValueError('Cached protocol mismatch')
    if previous and (previous['complete'] or mode=='pilot'):return previous
    payload=parent(state_id);initial=payload['env'].state
    # Reuse the frozen teacher's existing valid cache; no policy/score change.
    # Cache lifetime affects runtime only, and cold/warm path identity is tested.
    if state_id not in WORKER_AGENTS:WORKER_AGENTS[state_id]=RentRerollAgent(payload['env'].catalog)
    agent=WORKER_AGENTS[state_id];agent.record_trace=trial==0
    if previous:
        saved=pickle.loads(resume.read_bytes());env=saved['env'];acc=saved['acc'];checkpoints=previous['checkpoints'];traces=previous['trace'];elapsed=previous['elapsed_seconds'];first=None
        # Income is observable and retained in the exact environment clone;
        # normalize pilot metric bookkeeping without replaying any random path.
        acc['income']=sum(env._recent[len(payload['env']._recent):])
        for checkpoint in checkpoints.values():checkpoint['spin_income']=acc['income']
    else:
        env=fork_env(payload['env'],state_id,branch,trial);acc=None;checkpoints=None;traces=[];elapsed=0
        first=Action(T.REROLL) if branch=='reroll' else action(payload['teacher']['current_best_action'])
    acc,checkpoints,traces,elapsed=walk(env,first,agent,1 if mode=='pilot' else 'end',acc,checkpoints,elapsed,initial,traces)
    complete=env.state.is_terminal
    if not complete:
        tmp=resume.with_suffix('.tmp');tmp.write_bytes(pickle.dumps(dict(env=env,acc=acc),protocol=pickle.HIGHEST_PROTOCOL));tmp.replace(resume)
    result=dict(state_id=state_id,branch=branch,continuation_id=trial,
        metric_version=2,
        seed_digest=digest(['v145-independent',state_id,branch,trial]),protocol_sha256=contract,
        complete=complete,checkpoints=checkpoints,elapsed_seconds=elapsed,trace=traces)
    dump(path,result);return result


def run_tasks(tasks):
    execution_path=OUT/'execution.json'
    workers=load(execution_path)['workers'] if execution_path.exists() else 3
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        fs=[pool.submit(task,*args) for args in tasks]
        for i,f in enumerate(as_completed(fs),1):
            f.result()
            if i%16==0 or i==len(fs):print(f'rollouts {i}/{len(fs)}',flush=True)


def experiment(mode):
    selected=load(OUT/'selected_states.json');ids=selected['pilot_state_ids'] if mode=='pilot' else selected['convergence_state_ids'] if mode=='convergence' else [r['state_id'] for r in selected['selected']]
    k=8 if mode=='pilot' else 64 if mode=='convergence' else 32
    if mode!='pilot':
        if not load(OUT/'pilot_gate.json')['passed']:raise ValueError('Pilot failed')
    if mode=='formal' and not (OUT/'convergence.json').exists():raise ValueError('Convergence audit required')
    run_tasks([(sid,branch,i,mode) for sid in ids for branch in ('current','reroll') for i in range(k)])
    if mode=='pilot':dump(OUT/'pilot_gate.json',dict(passed=True,states=len(ids),K=k,horizon=1,
       checks=['saved exact state/RNG/legal set','isolated branch seeds','rent boundary metrics','no truncation','resumable same random path']))
    elif mode=='convergence':convergence()


def normalize_pilot_income():
    """Fix diagnostic spin-income bookkeeping from saved clones, no resimulation."""
    count=0
    for path in (OUT/'continuations').glob('*.json'):
        r=load(path)
        if r.get('metric_version')==2:continue
        resume=path.with_suffix('.pkl')
        if not resume.exists():
            raise ValueError('Income normalization requires exact cached clone; do not fabricate missing field')
        saved=pickle.loads(resume.read_bytes());base=parent(r['state_id'])['env']
        income=sum(saved['env']._recent[len(base._recent):]);saved['acc']['income']=income
        for m in r['checkpoints'].values():m['spin_income']=income
        r['metric_version']=2;dump(path,r);resume.write_bytes(pickle.dumps(saved,protocol=pickle.HIGHEST_PROTOCOL));count+=1
    dump(OUT/'pilot_income_normalization.json',dict(corrected=count,source='exact cached env._recent suffix',replayed_paths=0))


def records(ids=None,k=None):
    rows=[]
    for path in (OUT/'continuations').glob('*.json'):
        r=load(path)
        if ids is not None and r['state_id'] not in ids:continue
        if k is not None and r['continuation_id']>=k:continue
        for m in r['checkpoints'].values():rows.append(dict(state_id=r['state_id'],branch=r['branch'],continuation_id=r['continuation_id'],complete=r['complete'],seed_digest=r['seed_digest'],**m))
    return rows


def aggregate(rows,ids,k):
    groups=defaultdict(list)
    for r in rows:
        if r['state_id'] in ids and r['continuation_id']<k:groups[(r['state_id'],str(r['horizon']),r['branch'])].append(r)
    results=[]
    for sid in ids:
        for h in HORIZONS:
            a,b=groups[(sid,str(h),'current')],groups[(sid,str(h),'reroll')]
            if len(a)!=k or len(b)!=k:raise ValueError(f'Incomplete {sid}/{h}: {len(a)}/{len(b)}')
            start=a[0]['stage_at_cut']-a[0]['stage_gain'] if 'stage_at_cut' in a[0] else 0
            span=13-start if h=='end' else min(int(h),13-start)
            scores={name:delta_stats(a,b,name,span if name=='stage_gain' else None) for name in ('stage_gain','reward_gain','net_coins_gained','rent_survival','future_reroll_opportunities','tokens_after')}
            results.append(dict(state_id=sid,horizon=h,K=k,**scores))
    return results


def delta_stats(a,b,key,bound=None):
    canonical={'stage_gain':'stage','reward_gain':'reward','rent_survival':'next_rent_survival'}.get(key,key)
    d=difference([{canonical:r[key]} for r in a],[{canonical:r[key]} for r in b],canonical)
    if d['se']>0:
        k=min(len(a),len(b));critical=2.365 if k<=8 else 2.131 if k<=16 else 2.04 if k<=32 else 2.0
        d['ci95']=[d['delta']-critical*d['se'],d['delta']+critical*d['se']]
        d['ci_method']=f'independent Welch conservative t approximation, critical={critical}, no multiplicity adjustment'
    elif bound is not None:
        radius=bound*(math.sqrt(math.log(80)/(2*len(a)))+math.sqrt(math.log(80)/(2*len(b))))
        d['ci95']=[max(-bound,d['delta']-radius),min(bound,d['delta']+radius)]
        d['ci_method']='bounded Hoeffding, actual remaining horizon; zero empirical variance'
    return d


def convergence():
    ids=load(OUT/'selected_states.json')['convergence_state_ids'];rows=records(ids,64);results=[]
    for k in (8,16,32,64):
        for r in aggregate(rows,ids,k):
            for target in ('stage_gain','reward_gain'):
                d=r[target];a=[x[target] for x in rows if x['state_id']==r['state_id'] and x['branch']=='current' and str(x['horizon'])==str(r['horizon']) and x['continuation_id']<k]
                b=[x[target] for x in rows if x['state_id']==r['state_id'] and x['branch']=='reroll' and str(x['horizon'])==str(r['horizon']) and x['continuation_id']<k]
                results.append(dict(state_id=r['state_id'],horizon=r['horizon'],K=k,target=target,
                    mean_current=mean(a),mean_reroll=mean(b),std_current=pstdev(a),std_reroll=pstdev(b),
                    current_cpu_seconds=sum(x['elapsed_seconds'] for x in rows if x['state_id']==r['state_id'] and x['branch']=='current' and str(x['horizon'])==str(r['horizon']) and x['continuation_id']<k),
                    reroll_cpu_seconds=sum(x['elapsed_seconds'] for x in rows if x['state_id']==r['state_id'] and x['branch']=='reroll' and str(x['horizon'])==str(r['horizon']) and x['continuation_id']<k),
                    **d,ci_width=d['ci95'][1]-d['ci95'][0] if d['ci95'] else None,sign=sign(d['delta'])))
    end={target:mean(next(x['sign'] for x in results if x['state_id']==sid and x['target']==target and x['K']==32 and x['horizon']=='end')==next(x['sign'] for x in results if x['state_id']==sid and x['target']==target and x['K']==64 and x['horizon']=='end') for sid in ids) for target in ('stage_gain','reward_gain')}
    dump(OUT/'convergence.json',dict(K32_vs64_end_sign_agreement=end,formal_K=32,
        stable_point_sign_gate=all(v>=.75 for v in end.values()),
        interpretation='Point sign stability only; finite nested pilot, no ground truth. FormalK stays frozen32, uncertainty reported.',results=results))
    write_csv(OUT/'convergence.csv',results)


def report():
    selected=load(OUT/'selected_states.json')['selected'];ids=[r['state_id'] for r in selected];index={r['state_id']:r for r in selected}
    rows=records(ids,32)
    if len(rows)!=40*2*32*4 or not all(r['complete'] for r in rows):raise ValueError('Formal dataset incomplete')
    summary=aggregate(rows,ids,32);lookup={(r['state_id'],str(r['horizon'])):r for r in summary}
    local_rel=[];horizon_rel=[];confusions=[];buckets=[]
    for h in HORIZONS:
        for target in ('stage_gain','reward_gain'):
            for axis in (0,1,2):
                subset=[r for r in selected if coordinate(r['reroll_advantage'])==axis]
                x=[r['reroll_advantage'][axis] for r in subset];y=[lookup[(r['state_id'],str(h))][target]['delta'] for r in subset]
                local_rel.append(dict(horizon=h,target=target,axis=axis,**relationships(x,y)))
            counts=Counter()
            for r in selected:
                d=lookup[(r['state_id'],str(h))][target];label=classify(1 if positive(r['reroll_advantage']) else -1,d['delta']);counts[label]+=1
                confusions.append(dict(state_id=r['state_id'],horizon=h,target=target,bucket=r['bucket'],
                    local_positive=positive(r['reroll_advantage']),longterm_delta=d['delta'],category=label,
                    ci95=d['ci95'],interval_excludes_zero=d['ci95'] is not None and (d['ci95'][0]>0 or d['ci95'][1]<0)))
            for name in sorted({r['bucket'] for r in selected}):
                ss=[r for r in selected if r['bucket']==name];vals=[lookup[(r['state_id'],str(h))][target]['delta'] for r in ss]
                buckets.append(dict(horizon=h,target=target,bucket=name,n=len(ss),mean_longterm_delta=mean(vals),
                    negative_proxy_count=sum(v<0 for v in vals),positive_proxy_count=sum(v>0 for v in vals)))
            if h!='end':
                short=[lookup[(sid,str(h))][target]['delta'] for sid in ids];end=[lookup[(sid,'end')][target]['delta'] for sid in ids]
                horizon_rel.append(dict(horizon=h,target=target,**relationships(short,end)))
    costs={str(h):dict(mean_continuation_seconds=mean(r['elapsed_seconds'] for r in rows if str(r['horizon'])==str(h)),
             K32_state_two_branch_seconds=64*mean(r['elapsed_seconds'] for r in rows if str(r['horizon'])==str(h))) for h in HORIZONS}
    replication=[]
    core=[r['state_id'] for r in selected if coordinate(r['reroll_advantage'])==1]
    first=aggregate([r for r in rows if r['continuation_id']<16],ids,16)
    second=aggregate([{**r,'continuation_id':r['continuation_id']-16} for r in rows if r['continuation_id']>=16],ids,16)
    maps=[{(r['state_id'],str(r['horizon'])):r for r in values} for values in (first,second)]
    for fold in (0,1):
        prediction,reference=maps[fold],maps[1-fold]
        for target in ('stage_gain','reward_gain'):
            y=[reference[(sid,'end')][target]['delta'] for sid in core]
            replication.append(dict(fold=fold,target=target,predictor='local_active_rent_axis',
                **relationships([index[sid]['reroll_advantage'][1] for sid in core],y)))
            for h in (1,2,3,'end'):
                x=[prediction[(sid,str(h))][target]['delta'] for sid in core]
                replication.append(dict(fold=fold,target=target,predictor=str(h),**relationships(x,y)))
    token_stats=[]
    for token in (1,2,3):
        subset=[r for r in selected if r['reroll_tokens_before']==token] if token<3 else [r for r in selected if r['reroll_tokens_before']>=3]
        token_stats.append(dict(tokens='3+' if token==3 else token,n=len(subset),
            stage_delta=mean(lookup[(r['state_id'],'end')]['stage_gain']['delta'] for r in subset) if subset else None,
            reward_delta=mean(lookup[(r['state_id'],'end')]['reward_gain']['delta'] for r in subset) if subset else None,
            future_opportunity_delta=mean(lookup[(r['state_id'],'end')]['future_reroll_opportunities']['delta'] for r in subset) if subset else None))
    cases=[]
    for r in selected:
        effect=lookup[(r['state_id'],'end')];d=effect['stage_gain']['delta'];local=positive(r['reroll_advantage'])
        if d==0:continue
        label=classify(1 if local else -1,d)
        cases.append(dict(state_id=r['state_id'],local_row=r,proxy=effect,
            classification=label,explanation='Unknown; Monte Carlo variance / continuation policy interaction are unresolved, not diagnosed causes',
            causal_error_proven=False,representative_trial=0))
    for label in ('positive','negative'):
        directory=OUT/f'{label}_cases';directory.mkdir(exist_ok=True)
        subset=sorted((c for c in cases if (c['proxy']['stage_gain']['delta']>0)==(label=='positive')),key=lambda c:-abs(c['proxy']['stage_gain']['delta']))[:10]
        for c in subset:
            sid=c['state_id'];c['continuation_traces']={b:load(OUT/'continuations'/f'{sid}-{b}-0.json')['trace'] for b in ('current','reroll')}
            dump(directory/f'{sid}.json',c)
    interpretation_path=OUT/'interpretation.json'
    interpretation=load(interpretation_path) if interpretation_path.exists() else {}
    decision=interpretation.get('decision','UNRESOLVED: assess independent-half replication and cost before choosing V146')
    tests_text=(OUT/'tests.txt').read_text(encoding='utf-8-sig',errors='replace')
    test_match=re.search(r'Ran (\d+) tests',tests_text)
    test_result=dict(count=int(test_match.group(1)) if test_match else None,
                    passed=bool(test_match and re.search(r'\nOK\s*$',tests_text)))
    if not test_result['passed']:raise ValueError('Full tests missing/failed')
    result=dict(version='V145 Limited Rollout Long-Horizon Validation',training_updates=0,
        tests=test_result,interpretation=interpretation,
        frozen_files_verified=frozen_check(),states=40,K=32,formal_paths=2560,
        continuation='frozen forecast_rents_v143',local_relationships=local_rel,horizon_relationships=horizon_rel,
        sign_confusion=confusions,buckets=buckets,summary=summary,cost=costs,
        convergence=load(OUT/'convergence.json'),token_stats=token_stats,cases=cases,
        independent_half_replication=replication,
        decision=decision,limitations=['Rollout-based Long-Horizon Proxy, not True Q. Conditional fixed policy and approximate restricted environment.',
          '40 frozen stratified development states; rare axes n2, no scalar mixing or population policy performance estimate.',
          'Nested continuations/horizons are correlated; stage/reward differences have separate units. No MAE across unlike units.',
          'Independent branch RNG with paired trial labels only; no semantic CRN.',
          'Zero point effects reported separately. Uncorrected per-state intervals cannot certify multiple causal errors.',
          'Token comparison changes both offer and inventory, so not an isolated scarcity-cost measurement; V144 pure inventory probes remain frozen.',
          'A shorter horizon agreeing with noisy end estimates is not proof of superiority over local scoring.'])
    write_csv(OUT/'rollout_results.csv',rows);write_csv(OUT/'horizon_comparison.csv',horizon_rel);write_csv(OUT/'sign_confusion.csv',confusions)
    write_csv(OUT/'independent_half_replication.csv',replication)
    dump(ROOT/'reports/v145_limited_rollout_validation.json',result)
    write_report(result)
    print(json.dumps(dict(states=40,K=32,paths=2560,decision=decision)),flush=True)


def write_report(r):
    parts=[]
    def add(name,body):parts.append(f'## 【{name}】\n\n{body}\n')
    def block(x):return json.dumps(x,ensure_ascii=False,indent=2)
    def fmt(x):return 'N/A' if x is None else f'{x:.3f}' if isinstance(x,float) else str(x)
    def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']+['| '+' | '.join(fmt(x) for x in row)+' |' for row in rows])
    add('当前版本',r['version']);add('本轮目标','Training Updates=0；验证有限续局是否值得继续投入，不改在线Teacher或局部公式。')
    add('冻结资产',f"{r['frozen_files_verified']}历史文件hash未变；V128/V130/Legacy/V143/V141–V144全冻结。")
    add('新增工具','tools/validate_long_horizon.py：独立clone/RNG、单租金pilot、checkpoint续跑、嵌套K收敛、1/2/3租金与终局比较；仅显式命令运行，无在线调用。')
    add('测试结果',f"完整{r['tests']['count']}项通过，0 Failed；12项V145新增检查覆盖clone/RNG/seed复现、租金/终局/奖励口径、无重放续跑、聚合/CI/sign、缓存冷热轨迹一致、跨进程复现及历史hash。详见logs/v145-rollout/tests.txt。")
    add('State Sampling','全部1369机会中预冻结40状态：六个主要租金优势分桶各6个、概率/现金稀有分量各2个；包含选择与拒绝，优先不同episode，不按续局结果选状态。pilot12状态先只走1租金，4状态K8/16/32/64收敛，formalK32复用pilot/full cache。')
    add('Continuation Convergence',block({k:v for k,v in r['convergence'].items() if k!='results'})+'\n\n逐状态meanQ/std/SE/CIwidth/sign见convergence.csv。K32预算固定，稳定性不成立时不自动上最大K来追显著。')
    add('Local vs Long-Term',table(['Horizon','Target','n','Pearson','Spearman','Sign agree','Nonzero agree'],
        [[x['horizon'],x['target'],x['n'],x['pearson'],x['spearman'],x['sign_agreement'],x['decisive_sign_agreement']] for x in r['local_relationships'] if x['axis']==1])+'\n\n上表为active rent轴36状态；概率/现金稀有分量各n2，相关N/A，详细记录在JSON。按axis分开，不混概率/租金/现金，不报告跨单位MAE。Pearson/Spearman与符号关系均为描述性。')
    add('Horizon Comparison',table(['H vs End','Target','n','Pearson','Spearman','Sign agree','Nonzero agree'],
        [[x['horizon'],x['target'],x['n'],x['pearson'],x['spearman'],x['sign_agreement'],x['decisive_sign_agreement']] for x in r['horizon_relationships']])+'\n\n三个短horizon与end使用同一条轨迹checkpoint，不能当独立验证；terminal早于目标时吸收终局值。终局是固定V143续局代理，不是ground truth。')
    add('Independent Continuation Replication',table(['Fold','Target','Predictor','n','Pearson','Spearman','Sign agree'],
        [[x['fold'],x['target'],x['predictor'],x['n'],x['pearson'],x['spearman'],x['sign_agreement']] for x in r['independent_half_replication']])+'\n\n补充预先冻结的分半分析：0–15预测、16–31终局参考，再交换；同路径相关不是验证。只用active rent轴36状态，不混局部评分单位。分半各16条/branch的终局也含噪声，不是真值。')
    add('Sign Confusion',block({f'{h}:{t}':dict(Counter(x['category'] for x in r['sign_confusion'] if str(x['horizon'])==str(h) and x['target']==t)) for h in HORIZONS for t in ('stage_gain','reward_gain')})+'\n\nZERO单列；false-positive proxy不等于已证明危险动作。逐状态CI及是否排除0见sign_confusion.csv。')
    for name,label in [('Strong Positive Cases','strong_positive'),('False Positive Cases','FALSE POSITIVE PROXY'),('False Negative Cases','FALSE NEGATIVE PROXY')]:
        ss=[c for c in r['cases'] if ('strong_positive' in c['local_row']['bucket'] if label=='strong_positive' else c['classification']==label)]
        add(name,block([dict(state_id=c['state_id'],stage_delta=c['proxy']['stage_gain']['delta'],ci95=c['proxy']['stage_gain']['ci95'],reason=c['explanation']) for c in ss])+'\n\nUnknown允许保留；没有从结果反推deck pollution、synergy loss或token错误。')
    add('Token Opportunity Cost',block(r['token_stats'])+'\n\n相同pre-action state下使用vs保留token，但同时改变候选，不能把整个行动收益归因于纯成本；不同token数量的状态还存在context混杂。3+无机会则N/A，禁止手调cost。')
    add('Compute Cost',table(['Horizon','Mean seconds/path','K32 two-branch seconds/state'],[[h,x['mean_continuation_seconds'],x['K32_state_two_branch_seconds']] for h,x in r['cost'].items()])+'\n\nseconds为每路径累积实测，K32成本是64条路径计时总量均值，不是并行wall；pilot续跑不重复已完成前缀。K成本详见convergence和正式记录。执行由3调至6worker，仅复用已提交原子cache，种子/样本/政策未变；温缓存与冷缓存动作/RNG相同已测。计时不含clone加载和cache I/O，不把混合worker/cache计时当严格加速实验。')
    add('Evidence Strength','本轮是版本化、可关闭、可复现的代理值验证，无训练/数据集生成/政策优化/在线扩局。有限样本和终局CI必须保留；短horizon与end一致也可能来自共同方差和通关上限。')
    add('结论','以完成数据解释强度；若没有可重复的更强长期信号，按硬停止条件冻结Reroll支线。')
    add('V146 决策',r['decision']+'。BC训练符号fit≈72.9%是明确且独立的已知瓶颈，本轮未处理。')
    if r['interpretation']:add('十项问题与研究停止条件',block(r['interpretation']))
    (ROOT/'reports/v145_limited_rollout_validation.md').write_text('\n'.join(parts),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['setup','pilot','convergence','formal','report','verify']);a=p.parse_args()
    if a.mode=='setup':setup()
    elif a.mode=='report':report()
    elif a.mode=='verify':print(frozen_check())
    else:experiment(a.mode)
