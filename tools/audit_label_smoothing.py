"""V149 single-variable label-smoothing audit on sealed V128 train/dev data."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
from random import Random
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import torch
from luck_agent.agents.magpie_model import MagpieCandidateModel
from luck_agent.agents.magpie_corpus_checkpoint import contract
from tools.audit_bc_optimization import groups,tensor_batch
from tools.v149_data import load_v149_data

CONFIG=ROOT/'configs/v149_label_smoothing.json'
OUT=ROOT/'logs/v149-label-smoothing'
V148=ROOT/'logs/v148-checkpoint-selection'
V147=ROOT/'logs/v147-generalization'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def eps_key(epsilon):return f'{epsilon:.2f}'

def baseline_pointer(seed):
    run=read(V147/'seed_summaries'/str(seed)/'run.json');return run['budgets']['500']['checkpoint']

def setup():
    cfg=read(CONFIG);OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'experiment_registry.json'
    if target.exists():
        registry=read(target)
        if registry['config_sha256']!=digest(CONFIG):raise ValueError('Frozen V149 config changed')
        return registry
    if cfg['epsilons']!=[0.,.02,.05,.1] or cfg['training_seeds']!=[123,456,789,24680,13579]:
        raise ValueError('Invalid pre-registered grid')
    old=read(V148/'protected_hashes.json')
    pins={p:h for p,h in old.items() if '/test-' not in p.replace('\\','/') and p!='logs/v128-magpie-shards/manifest.json'}
    for folder in (V148,V147):
        for p in folder.rglob('*'):
            rel=p.relative_to(ROOT).as_posix()
            if p.is_file() and '/test-' not in rel and rel!='logs/v128-magpie-shards/manifest.json':pins[rel]=digest(p)
    for pattern in ('v147*','v148*'):
        for p in (ROOT/'reports').glob(pattern):
            if p.is_file():pins[p.relative_to(ROOT).as_posix()]=digest(p)
    write(OUT/'protected_hashes.json',pins)
    pointers={str(seed):baseline_pointer(seed) for seed in cfg['training_seeds']}
    registry={'version':'V149','config_sha256':digest(CONFIG),'runs':20,'seeds':cfg['training_seeds'],
        'epsilons':cfg['epsilons'],'baseline_checkpoints':pointers,'test_access':'FORBIDDEN',
        'v128_manifest_access':'FORBIDDEN','protected_files_excluding_test_and_manifest':len(pins),
        'status':'PRE-REGISTERED BEFORE NEW RESULTS'}
    write(target,registry);write(OUT/'preregistration.json',{'config':cfg,'config_sha256':digest(CONFIG),
        'registry_sha256_after_write':None,'test_access':'FORBIDDEN'})
    return registry

def masked_label_smoothing_loss(logits,labels,valid_mask,epsilon):
    if epsilon==0:return torch.nn.functional.cross_entropy(logits,labels)
    if not 0.<epsilon<1.:raise ValueError('epsilon must be in [0,1)')
    if valid_mask.dtype is not torch.bool or valid_mask.shape!=logits.shape:raise ValueError('valid mask mismatch')
    logp=torch.log_softmax(logits,dim=1)
    hard=-logp.gather(1,labels[:,None]).squeeze(1)
    safe=logp.masked_fill(~valid_mask,0.)
    uniform=-safe.sum(1)/valid_mask.sum(1).to(logp.dtype)
    return ((1.-epsilon)*hard+epsilon*uniform).mean()

def action_name(action):
    if action['action_type'] in (1,3,8):return 'SKIP'
    if action['action_type']==5:return 'REROLL'
    return str(action['target_id'])

def score_rows(model,rows,cached):
    model.eval();result=[];offset=0
    with torch.no_grad():
        for x,y in cached:
            logits=model(x);probs=logits.softmax(1);pred=logits.argmax(1)
            ce=torch.nn.functional.cross_entropy(logits,y,reduction='none')
            order=torch.argsort(logits,dim=1,descending=True,stable=True)
            ranks=(order==y[:,None]).long().argmax(1)+1
            for i in range(len(y)):
                sample=rows[offset+i];n=len(sample['candidates']);label=int(y[i]);choice=int(pred[i])
                values=logits[i,:n].tolist();pv=probs[i,:n].tolist();actions=sample['metadata']['actions']
                other=max(values[j] for j in range(n) if j!=label);correct=choice==label
                brier=sum((p-(1. if j==label else 0.))**2 for j,p in enumerate(pv))
                result.append({'seed':sample['metadata']['seed'],'step':sample['metadata']['step'],
                    'phase':sample['metadata']['decision_type'],'candidate_count':n,'correct':correct,
                    'top2':int(ranks[i])<=2,'teacher_rank':int(ranks[i]),'ce':float(ce[i]),
                    'confidence':float(pv[choice]),'brier':brier,
                    'teacher_margin':values[label]-other,
                    'decision_margin':values[label]-other if correct else values[choice]-values[label],
                    'high_confidence_wrong':not correct and float(pv[choice])>=.8,
                    'teacher':action_name(actions[label]),'choice':action_name(actions[choice])})
            offset+=len(y)
    if offset!=len(rows):raise ValueError('Evaluation coverage mismatch')
    return result

def summarize(rows):
    if not rows:return {'n':0,'accuracy':None,'ce':None,'top2':None,'mean_teacher_rank':None,'high_confidence_wrong':0,'brier':None,'ece10':None}
    bins=[[] for _ in range(10)]
    for r in rows:bins[min(int(r['confidence']*10),9)].append(r)
    ece=sum(len(b)/len(rows)*abs(statistics.mean(x['confidence'] for x in b)-statistics.mean(x['correct'] for x in b)) for b in bins if b)
    return {'n':len(rows),'correct':sum(x['correct'] for x in rows),'accuracy':statistics.mean(x['correct'] for x in rows),
        'ce':statistics.mean(x['ce'] for x in rows),'top2':statistics.mean(x['top2'] for x in rows),
        'mean_teacher_rank':statistics.mean(x['teacher_rank'] for x in rows),
        'high_confidence_wrong':sum(x['high_confidence_wrong'] for x in rows),
        'mean_wrong_confidence':statistics.mean(x['confidence'] for x in rows if not x['correct']) if any(not x['correct'] for x in rows) else None,
        'brier':statistics.mean(x['brier'] for x in rows),'ece10':ece,
        'rank1':sum(x['teacher_rank']==1 for x in rows),'rank2':sum(x['teacher_rank']==2 for x in rows),
        'rank3plus':sum(x['teacher_rank']>=3 for x in rows)}

def evaluate(model,samples,caches,details=False):
    metrics={};all_details={}
    for split,rows in samples.items():
        scored=score_rows(model,rows,caches[split]);all_details[split]=scored
        phases={p:summarize([x for x in scored if x['phase']==p]) for p in ('symbol','item','remove')}
        metrics[split]={'all':summarize(scored),'phases':phases,'symbol':phases['symbol']}
    return metrics,all_details if details else None

def historical_model(seed):
    pointer=baseline_pointer(seed);path=ROOT/pointer['path']
    if digest(path)!=pointer['sha256']:raise ValueError('Historical checkpoint drift')
    return torch.load(path,map_location='cpu',weights_only=True),pointer

def run_path(epsilon,seed):return OUT/'runs'/f'epsilon-{eps_key(epsilon)}'/f'seed-{seed}'

def train_one(epsilon,seed,data):
    folder=run_path(epsilon,seed);complete=folder/'run.json'
    if complete.exists():return read(complete)
    folder.mkdir(parents=True,exist_ok=True);cfg=read(CONFIG)
    train=data['train'];samples={'train':train,'validation':data['validation']};caches={k:groups(v) for k,v in samples.items()}
    torch.set_num_threads(1);torch.manual_seed(seed);model=MagpieCandidateModel(16).eval()
    if sum(p.numel() for p in model.parameters())!=cfg['model']['expected_parameters']:raise ValueError('Parameter contract changed')
    optimizer=torch.optim.Adam(model.parameters(),lr=cfg['model']['learning_rate']);rng=Random(seed);order=[];curve=[];started=time.perf_counter()
    for step in range(0,cfg['updates']+1):
        if step in cfg['curve_updates']:
            metrics,_=evaluate(model,samples,caches)
            curve.append({'update':step,'metrics':metrics,'objective_loss':None if step==0 else float(loss.detach()),
                'gradient_norm_before_clip':None if step==0 else float(norm),'runtime':time.perf_counter()-started})
            write(folder/'training_curve.json',curve)
        if step==cfg['updates']:break
        chosen=[]
        for _ in range(cfg['model']['batch_size']):
            if not order:order=list(range(len(train)));rng.shuffle(order)
            chosen.append(train[order.pop()])
        x,y=tensor_batch(chosen);optimizer.zero_grad();logits=model(x)
        loss=masked_label_smoothing_loss(logits,y,x['candidates_mask'],epsilon)
        if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
        loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['model']['gradient_clip_norm'])
        if not math.isfinite(float(norm)):raise ValueError('Nonfinite gradient norm')
        optimizer.step()
    metrics,details=evaluate(model,samples,caches,details=True)
    exact=None;historical_sha=None
    if epsilon==0:
        old,pointer=historical_model(seed);historical_sha=pointer['sha256']
        exact=all(torch.equal(model.state_dict()[k],v) for k,v in old['state_dict'].items())
        if not exact:raise ValueError(f'epsilon=0 bitwise regression for seed {seed}')
        if data['scaler']!=old['scaler']:raise ValueError('Full-train scaler regression')
    checkpoint=folder/'update-500.pt'
    payload={**contract(),'width':16,'training_updates':500,'scaler':data['scaler'],'state_dict':model.state_dict(),
        'v149_epsilon':epsilon,'v149_seed':seed,'test_access':'FORBIDDEN'}
    with checkpoint.open('xb') as f:torch.save(payload,f)
    for split,rows in details.items():write(folder/f'{split}_details.json',rows)
    result={'epsilon':epsilon,'seed':seed,'metrics':metrics,'curve':curve,'checkpoint':checkpoint.relative_to(ROOT).as_posix(),
        'checkpoint_sha256':digest(checkpoint),'epsilon_zero_bitwise_historical':exact,'historical_checkpoint_sha256':historical_sha,
        'runtime':time.perf_counter()-started,'test_access':'FORBIDDEN'}
    write(complete,result)
    print(json.dumps({'epsilon':epsilon,'seed':seed,'val_symbol':metrics['validation']['symbol']['accuracy'],
        'hc_wrong':metrics['validation']['symbol']['high_confidence_wrong'],'epsilon0_exact':exact}),flush=True)
    return result

def train():
    registry=setup();data=load_v149_data();write(OUT/'data_access.json',{'opened':data['opened'],'test_opened':False,
        'v128_manifest_opened':False,'train_raw':len(data['train_raw']),'validation_raw':len(data['validation_raw']),
        'train_decisions':len(data['train']),'validation_decisions':len(data['validation'])})
    old,_=historical_model(registry['seeds'][0])
    if data['scaler']!=old['scaler']:raise ValueError('Dedicated reader did not reproduce frozen scaler')
    # Complete and verify every epsilon-zero run before positive epsilon is allowed.
    for seed in registry['seeds']:train_one(0.,seed,data)
    write(OUT/'epsilon_zero_regression.json',{'all_five_bitwise':True,'seeds':registry['seeds'],
        'positive_epsilon_started_after_regression':True})
    for epsilon in registry['epsilons'][1:]:
        for seed in registry['seeds']:train_one(epsilon,seed,data)
    print(json.dumps({'runs':20,'test_opened':False}),flush=True)

def quantile(values,q):
    if not values:return None
    x=sorted(values);pos=(len(x)-1)*q;lo=int(math.floor(pos));hi=int(math.ceil(pos))
    return x[lo]+(x[hi]-x[lo])*(pos-lo)

def distribution(values):
    return {'n':len(values),'mean':statistics.mean(values) if values else None,'median':quantile(values,.5),
        'p90':quantile(values,.9),'p95':quantile(values,.95)}

def bootstrap(values,seed,n):
    rng=Random(seed);m=len(values);draws=sorted(statistics.mean(values[rng.randrange(m)] for _ in range(m)) for _ in range(n))
    return [draws[int(.025*(n-1))],draws[int(.975*(n-1))]]

def mean_sd(values):return {'mean':statistics.mean(values),'std':statistics.stdev(values),'values':values}

def write_csv(path,rows):
    if not rows:return
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def analyze():
    cfg=read(CONFIG);runs={(e,s):read(run_path(e,s)/'run.json') for e in cfg['epsilons'] for s in cfg['training_seeds']}
    bucket_map=read(ROOT/'logs/v146-bc-audit/error_analysis/frequency.json')['buckets'];seed_rows=[];confidence_rows=[];frequency_rows=[];confusions={}
    summaries=[]
    for epsilon in cfg['epsilons']:
        for seed in cfg['training_seeds']:
            run=runs[(epsilon,seed)];tm=run['metrics']['train']['symbol'];vm=run['metrics']['validation']['symbol']
            seed_rows.append({'epsilon':epsilon,'seed':seed,'train_symbol':tm['accuracy'],'val_symbol':vm['accuracy'],
                'standard_val_ce':vm['ce'],'val_top2':vm['top2'],'mean_rank':vm['mean_teacher_rank'],
                'hc_wrong':vm['high_confidence_wrong'],'wrong_confidence':vm['mean_wrong_confidence'],
                'ece10':vm['ece10'],'brier':vm['brier'],'generalization_gap':tm['accuracy']-vm['accuracy']})
            for split in ('train','validation'):
                rows=read(run_path(epsilon,seed)/f'{split}_details.json');symbols=[x for x in rows if x['phase']=='symbol']
                for correct in (True,False):
                    subset=[x for x in symbols if x['correct']==correct]
                    c=distribution([x['confidence'] for x in subset]);m=distribution([x['decision_margin'] for x in subset])
                    confidence_rows.append({'epsilon':epsilon,'seed':seed,'split':split,'outcome':'correct' if correct else 'wrong',
                        **{'confidence_'+k:v for k,v in c.items()},**{'margin_'+k:v for k,v in m.items()}})
                for bucket in ('head','medium','tail'):
                    subset=[x for x in symbols if bucket_map.get(x['teacher'],'unseen')==bucket];sm=summarize(subset)
                    frequency_rows.append({'epsilon':epsilon,'seed':seed,'split':split,'bucket':bucket,'n':sm['n'],
                        'accuracy':sm['accuracy'],'ce':sm['ce'],'mean_rank':sm['mean_teacher_rank']})
                pairs=Counter((x['teacher'],x['choice']) for x in symbols if not x['correct'])
                confusions[f'{eps_key(epsilon)}/{seed}/{split}']={'tracked':{
                    f'{a}->{b}':pairs[(a,b)] for a,b in cfg['tracked_confusions']},
                    'top10':[[list(pair),count] for pair,count in pairs.most_common(10)]}
        erows=[x for x in seed_rows if x['epsilon']==epsilon]
        summaries.append({'epsilon':epsilon,**{k:mean_sd([x[k] for x in erows]) for k in (
            'train_symbol','val_symbol','standard_val_ce','val_top2','mean_rank','hc_wrong','wrong_confidence','ece10','brier','generalization_gap')}})
    baseline={x['seed']:x for x in seed_rows if x['epsilon']==0};paired=[];gate_rows=[]
    for epsilon in cfg['epsilons'][1:]:
        current={x['seed']:x for x in seed_rows if x['epsilon']==epsilon}
        deltas=[current[s]['val_symbol']-baseline[s]['val_symbol'] for s in cfg['training_seeds']]
        row={'epsilon':epsilon,'per_seed_delta':dict(zip(map(str,cfg['training_seeds']),deltas)),'mean_delta':statistics.mean(deltas),
            'std':statistics.stdev(deltas),'bootstrap_ci95':bootstrap(deltas,cfg['bootstrap_seed']+int(epsilon*1000),cfg['bootstrap_iterations']),
            'better':sum(x>0 for x in deltas),'equal':sum(x==0 for x in deltas),'worse':sum(x<0 for x in deltas)}
        paired.append(row);summary=next(x for x in summaries if x['epsilon']==epsilon);base=summaries[0];g=cfg['candidate_gate']
        checks={'mean_top1_strictly_higher':row['mean_delta']>g['mean_validation_symbol_top1_delta_min_exclusive'],
            'at_least_four_non_lower':sum(x>=0 for x in deltas)>=g['non_lower_seed_count_min'],
            'mean_rank_not_worse':summary['mean_rank']['mean']-base['mean_rank']['mean']<=g['mean_teacher_rank_delta_max'],
            'standard_ce_not_clearly_worse':summary['standard_val_ce']['mean']-base['standard_val_ce']['mean']<=g['standard_validation_ce_delta_max'],
            'hc_wrong_decreased':summary['hc_wrong']['mean']-base['hc_wrong']['mean']<g['mean_high_confidence_wrong_delta_max_exclusive']}
        gate_rows.append({'epsilon':epsilon,'checks':checks,'passed':all(checks.values()),
            'rank_delta':summary['mean_rank']['mean']-base['mean_rank']['mean'],
            'ce_delta':summary['standard_val_ce']['mean']-base['standard_val_ce']['mean'],
            'hc_wrong_delta':summary['hc_wrong']['mean']-base['hc_wrong']['mean']})
    passed=[x['epsilon'] for x in gate_rows if x['passed']];selected=min(passed) if passed else None;canonical=None
    if selected is not None:
        ordered=sorted((runs[(selected,s)]['metrics']['validation']['symbol']['accuracy'],s) for s in cfg['training_seeds']);canonical=ordered[2][1]
    result={'version':'V149','summaries':summaries,'seed_rows':seed_rows,'paired_comparison':paired,'candidate_gate':gate_rows,
        'selected_epsilon':selected,'canonical_seed':canonical,'epsilon_zero_regression':read(OUT/'epsilon_zero_regression.json'),
        'confidence_analysis':confidence_rows,'frequency_bucket_metrics':frequency_rows,'confusions':confusions,
        'online_smoke':'TRIGGERED' if selected is not None else 'NOT TRIGGERED','test_access':'SEALED'}
    write(OUT/'analysis.json',result);write(OUT/'confusions.json',confusions)
    write_csv(OUT/'seed_metrics.csv',seed_rows);write_csv(OUT/'paired_comparison.csv',[{k:v for k,v in x.items() if k!='per_seed_delta' and k!='bootstrap_ci95'}|{'ci_low':x['bootstrap_ci95'][0],'ci_high':x['bootstrap_ci95'][1]} for x in paired])
    write_csv(OUT/'confidence_analysis.csv',confidence_rows);write_csv(OUT/'frequency_bucket_metrics.csv',frequency_rows)
    online=OUT/'online_smoke';online.mkdir(exist_ok=True);write(online/'status.json',{'status':result['online_smoke'],
        'selected_epsilon':selected,'canonical_seed':canonical,'test_access':'SEALED'})
    pins=read(OUT/'protected_hashes.json');changed=[p for p,h in pins.items() if digest(ROOT/p)!=h]
    if changed:raise ValueError('Historical asset drift: '+str(changed[:5]))
    write(OUT/'frozen_verification.json',{'checked':len(pins),'changed':changed,'test_shards_opened':False,'v128_manifest_opened':False})
    print(json.dumps({'selected_epsilon':selected,'canonical_seed':canonical,'gate':gate_rows,'test_opened':False}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['setup','train','analyze']);args=parser.parse_args()
    {'setup':setup,'train':train,'analyze':analyze}[args.command]()
