"""V148 train-internal checkpoint selection with lock-before-audit separation."""
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
from tools.audit_bc_optimization import groups,metric_rows,summarize,tensor_batch
from tools.v148_split_coverage import create_split_manifest,load_split_data,coverage

CONFIG=ROOT/'configs/v148_checkpoint_selection.json'
OUT=ROOT/'logs/v148-checkpoint-selection'
V147=ROOT/'logs/v147-generalization'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def setup():
    config=read(CONFIG);OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'experiment_registry.json').exists():
        registry=read(OUT/'experiment_registry.json')
        if registry['config_sha256']!=digest(CONFIG):raise ValueError('Frozen V148 config changed')
        return registry
    manifests=[]
    for spec in config['splits']:
        manifest=create_split_manifest(spec['split_seed'],8,name=spec['name'],training_seeds=tuple(spec['training_seeds']))
        if manifest['fit_episodes']!=spec['fit_episode_ids'] or manifest['selection_episodes']!=spec['selection_episode_ids']:
            raise ValueError('Pre-registered episode derivation mismatch')
        manifests.append(manifest)
    write(OUT/'split_manifest.json',{'version':'v148-split-manifests-v1','config_sha256':digest(CONFIG),'splits':manifests})
    old=read(V147/'protected_hashes.json')
    # V148 never opens old test shards or the V128 manifest (which embeds test outcomes).
    pins={p:h for p,h in old.items() if '/test-' not in p.replace('\\','/') and p!='logs/v128-magpie-shards/manifest.json'}
    for p in (ROOT/'reports').glob('v147*'):pins[p.relative_to(ROOT).as_posix()]=digest(p)
    for p in (ROOT/'logs/v147-generalization').rglob('*'):
        if p.is_file():pins[p.relative_to(ROOT).as_posix()]=digest(p)
    write(OUT/'protected_hashes.json',pins)
    registry={'version':'V148','config_sha256':digest(CONFIG),'split_manifest_sha256':digest(OUT/'split_manifest.json'),
        'training_runs':sum(len(x['training_seeds']) for x in config['splits']),
        'candidate_checkpoints':config['candidate_checkpoints'],'primary_selection_metric':config['primary_selection_metric'],
        'validation_access':'forbidden until checkpoint_choices.lock.json exists','test_access':'FORBIDDEN',
        'v128_manifest_access':'FORBIDDEN because it embeds test outcomes','protected_files_excluding_test_and_manifest':len(pins)}
    write(OUT/'experiment_registry.json',registry);return registry

def manifest_map():return {x['name']:x for x in read(OUT/'split_manifest.json')['splits']}

def model_metrics(model,rows,cached):
    details=metric_rows(model,rows,cached)
    phases={p:summarize([r for r in details if r['phase']==p]) for p in sorted({r['phase'] for r in details})}
    return {'all':summarize(details),'phases':phases,'symbol':phases['symbol']},details

def checkpoint_path(split,seed,update):return OUT/'checkpoints'/split/f'seed-{seed}'/f'update-{update}.pt'

def train_one(manifest,seed):
    run=OUT/'training_curves'/manifest['name']/f'seed-{seed}.json'
    if run.exists():return read(run)
    data=load_split_data(manifest,mode='train');fit=data['fit'];selection=data['selection'];scaler=data['scaler']
    torch.set_num_threads(1);torch.manual_seed(seed);model=MagpieCandidateModel(16)
    if sum(p.numel() for p in model.parameters())!=28785:raise ValueError('Parameter contract changed')
    optimizer=torch.optim.Adam(model.parameters(),lr=.001);rng=Random(seed);order=[]
    fit_cache=groups(fit);selection_cache=groups(selection);checkpoints={};curve=[];started=time.perf_counter()
    for step in range(1,1001):
        chosen=[]
        for _ in range(64):
            if not order:order=list(range(len(fit)));rng.shuffle(order)
            chosen.append(fit[order.pop()])
        x,y=tensor_batch(chosen);optimizer.zero_grad();logits=model(x)
        loss=torch.nn.functional.cross_entropy(logits,y);loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
        if step not in read(CONFIG)['candidate_checkpoints']:continue
        fm,_=model_metrics(model,fit,fit_cache);sm,details=model_metrics(model,selection,selection_cache)
        path=checkpoint_path(manifest['name'],seed,step);path.parent.mkdir(parents=True,exist_ok=True)
        payload={'version':'v148-fit-checkpoint-v1','split_hash':manifest['split_hash'],'seed':seed,'update':step,
            'model_width':16,'parameters':28785,'scaler':scaler,'state_dict':model.state_dict(),
            'test_access':'FORBIDDEN','development_validation_access':'NOT YET OPENED'}
        with path.open('xb') as stream:torch.save(payload,stream)
        record={'update':step,'fit':fm,'selection':sm,'batch_loss':float(loss.detach()),
            'gradient_norm_before_clip':float(norm),'lr':optimizer.param_groups[0]['lr'],
            'runtime':time.perf_counter()-started,'checkpoint':path.relative_to(ROOT).as_posix(),'sha256':digest(path)}
        checkpoints[str(step)]=record;curve.append(record)
        print(json.dumps({'split':manifest['name'],'seed':seed,'update':step,
            'selection_ce':sm['symbol']['ce'],'selection_top1':sm['symbol']['accuracy']}),flush=True)
    result={'split':manifest['name'],'split_hash':manifest['split_hash'],'seed':seed,'fit_episodes':manifest['fit_episodes'],
        'selection_episodes':manifest['selection_episodes'],'fit_samples':len(fit),'selection_samples':len(selection),
        'scaler':scaler,'checkpoints':checkpoints,'runtime':time.perf_counter()-started,
        'gradient_data':'FIT only','selection_gradient_steps':0,'development_validation_access':'NOT OPENED','test_access':'FORBIDDEN'}
    write(run,result);return result

def train():
    setup();manifests=manifest_map();config=read(CONFIG)
    if (OUT/'checkpoint_choices.lock.json').exists():raise ValueError('Choices already locked; training closed')
    for spec in config['splits']:
        for seed in spec['training_seeds']:train_one(manifests[spec['name']],seed)
    print(json.dumps({'runs':sum(len(x['training_seeds']) for x in config['splits']),'validation_opened':False}),flush=True)

def lock():
    setup();target=OUT/'checkpoint_choices.lock.json'
    if target.exists():return read(target)
    config=read(CONFIG);manifests=manifest_map();splits={}
    for spec in config['splits']:
        choices={}
        for seed in spec['training_seeds']:
            run=read(OUT/'training_curves'/spec['name']/f'seed-{seed}.json');rows=list(run['checkpoints'].values())
            if sorted(r['update'] for r in rows)!=config['candidate_checkpoints']:raise ValueError('Incomplete checkpoints')
            chosen=min(rows,key=lambda r:(r['selection']['symbol']['ce'],r['update']))
            top1=max(rows,key=lambda r:(r['selection']['symbol']['accuracy'],-r['update']))
            choices[str(seed)]={'ce_selected_update':chosen['update'],'top1_selected_update':top1['update'],
                'checkpoint_sha256':chosen['sha256'],'checkpoint':chosen['checkpoint'],
                'selection_symbol_ce':chosen['selection']['symbol']['ce'],
                'selection_symbol_top1':chosen['selection']['symbol']['accuracy'],
                'locked_before_development_validation':True}
        splits[spec['name']]={'split_hash':manifests[spec['name']]['split_hash'],'choices':choices}
    value={'version':'v148-checkpoint-choice-lock-v1','config_sha256':digest(CONFIG),
        'split_manifest_sha256':digest(OUT/'split_manifest.json'),'selection_rule':config['primary_selection_rule'],
        'development_validation_access_before_lock':False,'test_access':'FORBIDDEN','splits':splits}
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    write(OUT/'checkpoint_lock.sha256.json',{'path':target.relative_to(ROOT).as_posix(),'sha256':digest(target)})
    print(json.dumps({'locked_choices':sum(len(x['choices']) for x in splits.values()),'lock_sha256':digest(target)}),flush=True)
    return value

def load_model(path,expected_hash,manifest,seed,update):
    path=ROOT/path
    if digest(path)!=expected_hash:raise ValueError('Checkpoint changed after lock/training')
    payload=torch.load(path,map_location='cpu',weights_only=True)
    if (payload.get('version')!='v148-fit-checkpoint-v1' or payload.get('split_hash')!=manifest['split_hash']
            or payload.get('seed')!=seed or payload.get('update')!=update or payload.get('parameters')!=28785):
        raise ValueError('Checkpoint provenance mismatch')
    model=MagpieCandidateModel(16);model.load_state_dict(payload['state_dict']);return model.eval(),payload['scaler']

def audit():
    setup();lock_path=OUT/'checkpoint_choices.lock.json';lock=read(lock_path);lock_hash=read(OUT/'checkpoint_lock.sha256.json')['sha256']
    if digest(lock_path)!=lock_hash:raise ValueError('Choice lock changed')
    config=read(CONFIG);manifests=manifest_map();all_rows=[];coverage_rows={}
    bucket_map=read(ROOT/'logs/v146-bc-audit/error_analysis/frequency.json')['buckets']
    for spec in config['splits']:
        manifest=manifests[spec['name']];first=read(OUT/'training_curves'/spec['name']/f"seed-{spec['training_seeds'][0]}.json")
        audit_data=load_split_data(manifest,mode='audit',scaler=first['scaler'],lock_path=lock_path)
        # Scaler is split-specific, not seed-specific; assert every run used exactly it.
        for seed in spec['training_seeds']:
            run=read(OUT/'training_curves'/spec['name']/f'seed-{seed}.json')
            if run['scaler']!=first['scaler']:raise ValueError('Scaler varies by seed')
            choices=lock['splits'][spec['name']]['choices'][str(seed)];cached=groups(audit_data['audit'])
            for update in config['candidate_checkpoints']:
                source=run['checkpoints'][str(update)]
                model,_=load_model(source['checkpoint'],source['sha256'],manifest,seed,update)
                metrics,details=model_metrics(model,audit_data['audit'],cached)
                wrong=[r for r in details if r['phase']=='symbol' and not r['correct']]
                def target(row):return 'SKIP' if row['skip'] else row['teacher_target']
                frequency={bucket:summarize([r for r in details if r['phase']=='symbol'
                    and bucket_map.get(target(r),'unseen')==bucket]) for bucket in ('head','medium','tail','unseen')}
                all_rows.append({'split':spec['name'],'role':spec['role'],'seed':seed,'update':update,
                    'ce_selected':update==choices['ce_selected_update'],'top1_selected':update==choices['top1_selected_update'],
                    'metrics':metrics,'rank2_wrong':sum(r['teacher_rank']==2 for r in wrong),
                    'rank3plus_wrong':sum(r['teacher_rank']>=3 for r in wrong),
                    'mean_wrong_confidence':statistics.mean(r['confidence'] for r in wrong) if wrong else None,
                    'frequency_buckets':frequency,
                    'checkpoint_sha256':source['sha256']})
        train_data=load_split_data(manifest,mode='train')
        coverage_rows[spec['name']]={'fit':coverage(train_data['fit'],bucket_map=bucket_map),
            'selection':coverage(train_data['selection'],bucket_map=bucket_map),
            'development_validation':coverage(audit_data['audit'],bucket_map=bucket_map)}
    value={'version':'v148-selection-independent-development-audit-v1','lock_sha256':lock_hash,
        'audit_started_after_lock':True,'validation_role':'development audit; repeatedly observed in V146/V147, not untouched holdout',
        'test_access':'FORBIDDEN','rows':all_rows,'coverage':coverage_rows}
    write(OUT/'audit_raw.json',value);write(OUT/'coverage_audit.json',coverage_rows)
    verify=read(OUT/'protected_hashes.json');changed=[]
    for rel,expected in verify.items():
        # These explicit exclusions are the test-leakage contract, not skipped failures.
        normalized=rel.replace('\\','/')
        if '/test-' in normalized or normalized=='logs/v128-magpie-shards/manifest.json':continue
        if digest(ROOT/rel)!=expected:changed.append(rel)
    if changed:raise ValueError('Historical asset drift: '+str(changed[:5]))
    write(OUT/'frozen_verification.json',{'checked':len(verify),'changed':changed,
        'test_shards_opened':False,'v128_manifest_opened':False})
    print(json.dumps({'audit_rows':len(all_rows),'historical_changed':len(changed),'test_opened':False}),flush=True)

def bootstrap(values,seed,n=10000):
    rng=Random(seed);m=len(values);samples=sorted(sum(values[rng.randrange(m)] for _ in range(m))/m for _ in range(n))
    return [samples[int(.025*(n-1))],samples[int(.975*(n-1))]]

def write_csv(path,rows):
    if not rows:return
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def analyze():
    config=read(CONFIG);audit_data=read(OUT/'audit_raw.json');lock=read(OUT/'checkpoint_choices.lock.json');rows=audit_data['rows']
    primary=next(x for x in config['splits'] if x['role']=='primary');name=primary['name'];seeds=primary['training_seeds']
    flat=[];regret=[];choice_rows=[]
    for seed in seeds:
        sr=[r for r in rows if r['split']==name and r['seed']==seed];choice=lock['splits'][name]['choices'][str(seed)]
        oracle=max(sr,key=lambda r:(r['metrics']['symbol']['accuracy'],-r['update']))
        for r in sr:
            flat.append({'seed':seed,'update':r['update'],'ce_selected':r['ce_selected'],
                'val_top1':r['metrics']['symbol']['accuracy'],'val_ce':r['metrics']['symbol']['ce'],
                'val_top2':r['metrics']['symbol']['top2'],'mean_rank':r['metrics']['symbol']['mean_teacher_rank'],
                'high_conf_wrong':r['metrics']['symbol']['high_confidence_wrong'],'rank2_wrong':r['rank2_wrong'],
                'rank3plus_wrong':r['rank3plus_wrong'],'mean_wrong_confidence':r['mean_wrong_confidence']})
        selected=next(r for r in sr if r['ce_selected'])
        choice_rows.append({'seed':seed,'ce_selected_update':choice['ce_selected_update'],'top1_selected_update':choice['top1_selected_update'],
            'fixed300_val':next(r for r in sr if r['update']==300)['metrics']['symbol']['accuracy'],
            'fixed500_val':next(r for r in sr if r['update']==500)['metrics']['symbol']['accuracy'],
            'ce_selected_val':selected['metrics']['symbol']['accuracy'],'selection_ce':choice['selection_symbol_ce'],
            'hindsight_best_update':oracle['update']})
        item={'seed':seed,'oracle_update':oracle['update'],'oracle_val_top1':oracle['metrics']['symbol']['accuracy']}
        for label,update in [('ce_selected',choice['ce_selected_update']),('fixed200',200),('fixed300',300),('fixed500',500)]:
            actual=next(r for r in sr if r['update']==update)['metrics']['symbol']['accuracy'];item[label+'_regret']=oracle['metrics']['symbol']['accuracy']-actual
        regret.append(item)
    def policy(update_key):
        selected=[]
        for seed in seeds:
            update=lock['splits'][name]['choices'][str(seed)]['ce_selected_update'] if update_key=='ce_selected' else int(update_key[5:])
            selected.append(next(r for r in rows if r['split']==name and r['seed']==seed and r['update']==update))
        def agg(field):
            vals=[r['metrics']['symbol'][field] for r in selected]
            return {'mean':statistics.mean(vals),'std':statistics.stdev(vals),'values':dict(zip(map(str,seeds),vals))}
        fit_values=[]
        for seed,r in zip(seeds,selected):
            run=read(OUT/'training_curves'/name/f'seed-{seed}.json')
            fit_values.append(run['checkpoints'][str(r['update'])]['fit']['symbol']['accuracy'])
        frequency={bucket:{'accuracy_mean':statistics.mean(r['frequency_buckets'][bucket]['accuracy'] for r in selected),
            'accuracy_values':dict(zip(map(str,seeds),(r['frequency_buckets'][bucket]['accuracy'] for r in selected))),
            'n_per_seed':selected[0]['frequency_buckets'][bucket]['n']} for bucket in ('head','medium','tail')}
        return {'policy':update_key,'top1':agg('accuracy'),'ce':agg('ce'),'top2':agg('top2'),
            'mean_rank':agg('mean_teacher_rank'),'high_conf_wrong':agg('high_confidence_wrong'),
            'mean_wrong_confidence':statistics.mean(r['mean_wrong_confidence'] for r in selected),
            'fit_top1_mean':statistics.mean(fit_values),'generalization_gap_mean':statistics.mean(fit_values)-agg('accuracy')['mean'],
            'frequency_buckets':frequency}
    policies=[policy(x) for x in ('ce_selected','fixed200','fixed300','fixed500')]
    ce=policies[0];fixed=policies[-1];deltas=[ce['top1']['values'][str(s)]-fixed['top1']['values'][str(s)] for s in seeds]
    gate=config['primary_success_gate'];gate_result={
        'mean_top1_delta':statistics.mean(deltas),'bootstrap_ci95':bootstrap(deltas,config['bootstrap_seed']),
        'better':sum(x>0 for x in deltas),'equal':sum(x==0 for x in deltas),'worse':sum(x<0 for x in deltas),
        'non_materially_worse':sum(x*100>=-gate['per_seed_non_materially_worse_tolerance_pp'] for x in deltas),
        'ce_delta':ce['ce']['mean']-fixed['ce']['mean'],'rank_delta':ce['mean_rank']['mean']-fixed['mean_rank']['mean'],
        'high_conf_wrong_delta':ce['high_conf_wrong']['mean']-fixed['high_conf_wrong']['mean'],
        'selected_1000_count':sum(x['ce_selected_update']==1000 for x in choice_rows)}
    gate_result['passed']=bool(gate_result['mean_top1_delta']*100>=gate['ce_selected_mean_top1_delta_vs_fixed500_min_pp']
        and gate_result['non_materially_worse']>=gate['ce_selected_non_materially_worse_seed_count_min']
        and gate_result['ce_delta']<=gate['mean_validation_ce_delta_vs_fixed500_max']
        and gate_result['rank_delta']<=gate['mean_teacher_rank_delta_vs_fixed500_max']
        and gate_result['high_conf_wrong_delta']<=gate['mean_high_confidence_wrong_delta_vs_fixed500_max']
        and gate_result['selected_1000_count']<=gate['selected_at_1000_count_max'])
    updates=[x['ce_selected_update'] for x in choice_rows]
    stability={'mean':statistics.mean(updates),'median':statistics.median(updates),'std':statistics.stdev(updates),
        'min':min(updates),'max':max(updates),'within_300_600':sum(300<=x<=600 for x in updates),
        'ce_vs_top1_exact':sum(x['ce_selected_update']==x['top1_selected_update'] for x in choice_rows),
        'hindsight_exact':sum(x['ce_selected_update']==x['hindsight_best_update'] for x in choice_rows),
        'hindsight_within_100':sum(abs(x['ce_selected_update']-x['hindsight_best_update'])<=100 for x in choice_rows),
        'hindsight_within_200':sum(abs(x['ce_selected_update']-x['hindsight_best_update'])<=200 for x in choice_rows)}
    # Secondary split robustness: selection update distributions only plus selection-independent audit top1 delta.
    secondary=[]
    for spec in config['splits'][1:]:
        for seed in spec['training_seeds']:
            choice=lock['splits'][spec['name']]['choices'][str(seed)];sr=[r for r in rows if r['split']==spec['name'] and r['seed']==seed]
            chosen=next(r for r in sr if r['update']==choice['ce_selected_update']);fixed500=next(r for r in sr if r['update']==500)
            secondary.append({'split':spec['name'],'seed':seed,'selected_update':choice['ce_selected_update'],
                'val_top1_delta_vs_fixed500':chosen['metrics']['symbol']['accuracy']-fixed500['metrics']['symbol']['accuracy'],
                'val_ce_delta_vs_fixed500':chosen['metrics']['symbol']['ce']-fixed500['metrics']['symbol']['ce']})
    result={'version':'V148','choice_lock_sha256':digest(OUT/'checkpoint_choices.lock.json'),
        'choices':choice_rows,'policy_summary':policies,'regret':regret,'selection_stability':stability,
        'gate_vs_fixed500':gate_result,'secondary_split_robustness':secondary,'coverage':audit_data['coverage'],
        'online_smoke':'NOT APPLICABLE','test_access':'FORBIDDEN','development_validation_role':audit_data['validation_role']}
    write(OUT/'analysis.json',result)
    write_csv(OUT/'checkpoint_choices.csv',choice_rows);write_csv(OUT/'selection_regret.csv',regret)
    write_csv(OUT/'audit_metrics.csv',flat)
    selection_csv=[]
    for spec in config['splits']:
        for seed in spec['training_seeds']:
            run=read(OUT/'training_curves'/spec['name']/f'seed-{seed}.json')
            for x in run['checkpoints'].values():selection_csv.append({'split':spec['name'],'seed':seed,'update':x['update'],
                'selection_symbol_ce':x['selection']['symbol']['ce'],'selection_symbol_top1':x['selection']['symbol']['accuracy'],
                'fit_symbol_ce':x['fit']['symbol']['ce'],'fit_symbol_top1':x['fit']['symbol']['accuracy']})
    write_csv(OUT/'selection_metrics.csv',selection_csv)
    print(json.dumps({'primary_selected_updates':updates,'gate_passed':gate_result['passed'],
        'mean_delta_vs500':gate_result['mean_top1_delta'],'secondary_runs':len(secondary)}),flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['setup','train','lock','audit','analyze'])
    cmd=parser.parse_args().command
    {'setup':setup,'train':train,'lock':lock,'audit':audit,'analyze':analyze}[cmd]()
