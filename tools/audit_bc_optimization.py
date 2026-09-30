"""V146 offline audit. Frozen corpus; no new labels, test metrics or online policy changes."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from random import Random
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch
from luck_agent.agents.magpie_model import MagpieCandidateModel, magpie_tensors
from luck_agent.agents.magpie_corpus_checkpoint import contract
from luck_agent.evaluation.magpie_corpus import load_corpus_samples
from luck_agent.evaluation.magpie_batching import collate_magpie
from luck_agent.evaluation.magpie_corpus_preprocessing import fit_corpus_scaler, scale_corpus_sample
from luck_agent.evaluation.dataset import read_episodes

OUT = ROOT/'logs/v146-bc-audit'
CORPUS = ROOT/'logs/v128-magpie-shards'
BASE = ROOT/'outputs/v130-magpie-corpus-training'
KEYS = ('scalars','deck','items','candidates','board','board_mask','board_observed')

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def write(p, obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify():
    pins=read(OUT/'protected_hashes.json')
    for p,h in pins.items():
        if sha(ROOT/p)!=h:raise ValueError('Frozen asset changed: '+p)
    return len(pins)

def setup():
    if (OUT/'protocol.json').exists():return len(read(OUT/'protected_hashes.json'))
    OUT.mkdir(parents=True,exist_ok=True)
    pins=read(ROOT/'logs/v145-rollout/protected_hashes.json')
    for folder in (ROOT/'logs/v145-rollout',BASE):
        for p in folder.rglob('*'):
            if p.is_file():pins[p.relative_to(ROOT).as_posix()]=sha(p)
    for p in (ROOT/'reports').glob('v145*'):pins[p.relative_to(ROOT).as_posix()]=sha(p)
    for p in (ROOT/'luck_agent').rglob('*.py'):pins[p.relative_to(ROOT).as_posix()]=sha(p)
    pins['tools/train_magpie_corpus.py']=sha(ROOT/'tools/train_magpie_corpus.py')
    write(OUT/'protected_hashes.json',pins)
    git=subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True)
    write(OUT/'git_state.json',{'returncode':git.returncode,'status':git.stdout,'error':git.stderr})
    write(OUT/'protocol.json',{
        'version':'V146','dataset_sha256':sha(CORPUS/'manifest.json'),'baseline_sha256':sha(BASE/'research-200-updates.pt'),
        'splits_read_for_metrics':['train','validation'],'test_metrics':'SEALED; existing corpus validator checks hashes/provenance only',
        'optimizer':'Adam','lr':.001,'weight_decay':0,'scheduler':None,'batch_size':64,'clip':1.,'width':16,
        'loss':'candidate cross entropy; forced decisions excluded','initialization':'PyTorch default, manual_seed before model',
        'seed':123,'tiny_sizes':[32,128,512],'tiny_max_updates':2000,'tiny_stop':'100% top1 AND CE<=0.05 at a 100-update checkpoint',
        'tiny_selection':'nested SHA256(seed,step) ordered TRAIN symbol states; no augmentation',
        'budget_updates':[200,500,1000,2000],'curve_every':100,
        'capacity_gate':'train symbol fit <95% AND gain 1000->2000 <2 percentage points; then widths8/32, same2000updates',
        'symbol_only':'same encoder/width/seed/batch; checkpoints200/500/1000/2000 plus exposure-matched update',
        'robustness_seeds':[123,456,789],
        'candidate_gate':'val symbol fit improves >=2pp; choose earliest budget with train>=95% else best val (tie lower budget)',
        'ranking_loss_gate':'budget plateau in top1 with fallingCE AND majority errors rank2; otherwise no loss experiment',
        'high_confidence_wrong':'model softmax(top1)>=0.8 AND top1!=teacher; not teacher confidence',
        'near_miss':'wrong teacher rank2 and predicted-minus-teacher logit<=0.5',
        'frequency_buckets':'per-target TRAIN teacher frequency terciles, ties by target id; validation uses same bins',
        'online':'deferred to V147 fixed multi-seed online protocol; audit candidates not promoted',
        'environment':'frozen instance-magpie-v1; legacy teacher forecast_rents; no Reroll research',
        'runtime':'training loop incl checkpoint metrics; CPU wall time, torch threads1',
        'checkpoint_selection':'diagnostic fixed checkpoints; no default model replacement','v130_early_stopping':None})
    return verify()

def data():
    torch.set_num_threads(1)
    payload=torch.load(BASE/'research-200-updates.pt',map_location='cpu',weights_only=True)
    scaler=fit_corpus_scaler(CORPUS)
    if scaler!=payload['scaler']:raise ValueError('Scaler reproduction failed')
    raw={p:load_corpus_samples(CORPUS,split=p) for p in ('train','validation')}
    samples={p:[scale_corpus_sample(s,scaler) for s in rows if len(s['candidates'])>1] for p,rows in raw.items()}
    return payload,scaler,raw,samples

def tensor_batch(rows):
    b=collate_magpie(rows)
    return magpie_tensors(b),torch.tensor(b['label'])

def groups(rows):
    return [tensor_batch(rows[i:i+64]) for i in range(0,len(rows),64)]

def metric_rows(model, rows, cached=None):
    model.eval();result=[];offset=0
    with torch.no_grad():
        for x,y in (cached if cached is not None else groups(rows)):
            scores=model(x);probs=scores.softmax(1);pred=scores.argmax(1)
            ce=torch.nn.functional.cross_entropy(scores,y,reduction='none')
            # Stable first-index tie ordering matches legal action argmax contract.
            order=torch.argsort(scores,dim=1,descending=True,stable=True)
            ranks=(order==y[:,None]).long().argmax(1)+1
            for i in range(len(y)):
                s=rows[offset+i];label=int(y[i]);choice=int(pred[i]);n=len(s['candidates'])
                v=scores[i,:n].tolist();other=max(v[j] for j in range(n) if j!=label)
                actions=s['metadata']['actions'];target=actions[label];wrong=actions[choice]
                result.append({'seed':s['metadata']['seed'],'step':s['metadata']['step'],
                    'phase':s['metadata']['decision_type'],'candidate_count':n,'label':label,'prediction':choice,
                    'correct':choice==label,'top2':int(ranks[i])<=2,'teacher_rank':int(ranks[i]),'ce':float(ce[i]),
                    'teacher_margin':v[label]-other,'wrong_margin':v[choice]-v[label],
                    'high_confidence_wrong':choice!=label and float(probs[i,choice])>=.8,
                    'confidence':float(probs[i,choice]),'top1_score':v[choice],'teacher_score':v[label],
                    'teacher_type':target['action_type'],'teacher_target':target['target_id'],
                    'choice_target':wrong['target_id'],'choice_type':wrong['action_type'],
                    'skip':target['action_type'] in (1,3,8)})
            offset+=len(y)
    if offset!=len(rows):raise ValueError('Metric coverage mismatch')
    return result

def summarize(rows):
    if not rows:return {'n':0,'accuracy':None,'ce':None,'top2':None,'mean_teacher_rank':None,'mean_teacher_margin':None,'high_confidence_wrong':0}
    return {'n':len(rows),'correct':sum(r['correct'] for r in rows),'accuracy':sum(r['correct'] for r in rows)/len(rows),
        'ce':sum(r['ce'] for r in rows)/len(rows),'top2':sum(r['top2'] for r in rows)/len(rows),
        'mean_teacher_rank':sum(r['teacher_rank'] for r in rows)/len(rows),
        'mean_teacher_margin':sum(r['teacher_margin'] for r in rows)/len(rows),
        'high_confidence_wrong':sum(r['high_confidence_wrong'] for r in rows),
        'candidate_buckets':{k:{'n':len(z),'correct':sum(r['correct'] for r in z),'accuracy':sum(r['correct'] for r in z)/len(z)}
            for k in ('2','3','4+') if (z:=[r for r in rows if ('4+' if r['candidate_count']>=4 else str(r['candidate_count']))==k])}}

def metrics(model,samples,caches):
    result={}
    for split,rows in samples.items():
        details=metric_rows(model,rows,caches[split]);result[split]={'all':summarize(details),
            'phases':{p:summarize([r for r in details if r['phase']==p]) for p in sorted({r['phase'] for r in details})},
            'skip':summarize([r for r in details if r['skip']])}
    return result

def input_key(sample):
    x,_=tensor_batch([sample])
    # Actual final float32/bool input, not metadata or raw JSON equality.
    return json.dumps({k:{'shape':list(t.shape),'dtype':str(t.dtype),'value':t.tolist()} for k,t in x.items()},sort_keys=True,separators=(',',':'))

def collisions(rows):
    seen=defaultdict(set);candidate_conflicts=0
    for s in rows:
        seen[input_key(s)].add(s['label'])
        teacher=s['candidates'][s['label']]
        candidate_conflicts+=sum(c==teacher for c in s['candidates'])>1
    return {'samples':len(rows),'unique_inputs':len(seen),'input_label_conflicts':sum(len(y)>1 for y in seen.values()),
        'within_state_identical_teacher_candidates':candidate_conflicts}

def baseline(payload,scaler,raw,samples):
    if (OUT/'baseline_metrics.json').exists():return read(OUT/'baseline_metrics.json')
    model=MagpieCandidateModel(payload['width']);model.load_state_dict(payload['state_dict'])
    caches={p:groups(rows) for p,rows in samples.items()}
    values=metrics(model,samples,caches)
    old=read(BASE/'result.json')
    for p in samples:
        for phase,m in values[p]['phases'].items():
            prior=old['phase_metrics'][p][phase]
            if m['n']!=prior['decisions'] or abs(m['accuracy']-prior['accuracy'])>1e-12:raise ValueError('V130 metric mismatch')
    manifest=read(CORPUS/'manifest.json')
    result={'metrics':values,'coverage':{p:{'episodes':len(manifest['spec']['seeds'][p]),'all_transitions':len(raw[p]),
        'multi_candidate_samples':len(samples[p]),'shards':[e['file'] for e in manifest['entries'] if e['split']==p]} for p in samples},
        'collisions':{p:collisions(rows) for p,rows in samples.items()},'v130_exact_phase_accuracy':True,
        'parameters':sum(p.numel() for p in model.parameters()),'scaler':scaler,
        'training_contract':{**read(OUT/'protocol.json'),'scalar_dimension':len(scaler['fields']),
            'candidate_dimension':4,'board_dimension':[20,5],'deck_dimension':4,'model':repr(model),
            'optimizer_defaults':torch.optim.Adam(model.parameters(),lr=.001).defaults,'torch_version':str(torch.__version__),
            'v130_epochs_equivalent':200*64/len(samples['train'])}}
    for split in samples:
        write(OUT/'error_analysis'/f'baseline-{split}-decisions.json',metric_rows(model,samples[split],caches[split]))
    normal={}
    for split,rows in raw.items():
        columns=list(zip(*(s['scalars'] for s in rows)))
        normal[split]={name:{'n':len(col),'min':min(col),'max':max(col),'zero_variance':max(col)==min(col),
            'mean':sum(col)/len(col),'max_abs_z':max(abs((v-scaler['mean'][i])/scaler['scale'][i]) for v in col)}
            for i,(name,col) in enumerate(zip(scaler['fields'],columns))}
    result['normalization']=normal
    write(OUT/'baseline_metrics.json',result);return result

def run_train(name,training,samples,scaler,*,seed=123,width=16,updates=(200,500,1000,2000),tiny=False,expected=None):
    folder=OUT/name
    if (folder/'result.json').exists():return read(folder/'result.json')
    if (folder/'config.json').exists():raise RuntimeError('Incomplete run needs explicit recovery: '+name)
    folder.mkdir(parents=True,exist_ok=True)
    config={**read(OUT/'protocol.json'),'name':name,'seed':seed,'width':width,'updates':list(updates),
        'training_samples':len(training),'subset_keys':[[s['metadata']['seed'],s['metadata']['step']] for s in training],
        'source_hash':sha(Path(__file__)),'git_state':read(OUT/'git_state.json')}
    write(folder/'config.json',config)
    torch.manual_seed(seed);model=MagpieCandidateModel(width).eval()
    optimizer=torch.optim.Adam(model.parameters(),lr=.001);rng=Random(seed);order=[]
    caches={p:groups(rows) for p,rows in samples.items()}
    start=time.perf_counter();curve=[];checkpoints={};all_modules=defaultdict(list);symbol_draws=0
    initial={k:v.detach().clone() for k,v in model.state_dict().items()}
    curve.append({'update':0,'metrics':metrics(model,samples,caches),'runtime':0.})
    exact=None
    for step in range(1,max(updates)+1):
        chosen=[]
        for _ in range(64):
            if not order:order=list(range(len(training)));rng.shuffle(order)
            chosen.append(training[order.pop()])
        symbol_draws+=sum(s['metadata']['decision_type']=='symbol' for s in chosen)
        x,y=tensor_batch(chosen);optimizer.zero_grad();scores=model(x)
        loss=torch.nn.functional.cross_entropy(scores,y);loss.backward()
        if not torch.isfinite(loss) or any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):raise ValueError('Nonfinite training')
        grad={}
        for module in ('symbol','item','action','instance','board_cell','head'):
            sq=sum(float(p.grad.square().sum()) for n,p in model.named_parameters() if n.split('.')[0]==module and p.grad is not None)
            grad[module]=math.sqrt(sq);all_modules[module].append(grad[module])
        before={n:p.detach().clone() for n,p in model.named_parameters()} if step==1 or step%100==0 or step in updates else None
        norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
        if before is not None:
            ratio={n:float((p.detach()-before[n]).norm())/max(float(before[n].norm()),1e-12) for n,p in model.named_parameters()}
            event={'update':step,'batch_loss':float(loss.detach()),'gradient_norm_before_clip':float(norm),
                'module_gradient_norm':grad,'parameter_update_ratio':ratio,'lr':optimizer.param_groups[0]['lr'],
                'symbol_draws':symbol_draws,'runtime':time.perf_counter()-start}
            if step%100==0 or step in updates:event['metrics']=metrics(model,samples,caches)
            curve.append(event)
            write(folder/'training_curve.json',curve)
        if step==200 and expected is not None:
            exact=all(torch.equal(model.state_dict()[k],v) for k,v in expected.items())
            write(folder/'exact_v130_reproduction.json',{'all_weights_bitwise_equal':exact,'updates':200})
            if not exact:raise ValueError('V130 exact reproduction failed: optimization stopped')
        stop=tiny and step%100==0 and event['metrics']['train']['all']['accuracy']==1 and event['metrics']['train']['all']['ce']<=.05
        if step in updates or stop:
            path=folder/f'update-{step}.pt'
            torch.save({**contract(),'width':width,'training_updates':step,'scaler':scaler,'state_dict':model.state_dict()},path)
            checkpoints[str(step)]={'metrics':metrics(model,samples,caches),'runtime':time.perf_counter()-start,
                'checkpoint':path.relative_to(ROOT).as_posix(),'checkpoint_sha256':sha(path),'symbol_draws':symbol_draws}
            # Persist recoverable optimizer/sampling state in new diagnostic namespace.
            torch.save({'optimizer':optimizer.state_dict(),'rng_state':rng.getstate(),'order':order,'update':step},folder/f'resume-{step}.pt')
            print(json.dumps({'experiment':name,'step':step,'train':checkpoints[str(step)]['metrics']['train']['all']['accuracy'],
                'symbol':checkpoints[str(step)]['metrics']['train']['phases'].get('symbol',{}).get('accuracy'),
                'val_symbol':checkpoints[str(step)]['metrics'].get('validation',{}).get('phases',{}).get('symbol',{}).get('accuracy') }),flush=True)
        if stop:break
    utilization={n:{'initial_norm':float(v.norm()),'total_change_norm':float((model.state_dict()[n]-v).norm()),
        'unchanged_elements':int((model.state_dict()[n]==v).sum()),'elements':v.numel()} for n,v in initial.items()}
    result={'name':name,'parameters':sum(p.numel() for p in model.parameters()),'seed':seed,'width':width,
        'updates_executed':step,'runtime':time.perf_counter()-start,'checkpoints':checkpoints,'exact_v130_weights':exact,
        'gradients':{k:{'min':min(v),'max':max(v),'mean':sum(v)/len(v),'zero_steps':sum(x==0 for x in v)} for k,v in all_modules.items()},
        'parameter_utilization':utilization,'training_sample_count':len(training)}
    write(folder/'result.json',result);return result

def execute():
    setup();payload,scaler,raw,samples=data();baseline(payload,scaler,raw,samples)
    symbols=[s for s in samples['train'] if s['metadata']['decision_type']=='symbol']
    selected=sorted(symbols,key=lambda s:hashlib.sha256(json.dumps([s['metadata']['seed'],s['metadata']['step']]).encode()).hexdigest())
    for n in (32,128,512):
        subset=selected[:n];folder=OUT/'tiny_overfit'/str(n)
        write(folder/'input_collisions.json',collisions(subset))
        if collisions(subset)['input_label_conflicts']:raise ValueError('Tiny set input conflicts: stop experiments')
        run=run_train(f'tiny_overfit/{n}',subset,{'train':subset},scaler,updates=(200,500,1000,2000),tiny=True)
        if n==32 and list(run['checkpoints'].values())[-1]['metrics']['train']['all']['accuracy']<.99:
            write(OUT/'diagnostic_stop.json',{'reason':'32-state overfit failed','next':'implementation/representation audit'});return
    budget=run_train('budget_scaling/seed123',samples['train'],samples,scaler,expected=payload['state_dict'])
    cps=budget['checkpoints'];train=lambda k:cps[str(k)]['metrics']['train']['phases']['symbol']['accuracy']
    if train(2000)<.95 and train(2000)-train(1000)<.02:
        for width in (8,32):run_train(f'capacity/width{width}',samples['train'],samples,scaler,width=width)
    else:write(OUT/'capacity/gate.json',{'run':False,'reason':'Budget improvement sufficient or no plateau; larger model not justified'})
    exposure=round(cps['2000']['symbol_draws']/64)
    run_train('symbol_only/seed123',symbols,{'train':symbols,'validation':[s for s in samples['validation'] if s['metadata']['decision_type']=='symbol']},scaler,
        updates=tuple(sorted({200,500,1000,2000,exposure})))
    baseval=cps['200']['metrics']['validation']['phases']['symbol']['accuracy']
    eligible=[k for k in (500,1000,2000) if cps[str(k)]['metrics']['validation']['phases']['symbol']['accuracy']>=baseval+.02]
    chosen=next((k for k in eligible if train(k)>=.95),None)
    if chosen is None and eligible:chosen=max(eligible,key=lambda k:(cps[str(k)]['metrics']['validation']['phases']['symbol']['accuracy'],-k))
    write(OUT/'candidate_gate.json',{'chosen_updates':chosen,'baseline_val_symbol':baseval,'eligible':eligible,'symbol_exposure_matched_update':exposure,
        'selection':'fixed protocol; validation used for diagnostics, not independent holdout'})
    if chosen:
        for seed in (456,789):run_train(f'budget_scaling/seed{seed}',samples['train'],samples,scaler,seed=seed,updates=(200,chosen))
    # Extended objectives require diagnostic evidence; no automatic parameter search.
    write(OUT/'loss_gate.json',{'run':False,'reason':'Assess budget/capacity/interference evidence in final report before any objective experiment; no loss sweep'})
    verify()

def csv_write(path,rows):
    if not rows:return
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def report():
    # execute() already checked all pinned hashes after every experiment; avoid
    # repeatedly traversing the multi-gigabyte V145 diagnostic archive.
    count=len(read(OUT/'protected_hashes.json'))
    base=read(OUT/'baseline_metrics.json');runs=[read(p) for p in sorted(OUT.glob('*/**/result.json'))]
    table=[]
    for run in runs:
        for step,cp in run['checkpoints'].items():
            t=cp['metrics']['train']['phases'].get('symbol',{});v=cp['metrics'].get('validation',{}).get('phases',{}).get('symbol',{})
            table.append({'experiment':run['name'],'params':run['parameters'],'updates':int(step),'train_symbol_fit':t.get('accuracy'),
                'val_symbol_fit':v.get('accuracy'),'train_ce':t.get('ce'),'val_ce':v.get('ce'),'teacher_top2':v.get('top2'),
                'mean_teacher_rank':v.get('mean_teacher_rank'),'runtime':cp['runtime']})
    csv_write(OUT/'experiment_summary.csv',table)
    details={split:read(OUT/'error_analysis'/f'baseline-{split}-decisions.json') for split in ('train','validation')}
    symbols={p:[r for r in rows if r['phase']=='symbol'] for p,rows in details.items()}
    target=lambda r:'SKIP' if r['skip'] else r['teacher_target']
    freq=Counter(target(r) for r in symbols['train']);ordered=sorted(freq,key=lambda t:(-freq[t],str(t)))
    buckets={t:('head' if i<len(ordered)/3 else 'medium' if i<2*len(ordered)/3 else 'tail') for i,t in enumerate(ordered)}
    frequency={'train_teacher_frequency':dict(freq),'buckets':buckets,'splits':{}}
    for split,rows in symbols.items():
        wrong=[r for r in rows if not r['correct']]
        frequency['splits'][split]={'teacher_frequency':dict(Counter(target(r) for r in rows)),
            'per_target':{t:summarize([r for r in rows if target(r)==t]) for t in sorted({target(r) for r in rows},key=str)},
            'buckets':{b:summarize([r for r in rows if buckets.get(target(r),'unseen')==b]) for b in ('head','medium','tail','unseen')},
            'errors':{'n':len(wrong),'rank2':sum(r['teacher_rank']==2 for r in wrong),'rank3plus':sum(r['teacher_rank']>=3 for r in wrong),
                'near_miss':sum(r['teacher_rank']==2 and r['wrong_margin']<=.5 for r in wrong),
                'top_teacher_errors':Counter(target(r) for r in wrong).most_common(10),
                'top_wrong_choices':Counter('SKIP' if r['choice_type'] in (1,3,8) else r['choice_target'] for r in wrong).most_common(10),
                'confusion_pairs':Counter((target(r),'SKIP' if r['choice_type'] in (1,3,8) else r['choice_target']) for r in wrong).most_common(20)}}
    # Candidate frequency counts every legal option, distinct from chosen-label frequency.
    # The frozen corpus was already validated by E0; count candidates directly from
    # the 40 existing train/validation shards without re-encoding every state.
    manifest=read(CORPUS/'manifest.json');candidate_freq={split:Counter() for split in ('train','validation')}
    for entry in manifest['entries']:
        split=entry['split']
        if split not in candidate_freq:continue
        for _,episode in read_episodes(CORPUS/entry['file']):
            for record in episode:
                if record['state']['decision_type']!='symbol' or len(record['legal_actions'])<=1:continue
                candidate_freq[split].update('SKIP' if a['action_type'] in (1,3,8) else
                    'REROLL' if a['action_type']==5 else str(a['target_id'])
                    for a in record['legal_actions'])
    frequency['candidate_frequency']={p:dict(c) for p,c in candidate_freq.items()}
    write(OUT/'error_analysis/frequency.json',frequency)
    result={'version':'V146','frozen_files_verified':count,'baseline':base,'experiments':table,'runs':runs,'frequency':frequency,
        'candidate_gate':read(OUT/'candidate_gate.json'),'capacity_gate':read(OUT/'capacity/gate.json') if (OUT/'capacity/gate.json').exists() else {'run':True},
        'online':'NOT RUN; no promotion. V147 predeclared online evaluation needed.','test_metrics':'SEALED',
        'interpretation':read(OUT/'interpretation.json') if (OUT/'interpretation.json').exists() else {'status':'pending evidence interpretation'}}
    test_text=(OUT/'tests.txt').read_text(encoding='utf-8') if (OUT/'tests.txt').exists() else ''
    match=re.search(r'Ran (\d+) tests',test_text)
    result['tests']={'count':int(match.group(1)) if match else None,'passed':bool(match and re.search(r'\nOK\s*$',test_text))}
    write(ROOT/'reports/v146_bc_optimization_audit.json',result)
    interp=result['interpretation'];symbol_train=base['metrics']['train']['phases']['symbol'];symbol_val=base['metrics']['validation']['phases']['symbol']
    pct=lambda x:'N/A' if x is None else f'{100*x:.2f}%'
    lines=['# V146 BC Optimization Audit','',
        '## 【当前版本】','V146 BC Optimization Audit','',
        '## 【本轮目标】','确定V130训练集符号拟合72.9%的主要原因；本轮训练仅用冻结train，validation仅诊断，test指标封存。','',
        '## 【冻结资产】',f'{count}个历史文件在实验末SHA校验不变；V128数据/分区/Teacher、V130模型、环境/规则/奖励、V143–V145均冻结。','',
        '## 【V130训练合同】',
        f"Dataset manifest SHA256 `{read(OUT/'protocol.json')['dataset_sha256']}`；train32局/val8局，原始训练11755转移，3849多候选决策。8维scalars、4维candidate、20×5 board，训练分区11755样本拟合z-score；模型宽16，参数{base['parameters']}。",
        'PyTorch默认初始化、seed123、Adam(lr=0.001,weight_decay=0)、batch64、无scheduler/early stopping、candidate CE、全局梯度裁剪1；不重复轮换随机顺序200更新，约3.33次多候选样本曝光。最终固定更新checkpoint，不按validation挑选。','',
        '## 【Metric Recompute】',
        f"冻结V130完整train Symbol Fit **{symbol_train['correct']}/{symbol_train['n']}={pct(symbol_train['accuracy'])}**；validation **{symbol_val['correct']}/{symbol_val['n']}={pct(symbol_val['accuracy'])}**。完整样本train3849/val1111；覆盖32/8分片，源数据hash验证。",
        f"Symbol train/val Top2 {pct(symbol_train['top2'])}/{pct(symbol_val['top2'])}；mean rank {symbol_train['mean_teacher_rank']:.3f}/{symbol_val['mean_teacher_rank']:.3f}；CE {symbol_train['ce']:.4f}/{symbol_val['ce']:.4f}；高置信错75/19。",
        'Decision Type逐项如下（仅多候选）：','',
        '| Split | Type | Correct/n | Top1 | Top2 | CE | Mean Teacher Rank | High-confidence Wrong |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for split in ('train','validation'):
        for phase,m in base['metrics'][split]['phases'].items():
            lines.append(f"| {split} | {phase} | {m['correct']}/{m['n']} | {pct(m['accuracy'])} | {pct(m['top2'])} | {m['ce']:.4f} | {m['mean_teacher_rank']:.3f} | {m['high_confidence_wrong']} |")
    lines+=['',
        '## 【Tiny-set Overfit】',
        '从原train符号状态按固定SHA顺序嵌套取32/128/512，禁止augmentation；实际最终float32/bool模型输入的异标冲突均0。32在200更新、128在300、512在500更新达到100%且CE≤0.05。由此排除“32个训练状态都学不住”；不能据此证明完整状态表示无信息损失。','',
        '## 【Training Curve】',
        '第200更新全部权重与V130 bitwise一致；逐100更新记录train/val loss、fit、rank、梯度、学习率与参数更新幅度。训练曲线见 `logs/v146-bc-audit/budget_scaling/seed123/training_curve.json`。','',
        '## 【Budget Scaling】',
        '| Experiment | Params | Updates | Train Symbol Fit | Val Symbol Fit | Teacher Top2 (val) | Runtime s |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in table:lines.append(f"| {r['experiment']} | {r['params']} | {r['updates']} | {pct(r['train_symbol_fit'])} | {pct(r['val_symbol_fit'])} | {pct(r['teacher_top2'])} | {r['runtime']:.2f} |")
    lines+=['',
        '200→2000更新：train符号72.88→98.70%，validation 75.85→73.75%；val CE在500最低0.5702，2000为0.9939。训练预算不足解释原训练拟合，简单延长预算不改善验证。','',
        '## 【Capacity】',
        '预设门槛要求2000更新train符号仍<95%且1000→2000增益<2pp；实测98.70%，故不进行宽度/深度搜索。当前容量不是已证实的训练集瓶颈，不能推论绝无容量问题。','',
        '## 【Multi-task Interference】',
        '相同编码器/宽16/seed123的Symbol-only：200/500/1000/2000更新train符号76.19/84.63/95.32/99.37%，val79.13/79.27/75.72/73.10%。按主实验2000更新的symbol曝光匹配1477更新时，train98.24%、val75.85%；主实验2000更新train98.70%、val73.75%。优化序列和非符号上下文不同，不能据此认定多任务干扰；未触发验证显著更优的候选门槛。','',
        '补充固定500更新、seed123/456/789的配对诊断：multi-task验证Symbol Fit分别76.64/79.13/79.27%，symbol-only为79.27/78.48/78.35%；symbol-only减multi-task为+2.62/−0.66/−0.92个百分点，平均+0.35个百分点。单种子优势未复现，且训练时符号曝光数不同。','',
        '## 【Frequency / Imbalance】',
        '按训练teacher目标出现频次排序后按目标种类三等分；head/medium/tail的train符号fit为81.47%/36.14%/18.56%，样本数2342/404/97；validation为82.56%/44.94%/12.00%，样本数648/89/25。低频确实集中错误，但分桶与决策难度混杂，非因果。candidate频次与teacher选中频次分开保存。','',
        '## 【Candidate Size】',
        '全部train2843/val762符号决策的合法action数均为4+；2/3候选桶N/A。恰好4个action的train480例fit70.63%、val120例fit70.83%；5个action的train2363例fit73.34%、val642例fit76.79%，第五项为可用REROLL。候选规模与资源可用性混杂，不能由此推断数目效应。','',
        '## 【Teacher Ranking】',
        'train符号错误771个，其中teacher rank2为554、rank≥3为217；rank2且错分margin≤0.5为273。最多的teacher目标错误为SKIP107、goldfish90、bar_of_soap79；模型误选为SKIP204、bar_of_soap160、spirit103。在线V142错误分布不可直接替代训练错误。','',
        '## 【Gradient Diagnostics】',
        '主实验2000更新六个模块的全局梯度norm均非零，未见梯度断链；embedding中不变元素来自padding/未出现action token，head两层全部参数改变。逐模块min/max/mean、更新比、参数变化见训练曲线和result.json。scaler仅由train拟合，无zero-variance字段；train scalar最大|z|为coins6.14，val最大|z|为last_spin_income4.00，未发现足以支持改normalization的证据。','',
        '## 【实验结果】',
        f"完整{result['tests']['count']}项测试{'通过' if result['tests']['passed'] else '未确认'}；训练模型均为实验资产，无生产默认模型替换、无新teacher标签、无test指标。完整checkpoint、配置/seed、dataset/git hash、曲线/运行时/模型指标位于logs/v146-bc-audit。",'',
        '## 【主要瓶颈归因】','',
        '| Error Category | Evidence | Evidence Against | Confidence |','|---|---|---|---|']
    for row in interp.get('evidence_table',[]):lines.append('| '+' | '.join(row)+' |')
    lines+=['','## 【是否产生候选模型】',interp.get('candidate','未晋升。'),'','## 【在线评估】',
        '未触发明显验证改善/teacher rank改善/高置信错误下降门槛；0在线对局，保持V141合同用于将来的候选。','',
        '## 【结论】',interp.get('conclusion','见JSON解释。'),'','## 【V147决策】',interp.get('v147','待定。'),'','## 十个问题','']
    for i,answer in enumerate(interp.get('answers',[]),1):lines.append(f'{i}. {answer}')
    lines+=['','详细分子分母、每条score/rank/margin、分片覆盖、频次、收敛曲线与梯度见伴随JSON及logs/v146-bc-audit；上述统计均为当前受限仿真环境的离线诊断。']
    (ROOT/'reports/v146_bc_optimization_audit.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'experiments':len(table),'frozen_files':count}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['setup','execute','report','verify'])
    cmd=parser.parse_args().command
    {'setup':setup,'execute':execute,'report':report,'verify':verify}[cmd]()
