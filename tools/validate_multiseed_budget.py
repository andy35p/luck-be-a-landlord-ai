"""V147 frozen-grid, continuation-verified budget and seed diagnostic."""
import csv
from collections import Counter
from copy import deepcopy
import ctypes
import gzip
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
from tools.audit_bc_optimization import (OUT as V146, BASE, CORPUS, ROOT as REPO,
    data, groups, metric_rows, read, sha, summarize, tensor_batch, write)
from luck_agent.agents.magpie_model import MagpieCandidateModel
from luck_agent.agents.magpie_corpus_checkpoint import contract

CONFIG=ROOT/'configs/v147_multiseed_generalization.json'
OUT=ROOT/'logs/v147-generalization'
HISTORY={123:V146/'budget_scaling/seed123',456:V146/'interference/seed456-multi',789:V146/'interference/seed789-multi'}

def process_peak_bytes():
    if sys.platform!='win32':return None
    from ctypes import wintypes
    class PMC(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
            ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
            ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
            ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
            ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
    x=PMC();x.cb=ctypes.sizeof(x)
    get_handle=ctypes.windll.kernel32.GetCurrentProcess
    get_handle.restype=ctypes.c_void_p
    query=ctypes.windll.psapi.GetProcessMemoryInfo
    query.argtypes=[ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD]
    query.restype=wintypes.BOOL
    if not query(get_handle(),ctypes.byref(x),x.cb):raise OSError('Memory query failed')
    return int(x.PeakWorkingSetSize)

def setup():
    config=read(CONFIG);OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'experiment_registry.json').exists():
        registry=read(OUT/'experiment_registry.json')
        if registry['config_sha256']!=sha(CONFIG):raise ValueError('Frozen V147 config changed')
        return registry
    if (config['budgets']!=[200,300,500,750,1000] or len(config['training_seeds'])!=5
            or len(set(config['training_seeds']))!=5):
        raise ValueError('Invalid pre-registered grid')
    pins=read(V146/'protected_hashes.json')
    for folder in (V146,):
        for p in folder.rglob('*'):
            if p.is_file():pins[p.relative_to(ROOT).as_posix()]=sha(p)
    for p in ROOT.glob('reports/v146*'):pins[p.relative_to(ROOT).as_posix()]=sha(p)
    pins['tools/audit_bc_optimization.py']=sha(ROOT/'tools/audit_bc_optimization.py')
    pins['tests/test_v146_bc_audit.py']=sha(ROOT/'tests/test_v146_bc_audit.py')
    write(OUT/'protected_hashes.json',pins)
    registry={'version':'V147','config_sha256':sha(CONFIG),'manifest_sha256':sha(CORPUS/'manifest.json'),
        'v130_sha256':sha(BASE/'research-200-updates.pt'),'seeds':config['training_seeds'],'budgets':config['budgets'],
        'source_checkpoint':{str(seed):{str(step):sha(folder/f'update-{step}.pt')
             for step in (200,500,1000) if (folder/f'update-{step}.pt').exists()}
             for seed,folder in HISTORY.items()},
        'source_resume':{str(seed):sha(folder/'resume-200.pt') for seed,folder in HISTORY.items()},
        'reuse_protocol':'restore exact optimizer/Python sampler at200; compare bitwise weights at500/1000 where available',
        'test_metrics':'SEALED','output_prefix':'logs/v147-generalization'}
    write(OUT/'experiment_registry.json',registry)
    return registry

def verify():
    pins=read(OUT/'protected_hashes.json')
    changed=[p for p,h in pins.items() if sha(ROOT/p)!=h]
    if changed:raise ValueError('Frozen assets changed: '+str(changed[:5]))
    return len(pins)

def checkpoint(seed,step,model,scaler,run):
    historical=HISTORY.get(seed)
    if historical and (historical/f'update-{step}.pt').exists():
        old=torch.load(historical/f'update-{step}.pt',map_location='cpu',weights_only=True)
        if any(not torch.equal(model.state_dict()[k],v) for k,v in old['state_dict'].items()):
            raise ValueError(f'Seed {seed} failed bitwise continuation at {step}')
        return {'path':(historical/f'update-{step}.pt').relative_to(ROOT).as_posix(),
            'sha256':sha(historical/f'update-{step}.pt'),'reused':True,'exact_weights':True}
    dest=run/'checkpoints'/f'update-{step}.pt';dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:torch.save({**contract(),'width':16,'training_updates':step,
        'scaler':scaler,'state_dict':model.state_dict()},f)
    return {'path':dest.relative_to(ROOT).as_posix(),'sha256':sha(dest),'reused':False,'exact_weights':None}

def evaluate(model,samples,caches,*,details=False):
    start=time.perf_counter();result={};rows_by_split={}
    for split,rows in samples.items():
        scored=metric_rows(model,rows,caches[split]);rows_by_split[split]=scored
        result[split]={'all':summarize(scored),'phases':{p:summarize([r for r in scored if r['phase']==p])
            for p in ('symbol','item','remove')},
            'symbol':summarize([r for r in scored if r['phase']=='symbol'])}
    return result,rows_by_split if details else None,time.perf_counter()-start

def run_seed(seed,samples,scaler):
    config=read(CONFIG);run=OUT/'seed_summaries'/str(seed)
    if (run/'run.json').exists():return read(run/'run.json')
    if (run/'config.json').exists():raise RuntimeError('Incomplete V147 seed run; inspect before retrying: '+str(seed))
    run.mkdir(parents=True,exist_ok=True)
    write(run/'config.json',{'seed':seed,'grid':config['budgets'],'config_sha256':sha(CONFIG),
        'dataset_sha256':sha(CORPUS/'manifest.json'),'v130_sha256':sha(BASE/'research-200-updates.pt'),
        'git_state':read(V146/'git_state.json')})
    torch.set_num_threads(1);torch.manual_seed(seed);model=MagpieCandidateModel(16).eval()
    if sum(p.numel() for p in model.parameters())!=config['expected_parameters']:raise ValueError('Parameter mismatch')
    optimizer=torch.optim.Adam(model.parameters(),lr=.001);rng=Random(seed);order=[];start_step=0
    historical=HISTORY.get(seed)
    if historical:
        old=torch.load(historical/'update-200.pt',map_location='cpu',weights_only=True)
        model.load_state_dict(old['state_dict'],strict=True)
        state=torch.load(historical/'resume-200.pt',map_location='cpu',weights_only=True)
        optimizer.load_state_dict(state['optimizer']);rng.setstate(state['rng_state']);order=state['order'];start_step=200
    caches={p:groups(rows) for p,rows in samples.items()}
    curve=[];budget_rows={};started=time.perf_counter();validation_time=0.;peak=process_peak_bytes()
    previous=read(historical/'result.json') if historical else None
    oldcurve=read(historical/'training_curve.json') if historical else []
    for row in oldcurve:
        if row['update']<=200 and row['update'] in config['curve_updates']:
            curve.append({'update':row['update'],'metrics':row['metrics'],'runtime':row['runtime'],
                'gradient_norm_before_clip':row.get('gradient_norm_before_clip'),
                'lr':row.get('lr',.001),'reused':True})
    if not historical:
        m,_,elapsed=evaluate(model,samples,caches);validation_time+=elapsed
        curve.append({'update':0,'metrics':m,'runtime':0.,'gradient_norm_before_clip':None,'lr':.001,'reused':False})
    train=samples['train']
    if historical:checkpoint(seed,200,model,scaler,run)
    for step in range(start_step+1,1001):
        chosen=[]
        for _ in range(64):
            if not order:order=list(range(len(train)));rng.shuffle(order)
            chosen.append(train[order.pop()])
        x,y=tensor_batch(chosen);optimizer.zero_grad();logits=model(x)
        loss=torch.nn.functional.cross_entropy(logits,y);loss.backward()
        if not torch.isfinite(loss):raise ValueError('Nonfinite CE')
        gradnorm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
        if step not in config['curve_updates']:continue
        m,details,elapsed=evaluate(model,samples,caches,details=step in config['budgets'])
        validation_time+=elapsed
        runtime=(previous['checkpoints']['200']['runtime'] if previous else 0.)+time.perf_counter()-started
        entry={'update':step,'metrics':m,'runtime':runtime,'gradient_norm_before_clip':float(gradnorm) if gradnorm is not None else None,
            'lr':optimizer.param_groups[0]['lr'],'reused':False}
        curve.append(entry);write(run/'training_curve.json',curve)
        if step in config['budgets']:
            pointer=checkpoint(seed,step,model,scaler,run)
            for split,rows in details.items():
                target=run/'details'/f'{split}-{step}.json.gz';target.parent.mkdir(parents=True,exist_ok=True)
                with gzip.open(target,'wt',encoding='utf-8') as f:json.dump(rows,f,separators=(',',':'))
            budget_rows[str(step)]={'metrics':m,'runtime':runtime,'evaluation_time':elapsed,'checkpoint':pointer,
                'peak_process_memory_bytes':process_peak_bytes()}
            write(run/'progress.json',budget_rows)
            print(json.dumps({'seed':seed,'update':step,'train_symbol':m['train']['symbol']['accuracy'],
                'val_symbol':m['validation']['symbol']['accuracy'],'exact':pointer['exact_weights']}),flush=True)
        peak=max(peak or 0,process_peak_bytes() or 0)
    # Recover the reused 200 budget row from exact saved model, with fresh detailed diagnostics.
    if historical:
        model200=MagpieCandidateModel(16);old=torch.load(historical/'update-200.pt',map_location='cpu',weights_only=True)
        model200.load_state_dict(old['state_dict']);m,details,elapsed=evaluate(model200,samples,caches,details=True)
        validation_time+=elapsed
        for split,rows in details.items():
            target=run/'details'/f'{split}-200.json.gz';target.parent.mkdir(parents=True,exist_ok=True)
            with gzip.open(target,'wt',encoding='utf-8') as f:json.dump(rows,f,separators=(',',':'))
        budget_rows['200']={'metrics':m,'runtime':previous['checkpoints']['200']['runtime'],
            'evaluation_time':elapsed,'checkpoint':checkpoint(seed,200,model200,scaler,run),
            'peak_process_memory_bytes':peak}
    if set(budget_rows)!={str(x) for x in config['budgets']}:raise ValueError('Incomplete seed grid')
    result={'seed':seed,'parameters':sum(p.numel() for p in model.parameters()),'budgets':budget_rows,
        'runtime_new_seconds':time.perf_counter()-started,'validation_time_new_seconds':validation_time,
        'peak_process_memory_bytes':peak,'source':'V146 exact 200-resume' if historical else 'new seed from scratch',
        'test_metrics':'SEALED','curve_path':(run/'training_curve.json').relative_to(ROOT).as_posix()}
    write(run/'run.json',result);return result

def execute():
    registry=setup();_,scaler,_,samples=data()
    for seed in registry['seeds']:run_seed(seed,samples,scaler)
    count=verify();write(OUT/'frozen_verification.json',{'files':count,'all_match':True})
    print(json.dumps({'seeds':len(registry['seeds']),'budgets':len(registry['budgets']),'frozen_files':count}),flush=True)

def load_detail(seed,split,step):
    p=OUT/'seed_summaries'/str(seed)/'details'/f'{split}-{step}.json.gz'
    with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)

def bucket_metrics(rows,bucket_map):
    symbols=[r for r in rows if r['phase']=='symbol']
    def target(r):return 'SKIP' if r['skip'] else r['teacher_target']
    return {b:summarize([r for r in symbols if bucket_map.get(target(r),'unseen')==b])
        for b in ('head','medium','tail','unseen')}

def rollup(values):
    n=len(values);mean=statistics.mean(values);std=statistics.stdev(values) if n>1 else 0.
    return {'n':n,'mean':mean,'std':std,'ci95':[mean-2.776445105*std/math.sqrt(n),mean+2.776445105*std/math.sqrt(n)],
        'median':statistics.median(values),'min':min(values),'max':max(values)}

def bootstrap(values,seed,n):
    rng=Random(seed);m=len(values);rep=sorted(sum(values[rng.randrange(m)] for _ in values)/m for _ in range(n))
    return [rep[int(.025*(n-1))],rep[int(.975*(n-1))]]

def write_csv(path,rows):
    if not rows:return
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def analyze():
    reg=setup();config=read(CONFIG);runs={seed:read(OUT/'seed_summaries'/str(seed)/'run.json') for seed in reg['seeds']}
    for seed,run in runs.items():
        if run['parameters']!=28785 or set(run['budgets'])!={str(x) for x in reg['budgets']} or run['test_metrics']!='SEALED':
            raise ValueError('Run contract incomplete')
    bucket_map=read(V146/'error_analysis/frequency.json')['buckets']
    summary=[];freq_rows=[];confusions=[];seed_rows=[]
    for seed,run in runs.items():
        for step in reg['budgets']:
            metrics=run['budgets'][str(step)]['metrics'];train=metrics['train']['symbol'];val=metrics['validation']['symbol']
            row={'seed':seed,'updates':step,'train_symbol_fit':train['accuracy'],'val_symbol_fit':val['accuracy'],
                'train_symbol_ce':train['ce'],'val_symbol_ce':val['ce'],'val_top2':val['top2'],
                'val_teacher_rank':val['mean_teacher_rank'],'val_high_confidence_wrong':val['high_confidence_wrong'],
                'generalization_gap':train['accuracy']-val['accuracy'],
                'runtime':run['budgets'][str(step)]['runtime'],
                'evaluation_time':run['budgets'][str(step)]['evaluation_time'],
                'peak_memory_bytes':run['budgets'][str(step)]['peak_process_memory_bytes']}
            seed_rows.append(row)
            for split in ('train','validation'):
                details=load_detail(seed,split,step);bins=bucket_metrics(details,bucket_map)
                for name,stats in bins.items():
                    freq_rows.append({'seed':seed,'updates':step,'split':split,'bucket':name,
                        'n':stats['n'],'correct':stats.get('correct',0),'accuracy':stats['accuracy'],
                        'ce':stats['ce'],'top2':stats['top2']})
                sym=[r for r in details if r['phase']=='symbol'];wrong=[r for r in sym if not r['correct']]
                pairs=Counter((('SKIP' if r['skip'] else r['teacher_target']),
                    ('SKIP' if r['choice_type'] in (1,3,8) else r['choice_target'])) for r in wrong)
                confusions.append({'seed':seed,'updates':step,'split':split,'wrong':len(wrong),
                    'rank2_wrong':sum(r['teacher_rank']==2 for r in wrong),'rank3plus_wrong':sum(r['teacher_rank']>=3 for r in wrong),
                    'mean_prediction_confidence':statistics.mean(r['confidence'] for r in sym),
                    'mean_wrong_confidence':statistics.mean(r['confidence'] for r in wrong) if wrong else None,
                    'mean_wrong_margin':statistics.mean(r['wrong_margin'] for r in wrong) if wrong else None,
                    'high_confidence_wrong':sum(r['high_confidence_wrong'] for r in wrong),
                    'pairs':[[a,b,n] for (a,b),n in pairs.most_common()]})
    fields=('train_symbol_fit','val_symbol_fit','train_symbol_ce','val_symbol_ce','val_top2','val_teacher_rank',
            'val_high_confidence_wrong','generalization_gap','runtime','evaluation_time','peak_memory_bytes')
    for step in reg['budgets']:
        rows=[r for r in seed_rows if r['updates']==step]
        summary.append({'updates':step,'seeds':len(rows),**{f:rollup([r[f] for r in rows]) for f in fields}})
    pairs=[]
    for high,low in config['paired_comparisons']:
        differences=[next(r for r in seed_rows if r['seed']==seed and r['updates']==high)['val_symbol_fit']-
                     next(r for r in seed_rows if r['seed']==seed and r['updates']==low)['val_symbol_fit'] for seed in reg['seeds']]
        mean=statistics.mean(differences)
        pairs.append({'higher':high,'lower':low,'per_seed':dict(zip(map(str,reg['seeds']),differences)),
            'mean_delta':mean,'bootstrap_ci95':bootstrap(differences,config['bootstrap_seed']+high*1000+low,config['bootstrap_iterations']),
            'better':sum(x>0 for x in differences),'equal':sum(x==0 for x in differences),'worse':sum(x<0 for x in differences)})
    fixed=200;gate=config['candidate_gate'];selection=[]
    for step in reg['budgets'][1:]:
        high=next(x for x in summary if x['updates']==step);base=summary[0]
        paired=next(x for x in pairs if x['higher']==step and x['lower']==fixed)
        details=[]
        if paired['mean_delta']*100<gate['mean_val_symbol_gain_pp_min']:details.append('mean top1 gain below 2pp')
        if paired['better']+paired['equal']<gate['non_worse_seeds_min']:details.append('fewer than 4/5 seeds non-worse')
        if high['val_symbol_ce']['mean']>base['val_symbol_ce']['mean']+gate['val_ce_mean_max_increase']:details.append('validation CE worsened')
        if high['val_teacher_rank']['mean']>base['val_teacher_rank']['mean']+gate['mean_teacher_rank_max_increase']:details.append('teacher rank worsened')
        for phase in ('item','remove'):
            before=statistics.mean(runs[s]['budgets']['200']['metrics']['validation']['phases'][phase]['accuracy'] for s in reg['seeds'])
            after=statistics.mean(runs[s]['budgets'][str(step)]['metrics']['validation']['phases'][phase]['accuracy'] for s in reg['seeds'])
            if (after-before)*100 < -gate[f'{phase}_val_accuracy_max_drop_pp']:details.append(f'{phase} regression >2pp')
        before=statistics.mean(next(r for r in freq_rows if r['seed']==s and r['updates']==200 and r['split']=='validation' and r['bucket']=='tail')['accuracy'] for s in reg['seeds'])
        after=statistics.mean(next(r for r in freq_rows if r['seed']==s and r['updates']==step and r['split']=='validation' and r['bucket']=='tail')['accuracy'] for s in reg['seeds'])
        if (after-before)*100 < -gate['tail_val_accuracy_max_drop_pp']:details.append('tail regression >2pp')
        selection.append({'updates':step,'eligible':not details,'gate_failures':details,'mean_gain_pp':paired['mean_delta']*100})
    eligible=[x for x in selection if x['eligible']]
    chosen=min(eligible,key=lambda x:x['updates'])['updates'] if eligible else None
    canonical=None
    if chosen is not None:
        ranked=sorted(((next(r for r in seed_rows if r['seed']==seed and r['updates']==chosen)['val_symbol_fit'],seed) for seed in reg['seeds']))
        canonical=ranked[2][1]
    best={}
    for seed,run in runs.items():
        curve=read(OUT/'seed_summaries'/str(seed)/'training_curve.json')
        def val_symbol(x):
            m=x['metrics']['validation']
            return m['symbol'] if 'symbol' in m else m['phases']['symbol']
        best[str(seed)]={'ce_update':min(curve,key=lambda x:(val_symbol(x)['ce'],x['update']))['update'],
            'top1_update':max(curve,key=lambda x:(val_symbol(x)['accuracy'],-x['update']))['update']}
    result={'version':'V147','registry':reg,'budget_summary':summary,'paired_comparison':pairs,'frequency_bucket_metrics':freq_rows,
        'confusion_metrics':confusions,'seed_rows':seed_rows,'candidate_gate':selection,
        'selected_budget':chosen,'canonical_seed':canonical,'best_curve_points':best,'test_metrics':'SEALED',
        'frozen_files':read(OUT/'frozen_verification.json')['files']}
    write(OUT/'analysis.json',result)
    write_csv(OUT/'budget_summary.csv',[{'updates':r['updates'],'seeds':r['seeds'],**{f+'_mean':r[f]['mean'] for f in fields},
        **{f+'_std':r[f]['std'] for f in fields}} for r in summary])
    write_csv(OUT/'paired_budget_comparison.csv',[{'higher':r['higher'],'lower':r['lower'],'mean_delta':r['mean_delta'],
        'ci_low':r['bootstrap_ci95'][0],'ci_high':r['bootstrap_ci95'][1],'better':r['better'],'equal':r['equal'],'worse':r['worse'],
        **{'seed_'+k:v for k,v in r['per_seed'].items()}} for r in pairs])
    write_csv(OUT/'frequency_bucket_metrics.csv',freq_rows)
    print(json.dumps({'seeds':len(runs),'budgets':len(summary),'candidate':chosen,'canonical_seed':canonical}),flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['setup','execute','analyze','verify'])
    cmd=parser.parse_args().command
    {'setup':setup,'execute':execute,'analyze':analyze,'verify':verify}[cmd]()
