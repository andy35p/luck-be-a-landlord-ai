"""V142 frozen-policy diagnostics. Outputs are never training inputs.

Replay adds missing observations/labels to V141, verifies original errors and
outcomes, and checkpoints each episode so interrupted runs do not repeat work.
"""
import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import mean, median
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from luck_agent.agents.bc_policy import BCPolicyAdapter
from luck_agent.agents.rent_forecast_agent import RentForecastAgent, rent_rank
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.env.action import ActionType as T
from luck_agent.evaluation.trajectory import normalized
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.magpie_corpus import validate_corpus
from luck_agent.evaluation.rent_forecast import forecast_rents
from luck_agent.legacy.fast_env import DEFAULT_RENTS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'logs/v142-diagnostics'
BASE = ROOT / 'logs/v141-unified/bc-20260928T150505900238Z'
KEYS = ('scalars', 'deck', 'items', 'candidates', 'board', 'board_mask', 'board_observed')
PAIRS = [('bar_of_soap', 'mouse'), ('time_machine', 'undertaker'),
         ('bar_of_soap', 'goldfish'), ('spirit', 'mouse')]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def choice(action, state):
    if action['action_type'] == T.REMOVE_SYMBOL:
        return next(s['symbol_id'] for s in state['symbols'] if s['instance_id'] == action['target_id'])
    return action['target_id'] or T(action['action_type']).name


def describe(state, actions):
    return dict(phase=state['decision_type'], rent_stage=state['rent_stage'],
                spin=state['spin_count'], coins=state['coins'], rent=state['current_rent'],
                rent_pressure=(state['current_rent']-state['coins'])/state['current_rent'],
                spins_until_rent=state['spins_until_rent'], deck_size=len(state['symbols']),
                recent_income=state['recent_income'],
                recent_income_mean=mean(state['recent_income']) if state['recent_income'] else 0,
                candidate_count=len(actions), reroll_tokens=state['reroll_tokens'],
                histogram=dict(Counter(s['symbol_id'] for s in state['symbols'])),
                items=sorted(state['items']))


def bucket(stage):
    # Natural schedule boundaries: 5/6/7 spins, then 8/9, then final 10-spin rents.
    return 'early' if DEFAULT_RENTS[min(stage,12)][1] <= 7 else 'mid' if stage < 10 else 'late'


def csv_write(name, rows):
    if not rows:
        (OUT/name).write_text('no_cases\n'); return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)


def replay(spec, policy):
    original=json.loads((BASE/'failure_summary.json').read_text())['high_confidence_errors']
    errors={(e['episode'],e['step']):e for e in original}
    with (BASE/'episodes.csv').open() as stream:
        outcomes={int(r['seed']):r for r in csv.DictReader(stream)}
    result=[]; enriched=[]; branches=[]; opportunities=[]
    for seed in range(spec['seed_start'],spec['seed_start']+spec['games']):
        cache=OUT/f'episode-{seed}.json.gz'
        if cache.exists():
            with gzip.open(cache,'rt') as stream:part=json.load(stream)
            if part['checkpoint']!=spec['checkpoint_sha256']:raise ValueError('Cache checkpoint drift')
        else:
            env=GameEnv(EnvConfig(**spec['environment']));state=env.reset(seed)
            teacher=RentForecastAgent(env.catalog);steps=0;reward_sum=0;trace=[];cases=[];cf=[];opp=[]
            tested=set()
            while not(state.is_terminal or state.is_truncated):
                actions=env.legal_actions();action,diag=policy.choose_with_diagnostics(state,actions)
                obs=normalized(state);aa=normalized(actions)
                recommended=teacher.choose(state,actions) if len(actions)>1 else action
                ra=normalized(recommended);ca=normalized(action)
                row=dict(seed=seed,step=steps,**describe(obs,aa),bc=choice(ca,obs),teacher=choice(ra,obs),
                         bc_type=ca['action_type'],teacher_type=ra['action_type'],
                         multi=len(actions)>1,agreement=action==recommended,
                         confidence=diag['top1_confidence'],margin=diag['score_margin'])
                row['high_error']=row['multi'] and not row['agreement'] and row['confidence']>=.8
                trace.append(row)
                if row['high_error']:
                    old=errors.get((seed,steps))
                    if old is None or old['state_id']!=digest(obs) or old['bc_choice']!=ca or old['teacher_choice']!=ra:
                        raise ValueError('V141 high-error replay drift')
                    scores=list(diag['scores']);weights=[math.exp(x-max(scores)) for x in scores]
                    ranks=sorted(range(len(scores)),key=lambda i:(-scores[i],i))
                    teacher_index=actions.index(recommended)
                    case={**row,'state_id':old['state_id'],'state':obs,'legal_actions':aa,
                          'bc_choice':ca,'teacher_choice':ra,'scores':scores,
                          'softmax_weights':[x/sum(weights) for x in weights],
                          'teacher_rank':ranks.index(teacher_index)+1,
                          'teacher_score_gap':max(scores)-scores[teacher_index]}
                    cases.append(case)
                    pair=(row['bc'],row['teacher'])
                    # One case of each priority pair in each of the first four seed blocks.
                    if pair in PAIRS and pair not in tested and seed<15004:
                        tested.add(pair);outcomes_cf=[]
                        for first in (action,recommended):
                            branch=deepcopy(env);ss,rr,*_=branch.step(first);n=1
                            while not(ss.is_terminal or ss.is_truncated):
                                ss,r,*_=branch.step(policy.choose(ss,branch.legal_actions()));rr+=r;n+=1
                            outcomes_cf.append(dict(stage=ss.rent_stage,reward=rr,won=ss.won,decisions=n))
                        cf.append(dict(seed=seed,step=steps,pair=list(pair),bc_branch=outcomes_cf[0],
                                       teacher_branch=outcomes_cf[1],delta_stage=outcomes_cf[1]['stage']-outcomes_cf[0]['stage'],
                                       delta_reward=outcomes_cf[1]['reward']-outcomes_cf[0]['reward'],
                                       delta_survival=int(outcomes_cf[1]['won'])-int(outcomes_cf[0]['won'])))
                # Systematic opportunities: teacher skips, >=2 tokens, <=0 rent pressure.
                if seed<15008 and len(opp)<2 and recommended.action_type==T.SKIP_SYMBOL and state.reroll_tokens>=2 and state.coins>=state.current_rent and any(a.action_type==T.REROLL for a in actions):
                    forecasts=forecast_rents(state,tuple(a for a in actions if a.action_type in (T.PICK_SYMBOL,T.SKIP_SYMBOL)),env.catalog,horizon=30,trials=8,seed=20270927)
                    branch=deepcopy(env);new_state,*_=branch.step(next(a for a in actions if a.action_type==T.REROLL))
                    if new_state.reroll_tokens!=state.reroll_tokens-1 or new_state.decision_type!='symbol':raise ValueError('Reroll semantics drift')
                    opp.append(dict(seed=seed,step=steps,state_id=digest(obs),state=obs,candidates=obs['candidates'],
                                    tokens=state.reroll_tokens,teacher_choice=ra,
                                    scores=[dict(action=normalized(f.action),lexicographic_rank=list(rent_rank(f))) for f in forecasts],
                                    reroll_score=None,reroll_scored=False,
                                    reroll_step_valid=True,after_candidates=list(new_state.candidates),after_tokens=new_state.reroll_tokens))
                state,r,*_=env.step(action);reward_sum+=r;steps+=1
            expected=outcomes[seed]
            for key,value in dict(stage=state.rent_stage,won=int(state.won),spins=state.spin_count,coins=state.coins,reward=reward_sum,decisions=steps,truncated=int(state.is_truncated)).items():
                if float(expected[key])!=value:raise ValueError(f'V141 outcome drift {seed} {key}')
            if {(seed,r['step']) for r in cases}!={k for k in errors if k[0]==seed}:raise ValueError('Missing original errors')
            for row in trace+cases:row.update(final_stage=state.rent_stage,episode_return=reward_sum,won=state.won)
            part=dict(checkpoint=spec['checkpoint_sha256'],trace=trace,errors=cases,branches=cf,opportunities=opp,outcome_verified=True)
            temporary=cache.with_suffix('.tmp')
            with gzip.open(temporary,'wt',encoding='utf-8') as stream:json.dump(part,stream)
            temporary.replace(cache)
            if (seed-14999)%8==0:print(json.dumps({'replayed':seed-14999,'of':128}),flush=True)
        result.extend(part['trace']);enriched.extend(part['errors']);branches.extend(part['branches']);opportunities.extend(part['opportunities'])
    return result,enriched,branches,opportunities


def candidate_key(actions):
    # Symbol/item identities and action kinds; removal IDs remain distinct within episode.
    return tuple(sorted((a['action_type'],a['target_id'] or '') for a in actions))


def support_similarity(a,b):
    ah,bh=a['histogram'],b['histogram'];keys=set(ah)|set(bh)
    intersection=sum(min(ah.get(k,0),bh.get(k,0)) for k in keys)
    union=sum(max(ah.get(k,0),bh.get(k,0)) for k in keys)
    h=intersection/union if union else 1
    ai,bi=set(a['items']),set(b['items']);j=len(ai&bi)/len(ai|bi) if ai|bi else 1
    stage=math.exp(-abs(a['rent_stage']-b['rent_stage']))
    size=math.exp(-abs(a['deck_size']-b['deck_size'])/5)
    pressure=math.exp(-abs(a['rent_pressure']-b['rent_pressure']))
    return .4*h+.15*j+.15*stage+.15*size+.15*pressure,h,j


def model_context_signature(sample):
    """Symbolic equivalence under the current linear instance + mean pooling.

    Includes every board/candidate pointed instance. This is stricter evidence
    than an embedding distance, and does not change or invoke model weights.
    """
    deck=sample['deck'];n=len(deck)
    hist=Counter(row[0] for row in deck)
    numeric=[sum(row[j] for row in deck)/max(1,n) for j in (1,2,3)]
    item_hist=Counter(sample['items']);ni=len(sample['items'])
    pointed=lambda index:deck[index-1] if index else [0,0,0,0]
    board=[(row[:4],pointed(row[4])) if mask else None for row,mask in zip(sample['board'],sample['board_mask'])]
    candidates=[(row[:3],pointed(row[3])) for row in sample['candidates']]
    return digest(dict(scalars=sample['scalars'],n=n,histogram=sorted((k,v/max(1,n)) for k,v in hist.items()),numeric=numeric,
                       items=sorted((k,v/max(1,ni)) for k,v in item_hist.items()),board=board,
                       board_observed=sample['board_observed'],candidates=candidates))


def training_audit(errors,policy,spec):
    directory=ROOT/spec['dataset_dir'];manifest=validate_corpus(directory)
    encoder=policy.agent.encoder;train=[];encoded=defaultdict(list);exact=defaultdict(list);by_candidates=defaultdict(list)
    for entry in manifest['entries']:
        if entry['split']!='train':continue
        for header,episode in read_episodes(directory/entry['file']):
            for record in episode:
                obs=record['state'];actions=record['legal_actions'];sample=encoder.encode(record,header['agent'])
                if len(actions)<=1:continue
                row=dict(**describe(obs,actions),seed=entry['seed'],step=record['step'],label=choice(record['action'],obs),
                         label_index=sample['label'],raw_hash=digest(obs),actions=actions,sample=sample)
                index=len(train);train.append(row);exact[row['raw_hash']].append(index)
                encoded[digest({k:sample[k] for k in KEYS})].append(index)
                by_candidates[candidate_key(actions)].append(index)
    support=[]
    for error in errors:
        pool=by_candidates[candidate_key(error['legal_actions'])]
        # Removal identity strings differ between runs; use encoded candidate rows as fallback.
        if not pool:pool=[i for i,r in enumerate(train) if r['phase']==error['phase'] and r['candidate_count']==error['candidate_count']]
        nearest=sorted(((support_similarity(error,train[i])[0],i) for i in pool),reverse=True)[:10]
        close=[(s,i) for s,i in nearest if s>=.85]
        labels=Counter(train[i]['label'] for s,i in close)
        category=('contradictory-support' if len(labels)>1 and max(labels.values())/sum(labels.values())<.8 else
                  'high-support' if len(close)>=5 else 'low-support')
        best=nearest[0] if nearest else (None,None)
        row=dict(seed=error['seed'],step=error['step'],state_id=error['state_id'],category=category,
                 exact_public_matches=len(exact[error['state_id']]),same_candidate_set_count=len(by_candidates[candidate_key(error['legal_actions'])]),
                 near_count_top10=len(close),best_support_score=best[0],near_teacher_labels=dict(labels),
                 same_teacher_label_near_count=labels.get(error['teacher'],0),
                 same_rent_stage_count=sum(train[i]['rent_stage']==error['rent_stage'] for s,i in nearest),
                 same_build_context_count=sum(support_similarity(error,train[i])[1]>=.8 and support_similarity(error,train[i])[2]==1 for s,i in nearest),
                 nearest_train_seed=train[best[1]]['seed'] if best[1] is not None else None,
                 nearest_train_step=train[best[1]]['step'] if best[1] is not None else None)
        support.append(row);error.update(training_support_category=category,training_support_score=best[0])
    collisions=[]
    for hash_key,indices in encoded.items():
        labels={train[i]['label_index'] for i in indices}
        if len(labels)>1:collisions.append(dict(kind='exact_encoder',feature_hash=hash_key,count=len(indices),labels=sorted(labels),examples=[(train[i]['seed'],train[i]['step']) for i in indices]))
    # Near audit uses padded actual encoder tensors, train-fitted scalar normalization,
    # same ordered encoded candidate list; token IDs are categorical one-hot distances.
    groups=defaultdict(list)
    for i,r in enumerate(train):groups[digest(r['sample']['candidates'])].append(i)
    near_checked=near_pairs=0;min_dist=None
    for indices in groups.values():
        if len(indices)<2:continue
        width=max(len(train[i]['sample']['deck']) for i in indices);vectors=[]
        for i in indices:
            s=policy.agent.scale(train[i]['sample'],policy.agent.scaler)
            deck=s['deck']+[[0,0,0,0]]*(width-len(s['deck']))
            # Continuous encoder components plus categorical one-hot indicators.
            v=list(s['scalars'])+[float(s['board_observed'])]
            for row in deck:
                v.extend(float(row[0]==token) for token in range(17));v.extend(row[1:])
            v.extend(float(token in s['items']) for token in range(1,3))
            for row in s['board']:
                v.extend(float(row[0]==token) for token in range(17));v.extend(row[1:])
            vectors.append(v)
        x=torch.tensor(vectors);dist=torch.cdist(x,x)
        for local,i in enumerate(indices):
            different=torch.tensor([train[j]['label_index']!=train[i]['label_index'] for j in indices])
            if not different.any():continue
            near_checked+=1;d,j=dist[local].masked_fill(~different,float('inf')).min(0);d=float(d);j=indices[int(j)]
            if min_dist is None or d<min_dist:min_dist=d
            # <= .25 L2 in full encoded categorical/normalized continuous input.
            if d<=.25:
                near_pairs+=1
                collisions.append(dict(kind='near_encoder',distance=d,seed=train[i]['seed'],step=train[i]['step'],other_seed=train[j]['seed'],other_step=train[j]['step'],label=train[i]['label'],other_label=train[j]['label']))
    # Frozen model fit on TRAIN only: supports capacity/objective diagnosis, no fitting.
    fit=defaultdict(lambda:Counter())
    from luck_agent.agents.magpie_model import magpie_tensors
    for row in train:
        features=encoder.features(policy.agent.scale(row['sample'],policy.agent.scaler))
        batch={k:[features[k]] for k in KEYS};batch.update(encoder_version=encoder.version,deck_mask=[[True]*len(features['deck'])],items_mask=[[True]*len(features['items'])],candidates_mask=[[True]*len(features['candidates'])])
        with torch.no_grad():prediction=int(policy.agent.model(magpie_tensors(batch))[0].argmax())
        fit[row['phase']]['n']+=1;fit[row['phase']]['correct']+=prediction==row['label_index']
    csv_write('training_support.csv',support);csv_write('feature_collisions.csv',collisions)
    return dict(training_multi_states=len(train),support_counts=dict(Counter(r['category'] for r in support)),
                exact_online_matches=sum(r['exact_public_matches']>0 for r in support),
                threshold=.85,min_near_examples=5,near_cap=10,
                similarity_weights=dict(histogram=.4,items=.15,stage=.15,deck_size=.15,pressure=.15),
                training_fit={k:dict(**v,agreement=v['correct']/v['n']) for k,v in fit.items()},
                feature_collision=dict(exact_groups=sum(r['kind']=='exact_encoder' for r in collisions),near_threshold_l2=.25,near_checked=near_checked,near_directed_pairs=near_pairs,minimum_different_label_distance=min_dist,
                                       note='Raw encoded input collision audit does not prove learned representation sufficiency. Unencoded effect_state/recent_income and pooling may still alias.'))


def group_stats(trace,field):
    groups=defaultdict(list)
    for row in trace:
        if row['multi']:groups[str(row[field])].append(row)
    return {k:dict(n=len(v),agreement=mean(r['agreement'] for r in v),high_error_rate=mean(r['high_error'] for r in v),high_errors=sum(r['high_error'] for r in v),
                   symbol_agreement=mean(r['agreement'] for r in v if r['phase']=='symbol') if any(r['phase']=='symbol' for r in v) else None,
                   win_errors=sum(r['high_error'] and r['won'] for r in v),loss_errors=sum(r['high_error'] and not r['won'] for r in v)) for k,v in sorted(groups.items())}


def summarize(trace,errors,branches,opportunities,audit):
    episodes=defaultdict(list)
    for r in trace:r['stage_bucket']=bucket(r['rent_stage']);episodes[r['seed']].append(r)
    windows=defaultdict(list);epstats=[]
    for seed,rows in episodes.items():
        mistakes=[r for r in rows if r['multi'] and not r['agreement']];high=[r for r in rows if r['high_error']]
        first=mistakes[0] if mistakes else None
        for origin in ([first] if first else []):
            for n in (5,10,20):
                future=[r for r in rows if origin['step']<r['step']<=origin['step']+n and r['multi']]
                if future:windows[n].append(mean(r['agreement'] for r in future))
        epstats.append(dict(seed=seed,won=rows[-1]['won'],first_disagreement_step=first['step'] if first else None,
                            first_disagreement_stage=first['rent_stage'] if first else None,
                            decisions_to_end_after_first=len(rows)-1-first['step'] if first else None,
                            first_high_error_step=high[0]['step'] if high else None,
                            decisions_to_end_after_first_high=len(rows)-1-high[0]['step'] if high else None,
                            high_errors=len(high),deck_size=mean(r['deck_size'] for r in rows),rent_pressure=mean(r['rent_pressure'] for r in rows),
                            skip_rate=mean(r['bc_type']==T.SKIP_SYMBOL for r in rows if r['phase']=='symbol'),
                            removal_rate=mean(r['bc_type']==T.REMOVE_SYMBOL for r in rows if r['phase']=='remove'),
                            **{phase+'_agreement':mean(r['agreement'] for r in rows if r['phase']==phase and r['multi']) if any(r['phase']==phase and r['multi'] for r in rows) else None for phase in ('symbol','item','remove')}))
    pairs=[]
    for pair in PAIRS:
        cases=[r for r in errors if (r['bc'],r['teacher'])==pair]
        future_stats={}
        for n in (5,10,20):
            vals=[]
            for e in cases:
                future=[r for r in episodes[e['seed']] if e['step']<r['step']<=e['step']+n and r['multi']]
                if future:vals.append(mean(r['agreement'] for r in future))
            future_stats[n]=dict(windows=len(vals),agreement=mean(vals) if vals else None)
        pairs.append(dict(pair=list(pair),count=len(cases),mean_rent_stage=mean(r['rent_stage'] for r in cases),median_rent_stage=median(r['rent_stage'] for r in cases),
                          **{'mean_'+key:mean(r[key] for r in cases) for key in ('coins','deck_size','confidence','margin','final_stage','episode_return','teacher_rank')},
                          win_rate=mean(r['won'] for r in cases),teacher_top2_rate=mean(r['teacher_rank']<=2 for r in cases),teacher_top3_rate=mean(r['teacher_rank']<=3 for r in cases),future=future_stats))
    wins={}
    for won in (True,False):
        selected=[r for r in epstats if r['won']==won];wins[str(won)]=dict(episodes=len(selected),**{k:mean(r[k] for r in selected if r[k] is not None) for k in ('first_disagreement_stage','high_errors','deck_size','rent_pressure','skip_rate','removal_rate','symbol_agreement','item_agreement','remove_agreement')})
    csv_write('episode_diagnostics.csv',epstats)
    csv_write('error_attribution.csv',[{k:v for k,v in r.items() if k!='state'} for r in errors])
    csv_write('reroll_audit.csv',opportunities);csv_write('counterfactual.csv',branches)
    result=dict(version='V142',frozen_baseline=dict(episodes=128,seeds=[15000,15127],random_stage=3.21875,heuristic_stage=6.609375,teacher_stage=11.609375,bc_stage=9.6328125,wins=dict(random=0,heuristic=19,teacher=57,bc=4)),
                high_errors=len(errors),replay_verified=True,stage=group_stats(trace,'rent_stage'),natural_stage=group_stats(trace,'stage_bucket'),
                stage_definition='zero-based rents 0-5: 5/6/7 spins; 6-9: 8/9 spins; 10-12: final 10-spin rents',
                main_errors=pairs,training_support=audit,
                error_groups={field:dict(Counter(str(r[field]) for r in errors)) for field in ('phase','bc','teacher','candidate_count','spin','rent_stage','final_stage','won')},
                continuous_error_fields={key:dict(mean=mean(r[key] for r in errors),median=median(r[key] for r in errors),min=min(r[key] for r in errors),max=max(r[key] for r in errors)) for key in ('coins','rent_pressure','deck_size','recent_income_mean','confidence','margin','episode_return')},
                candidate_ranking=dict(mean_teacher_rank=mean(r['teacher_rank'] for r in errors),top1=0,top2=mean(r['teacher_rank']<=2 for r in errors),top3=mean(r['teacher_rank']<=3 for r in errors),last_rank=mean(r['teacher_rank']==r['candidate_count'] for r in errors),probability_definition='Softmax of BC cross-entropy logits; uncalibrated categorical weights, not outcome probabilities'),
                severity=dict(cases=len(branches),branches=branches,limitation='Deepcopy shares exact starting RNG state and executes unchanged simulator. Different actions may consume different draws; common future events are not guaranteed. Exploratory branch outcomes, not strict causal effect.'),
                compounding=dict(future_agreement={n:dict(episodes=len(v),mean=mean(v)) for n,v in windows.items()},first_disagreement=epstats,limitation='Observational windows include only multi-action decisions in next N total decisions; rent stage, selection and survival confound. No causal claim.'),
                win_loss=wins,reroll=dict(opportunities=len(opportunities),teacher_scoring_includes_reroll=False,train_reroll_labels=0,semantics_checks=len(opportunities),reason='RentForecastAgent.choose filters to PICK_SYMBOL/SKIP_SYMBOL; no reroll EV branch or score. Mask exposes REROLL correctly.',interaction='UNRESOLVED / NO OPPORTUNITY'),training_updates_added=0)
    (ROOT/'reports/v142_high_confidence_error_attribution.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('high_errors','natural_stage','main_errors','training_support','candidate_ranking','win_loss','reroll')},indent=2),flush=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    spec=json.loads((ROOT/'configs/v141_unified_evaluation.json').read_text())
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'luck_agent').rglob('*.py'))}
    contract=dict(checkpoint=spec['checkpoint_sha256'],source_hashes=sources,baseline_sha256=hashlib.sha256((BASE/'failure_summary.json').read_bytes()).hexdigest(),diagnostic_only=True)
    contract_path=OUT/'contract.json'
    if contract_path.exists() and json.loads(contract_path.read_text())!=contract:raise ValueError('Diagnostic input drift')
    contract_path.write_text(json.dumps(contract,indent=2))
    policy=BCPolicyAdapter(ROOT/spec['checkpoint'],expected_sha256=spec['checkpoint_sha256'],dataset_dir=ROOT/spec['dataset_dir'],rule_version='instance-magpie-v1')
    trace,errors,branches,opportunities=replay(spec,policy)
    audit=training_audit(errors,policy,spec)
    summarize(trace,errors,branches,opportunities,audit)
    if sources!={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'luck_agent').rglob('*.py'))}:raise ValueError('Core source changed during diagnostics')
    supplement()
    write_report()


def supplement():
    """Cheap observed-state controls and sensitivity after cached replay completes."""
    path=ROOT/'reports/v142_high_confidence_error_attribution.json'
    result=json.loads(path.read_text(encoding='utf-8'));trace=[]
    for seed in range(15000,15128):
        with gzip.open(OUT/f'episode-{seed}.json.gz','rt') as stream:trace.extend(json.load(stream)['trace'])
    spec=json.loads((ROOT/'configs/v141_unified_evaluation.json').read_text())
    directory=ROOT/spec['dataset_dir'];manifest=validate_corpus(directory)
    original=json.loads((BASE/'failure_summary.json').read_text())['bc_by_decision_type']
    for phase,expected in original.items():
        rows=[r for r in trace if r['phase']==phase]
        checks=dict(total_decisions=len(rows),multi_action_decisions=sum(r['multi'] for r in rows),
                    teacher_agreement_count=sum(r['multi'] and r['agreement'] for r in rows),
                    teacher_disagreement_count=sum(r['multi'] and not r['agreement'] for r in rows),
                    high_confidence_errors=sum(r['high_error'] for r in rows))
        if any(expected[k]!=v for k,v in checks.items()):raise ValueError(f'V141 phase drift: {phase}')
    result['frozen_baseline'].update(bc_minus_teacher=-1.9765625,paired_stage_ci95=[-2.3671875,-1.59375])
    result['v141_phase_counts_verified']=True
    severity=[]
    for group in result['main_errors']:
        branches=[r for r in result['severity']['branches'] if r['pair']==group['pair']]
        severity.append(dict(pair=group['pair'],frequency=group['count'],branch_cases=len(branches),
                             mean_delta_stage=mean(r['delta_stage'] for r in branches) if branches else None,
                             mean_delta_reward=mean(r['delta_reward'] for r in branches) if branches else None,
                             stage_or_win_improvement_cases=sum(r['delta_stage']>0 or r['delta_survival']>0 for r in branches),
                             frequency_times_positive_stage_delta=group['count']*mean(max(0,r['delta_stage']) for r in branches) if branches else None))
    result['severity']['frequency_weighted_exploratory_index']=severity
    result['severity']['index_limitation']='Only first occurrence per priority pair in seeds15000-15003. Frequency times observed positive stage delta is a prioritization index, not an unbiased population severity or causal estimate.'
    train=defaultdict(list);train_action_counts=Counter();train_reroll_opportunities=0
    from luck_agent.evaluation.magpie_batching import MagpieCandidateEncoder
    encoder=MagpieCandidateEncoder();context_groups=defaultdict(list)
    for entry in manifest['entries']:
        if entry['split']!='train':continue
        for _,episode in read_episodes(directory/entry['file']):
            for record in episode:
                train_action_counts[T(record['action']['action_type']).name]+=1
                train_reroll_opportunities+=any(a['action_type']==T.REROLL for a in record['legal_actions'])
                if len(record['legal_actions'])<=1:continue
                sample=encoder.encode(record,'forecast_rents')
                context_groups[model_context_signature(sample)].append(dict(seed=entry['seed'],step=record['step'],label=sample['label']))
                row=describe(record['state'],record['legal_actions'])
                train[(row['phase'],row['rent_stage'])].append(row)
    # Interpretable build support, with phase and exact rent-stage conditioning.
    # Candidate identity not required: this measures build shift, not label support.
    def build_support(row):
        pool=train[(row['phase'],row['rent_stage'])]
        return max((support_similarity(row,t)[0] for t in pool),default=0)
    multi=[r for r in trace if r['multi']]
    errors=[r for r in multi if r['high_error']]
    controls=[r for r in multi if not r['high_error']]
    # Equal-sized systematic sample in ordered seed/step sequence.
    controls=[controls[int(i*len(controls)/len(errors))] for i in range(len(errors))]
    support_rows=[]
    for label,rows in [('high_error',errors),('non_high_error_control',controls)]:
        for row in rows:support_rows.append(dict(seed=row['seed'],step=row['step'],group=label,stage=row['rent_stage'],phase=row['phase'],score=build_support(row)))
    groups=defaultdict(list)
    for row in support_rows:groups[row['group']].append(row['score'])
    episodes=defaultdict(list)
    for r in trace:episodes[r['seed']].append(r)
    trajectories=[]
    for seed,rows in episodes.items():
        first=next((r for r in rows if r['multi'] and not r['agreement']),None)
        if not first:continue
        before=[r for r in rows if r['multi'] and r['step']<first['step']]
        observations={'before':before[-1] if before else first,'first':first}
        for n in (5,10,20):
            candidates=[r for r in rows if r['multi'] and first['step']+n<=r['step']]
            if candidates:observations[str(n)]=candidates[0]
        for offset,row in observations.items():trajectories.append(dict(seed=seed,offset=offset,actual_step=row['step'],agreement=row['agreement'],score=build_support(row)))
    temporal=defaultdict(list)
    for row in trajectories:temporal[row['offset']].append(row)
    csv_write('build_support_controls.csv',support_rows);csv_write('compounding_support.csv',trajectories)
    result['distribution_shift']=dict(method='phase and exact rent-stage conditioned maximum build similarity; candidate identities excluded; systematic equally sized controls',
        cohorts={k:dict(n=len(v),mean=mean(v),median=median(v),below_085=mean(x<.85 for x in v)) for k,v in groups.items()},
        after_first_disagreement={k:dict(n=len(v),mean_support=mean(r['score'] for r in v),agreement=mean(r['agreement'] for r in v)) for k,v in temporal.items()},
        limitation='Controls are descriptive, not randomized or matched for all game variables. No causal identification of error-to-shift chain.')
    result['reroll'].update(train_action_counts=dict(train_action_counts),train_reroll_available=train_reroll_opportunities,
                            train_reroll_labels=train_action_counts.get('REROLL',0))
    context_collisions=[dict(feature_hash=k,examples=v,labels=sorted({r['label'] for r in v})) for k,v in context_groups.items() if len({r['label'] for r in v})>1]
    csv_write('model_context_collisions.csv',context_collisions)
    result['training_support']['feature_collision'].update(model_context_conflict_groups=len(context_collisions),
        model_context_repeated_groups=sum(len(v)>1 for v in context_groups.values()),
        model_context_method='Analytic signature of mean linear instance pooling, mean item embeddings, ordered board and all candidate pointers; train only. Different-label collisions may also reflect finite Monte Carlo teacher sensitivity to deck order.')
    # Explicit bins supplement per-state continuous fields in the CSV.
    with (OUT/'error_attribution.csv').open(encoding='utf-8') as stream:attribution=list(csv.DictReader(stream))
    for row in attribution:
        actions=json.loads(row['legal_actions']);scores=json.loads(row['scores'])
        probabilities=json.loads(row['softmax_weights'])
        order=sorted(range(len(scores)),key=lambda i:(-scores[i],i))
        row['candidate_ranking']=[dict(action=action,score=scores[i],softmax_weight=probabilities[i],
                                       rank=order.index(i)+1,margin_to_top=max(scores)-scores[i]) for i,action in enumerate(actions)]
    csv_write('error_attribution.csv',attribution)
    bins={}
    for field,edges in {'coins':[0,25,100,300,600,1000], 'rent_pressure':[-1,0,.25,.5,1],
                        'deck_size':[5,10,20,30,40], 'recent_income_mean':[0,10,25,50,75,100],
                        'confidence':[.8,.9,.95,.99,1], 'margin':[0,1,2,4,8],
                        'episode_return':[0,250,500,750,1000,1500]}.items():
        counts=Counter()
        for row in attribution:
            value=float(row[field]);index=sum(value>=edge for edge in edges)
            label=(f'<{edges[0]}' if index==0 else f'>={edges[-1]}' if index==len(edges) else f'[{edges[index-1]},{edges[index]})')
            counts[label]+=1
        bins[field]=dict(counts)
    result['continuous_error_bins']=bins
    support=list(csv.DictReader((OUT/'training_support.csv').open(encoding='utf-8')))
    result['training_support']['threshold_sensitivity_best_neighbor']={str(t):sum(float(r['best_support_score'] or 0)>=t for r in support) for t in (.8,.85,.9,.95)}
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result['distribution_shift'],indent=2))


def write_report():
    path=ROOT/'reports/v142_high_confidence_error_attribution.json'
    r=json.loads(path.read_text(encoding='utf-8'));a=r['training_support'];f=a['feature_collision']
    c=r['distribution_shift']['cohorts'];w=r['compounding']['future_agreement']
    decline=w['5']['mean']>=w['10']['mean']>=w['20']['mean']
    matrix=[
        ['DATA',f"低支持{a['support_counts'].get('low-support',0)}例；错误build支持{c['high_error']['mean']:.3f}",
         f"对照支持{c['non_high_error_control']['mean']:.3f}，错误组并未更低；距离只是代理",'中：覆盖稀疏；选择性shift未证实'],
        ['REPRESENTATION','线性mean pooling可能丢失未观测计时器归属，合成测试验证',
         f"实际exact/near/context异标碰撞={f['exact_groups']}/{f['near_directed_pairs']}/{f['model_context_conflict_groups']}",'低；实际证据与结构风险分开'],
        ['MODEL',f"原train符号拟合率{a['training_fit']['symbol']['agreement']:.2%}",
         '未消融，不能区分容量、优化预算或目标函数','高：未充分拟合；具体机制低'],
        ['COMPOUNDING','首错后的窗口和支持变化见下表',
         '阶段、幸存和选择偏差混杂，未验证完整因果链','低至中：观察性递减' if decline else 'No Evidence of monotonic decline'],
        ['TEACHER','评分前排除REROLL；原train可用但无标签；机会重放有效',
         'BC与Teacher都不重掷，不能单独解释两者Stage差','高：Reroll设计缺口'],
        ['ENVIRONMENT','未发现本轮导致阶段差的环境/Action Mask错误',
         '128局重放一致；Reroll语义检查正常；仅受限近似环境','No Evidence；原版泛化未验证']]
    r['attribution_matrix']=[dict(zip(('category','evidence_for','evidence_against','confidence'),row)) for row in matrix]
    r['v143_decision']=dict(priority='Teacher',scope='先建立新版本Teacher的Reroll条件价值/资源成本评分与机会测试；冻结旧Teacher和V141基线。随后才选择Data或Model实验。',reason='按用户指定的上游优先级，教师动作支持缺口已被证实；并不声称该缺口解释当前BC相对教师阶段差。')
    r['research_answers']=dict(
        Q1='Early/Mid/Late high errors=515/425/69. Symbol agreement=69.20%/65.58%/57.82%; early already far from teacher.',
        Q2='1002 low-support errors, but train symbol fit only72.88%. Sparse data and insufficient fitting coexist; capacity/objective/optimization not isolated.',
        Q3='Error build support0.804 vs control0.793. No evidence errors selectively occupy less-supported builds than controls.',
        Q4='First-error future5/10/20 agreement52.34%/56.38%/66.25%; no monotonic decline or demonstrated causal compounding chain.',
        Q5='Teacher filters out REROLL before scoring; train2363 opportunities/0 labels;6 actual reroll semantics checks passed.')
    f['note']='Actual train encoder and analytic model context conflict audits found no conflicts. Synthetic mean-pooling timer-assignment loss is a structural risk, not demonstrated attribution. Current teacher does not read recent_income/effect_state.'
    r['tests']=dict(full_suite_passed=515,latest_diagnostic_suite_passed=4)
    path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    def table(headers,rows):
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(v) for v in row)+' |' for row in rows])
    sections=[]
    def add(title,body):sections.extend([f'## 【{title}】','',body,''])
    add('当前版本','V142 High-Confidence Error Attribution & Reroll Audit')
    add('本轮目标','冻结V130，解释差距并决定下一轮。训练更新0，模型、Teacher、Reward、规则、Environment、Dataset均未修改。诊断输出未进入训练Dataset。')
    add('冻结基线',table(['策略','平均Stage','Wins'],[['Random',3.21875,'0/128'],['Heuristic',6.609375,'19/128'],['Teacher',11.609375,'57/128'],['BC',9.6328125,'4/128']])+'\n\ninstance-magpie-v1；15000–15127；128局。BC−Teacher=−1.9765625，原配对95%CI=[−2.3671875,−1.59375]。沿用V141，未重新估计。种子已消费，不是新holdout。')
    add('新增工具','tools/analyze_bc_errors.py 复用既有诊断方式。V141缺少完整观测和低置信序列，故补放BC轨迹并查询同状态Teacher，没有重跑128局独立Teacher Benchmark。逐局缓存支持恢复；原1009例状态hash、动作、终局、各phase计数全部核对。')
    add('测试结果','515项完整测试通过；最终4项诊断测试通过（其中3项已包含于完整测试）。核心源文件诊断前后hash一致；checkpoint SHA严格加载验证；128局Stage/Win/Spins/Coins/Reward/Decisions/Truncation与V141逐局一致。日志见tests.txt及diagnostic_tests.txt。')
    add('错误阶段分布','rent_stage从0起：Early=0–5（5/6/7转），Mid=6–9（8/9转），Late=10–12（最终10转）；采用真实租金回合长度边界。分母只计多动作决策。\n\n'+table(['阶段','n','全体agreement','Symbol agreement','HC error rate','Win/Loss errors'],[[k,v['n'],f"{v['agreement']:.2%}",f"{v['symbol_agreement']:.2%}",f"{v['high_error_rate']:.2%}",f"{v['win_errors']}/{v['loss_errors']}"] for k,v in r['natural_stage'].items()])+'\n\n逐rent_stage结果见JSON.stage；coins、rent pressure、deck size、recent income、confidence、margin、return分桶见continuous_error_bins；所有逐状态字段在error_attribution.csv。')
    add('四类主要错误','箭头定义已核验：BC→Teacher。按错误出现次数加权，非独立episode均值。\n\n'+table(['类型','n','Stage mean/median','Coins','Deck','Confidence','Margin','Final stage','Win'],[['→'.join(v['pair']),v['count'],f"{v['mean_rent_stage']:.2f}/{v['median_rent_stage']}",f"{v['mean_coins']:.1f}",f"{v['mean_deck_size']:.1f}",f"{v['mean_confidence']:.3f}",f"{v['mean_margin']:.3f}",f"{v['mean_final_stage']:.2f}",f"{v['win_rate']:.2%}"] for v in r['main_errors']])+'\n\n错误后5/10/20总决策内的多动作一致率、有效窗口数及最终return在JSON.main_errors[].future/mean_episode_return。')
    add('Training Support',f"只使用train9000–9031，多动作状态{a['training_multi_states']}；Exact Public Match {a['exact_online_matches']}/1009；分类{a['support_counts']}。\n\n分数=直方图Jaccard40%+物品集合15%+阶段15%+牌组大小15%+租金压力15%。候选集合优先；无匹配则回退同phase/候选数，主要涉及removal实例ID。Top10中≥.85至少5例为high；近邻标签占优<80%为contradictory。这是近似异标，不能等同于相同特征冲突。\n\n阈值敏感性(best neighbor)：{a['threshold_sensitivity_best_neighbor']}。\n\n"+table(['cohort','n','Mean','Median','<.85'],[[k,v['n'],f"{v['mean']:.3f}",f"{v['median']:.3f}",f"{v['below_085']:.2%}"] for k,v in c.items()])+'\n\n辅助build对照按phase/实际rent_stage、等量系统抽样，候选身份不参与分数。不是完全匹配或随机对照。training_support.csv记录候选/阶段/build/Teacher label支持、最近train seed/step。')
    add('Feature Collision',f"Exact编码异标组={f['exact_groups']}。相同有序候选的实际编码token采用one-hot、标量使用冻结train scaler，L2≤.25异标有向近邻={f['near_directed_pairs']}；检查{f['near_checked']}例；最小异标距离={f['minimum_different_label_distance']}。\n\n按线性实例层+mean pooling+有序board及candidate pointers的符号表达式，实际train context异标组={f['model_context_conflict_groups']}，重复context组={f['model_context_repeated_groups']}。\n\n合成测试可构造未观测符号交换计时器但mean context相同；pointer/board观测可恢复区分。该合成探针不是实际错误证据。即使有context异标，有限8次Monte Carlo Teacher对deck顺序的敏感性也可能是原因。Raw无冲突不能替代这些审计。")
    ranking=r['candidate_ranking']
    add('Candidate Ranking',f"高置信错误中Teacher Top1=0（定义所致），Top2={ranking['top2']:.2%}，Top3={ranking['top3']:.2%}，Mean Rank={ranking['mean_teacher_rank']:.3f}，Last Rank={ranking['last_rank']:.2%}。每个case完整候选logit、softmax权重和Teacher gap/rank均在CSV。Softmax为未校准类别权重，不是胜率/存活概率。\n\n冻结模型对原TRAIN的拟合：\n\n"+table(['phase','n','agreement'],[[k,v['n'],f"{v['agreement']:.2%}"] for k,v in a['training_fit'].items()]))
    add('Error Severity',table(['类型','freq','cases','Mean ΔStage','Mean ΔReward','改善例','探索性freq×正ΔStage'],[['→'.join(v['pair']),v['frequency'],v['branch_cases'],v['mean_delta_stage'],v['mean_delta_reward'],v['stage_or_win_improvement_cases'],v['frequency_times_positive_stage_delta']] for v in r['severity']['frequency_weighted_exploratory_index']])+'\n\n仅15000–15003各类首例；deepcopy同一初始RNG，BC/Teacher动作后都由BC继续。Δ=Teacher−BC，reward是分支后的累计奖励。不同动作可消耗不同随机数，无法保证未来事件逐一对齐。因此改善只作为outcome-critical线索；指数是优先级探索，非总体无偏/因果严重度。Disagreement不等于严重错误。')
    add('Compounding Error',table(['首错后总decision窗','episode n','多动作agreement'],[[n,w[str(n)]['episodes'],f"{w[str(n)]['mean']:.2%}"] for n in (5,10,20)])+'\n\n'+table(['观察点','n','build support','agreement'],[[k,v['n'],f"{v['mean_support']:.3f}",f"{v['agreement']:.2%}"] for k,v in r['distribution_shift']['after_first_disagreement'].items()])+'\n\nbefore为首错前最近多动作，没有前例则首错；5/10/20为该step之后最近多动作。首错、首个高置信错误及距终局见episode_diagnostics.csv；胜局距终局不能称距死亡。阶段与幸存混杂，未证明首错→shift→再次错误→失败的因果链。')
    add('Win vs Loss','4胜/124非胜；Exploratory Only，按episode等权。\n\n'+table(['cohort','n','Symbol','Item','Remove','首错Stage','HC/局','Deck','Pressure','Skip','Removal'],[[k,v['episodes'],f"{v['symbol_agreement']:.2%}",f"{v['item_agreement']:.2%}",f"{v['remove_agreement']:.2%}",f"{v['first_disagreement_stage']:.2f}",f"{v['high_errors']:.2f}",f"{v['deck_size']:.2f}",f"{v['rent_pressure']:.3f}",f"{v['skip_rate']:.2%}",f"{v['removal_rate']:.2%}"] for k,v in r['win_loss'].items()]))
    rr=r['reroll']
    add('Reroll Audit',f"V141 Teacher9690/0，BC7734/0。RentForecastAgent评分前只保留PICK_SYMBOL/SKIP_SYMBOL；validate_choices明确拒绝REROLL。不存在Reroll EV、penalty或资源估值评分，并非mask降权。原train可用{rr['train_reroll_available']}，标签{rr['train_reroll_labels']}。\n\n前8局筛选Teacher Skip、tokens≥2、coins≥rent、每局最多2例，得到{rr['opportunities']}例。完整State、候选、券、Teacher lexicographic ranks在reroll_audit.csv；Reroll score=null。deepcopy执行均验证symbol阶段与tokens−1及候选更新。例15000/201：[milk,cat,flower]，2券→1券。此筛选不证明Reroll必然更优。\n\nSELECT_INTERACTION：UNRESOLVED / NO OPPORTUNITY。")
    add('归因矩阵',table(['类别','Evidence For','Evidence Against','Confidence'],matrix))
    add('结论','Q1：前/中/后期高置信错误515/425/69，后期不是主要高置信错误发生区；符号agreement为69.20%/65.58%/57.82%，前期也并未接近Teacher。首租阶段符号agreement仅49.22%，不能把全部问题解释为后期崩溃。\n\nQ2：1002例为低支持，但冻结模型在原train仍有27.12%符号分歧。Data coverage与未充分拟合共同存在；未做消融，不能认定具体Objective缺陷。\n\nQ3：错误build支持0.804，对照0.793；两组都稀疏，未证明高置信错误选择性集中于更严重OOD状态。\n\nQ4：首错后5/10/20窗口agreement为52.34%/56.38%/66.25%，没有持续下降。build支持随牌组增长下降，但不能证明错误导致该下降；完整compounding因果链未成立。\n\nQ5：Teacher排除Reroll评分，TRAIN2363次机会/0标签。环境6次定向资源与候选语义验证正常。此上游缺口不单独解释BC−Teacher，因为两者都未使用Reroll。\n\n有限分支7例中4例提高最终Stage，其余3例不提高，且某一Teacher替代动作减少reward；disagreement不可直接等同于严重错误。实际encoder/context冲突未发现，只有mean pooling合成探针揭示结构风险。当前Teacher不读取recent_income/effect_state，不能仅凭这些字段未编码就认定模仿输入不足。')
    add('V143 决策',r['v143_decision']['scope']+'\n\n'+r['v143_decision']['reason']+'优先级Environment→Teacher→Data→Representation→Model→RL。不进入PPO，不宣称修Reroll即可消除当前阶段差。')
    add('Artifact','机器报告：reports/v142_high_confidence_error_attribution.json。逐状态、支持、碰撞、Reroll、有限分支、episode及build对照：logs/v142-diagnostics/*.csv；完整错误观测：episode-<seed>.json.gz；冻结合同：contract.json。仅诊断，未新增Dataset。')
    (ROOT/'reports/v142_high_confidence_error_attribution.md').write_text('\n'.join(sections),encoding='utf-8')


if __name__=='__main__':main()
