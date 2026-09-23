"""Frozen source-specific loss and exact encoded-input label ambiguity audit."""
import hashlib
import argparse
import json
from collections import Counter
from pathlib import Path
import torch
from luck_agent.agents.candidate_model import CandidateModel,tensor_batch
from luck_agent.evaluation.teacher_dataset import original_examples,load_teacher_examples,collate_supervision
from luck_agent.evaluation.preprocessing import scale_sample
from luck_agent.evaluation.bc_contract import masked_bc_metrics


def input_key(sample):
    # Same ordered input only: equal counts or phases alone are not equivalent states.
    return hashlib.sha256(json.dumps({k:sample[k] for k in ('scalars','deck','items','candidates')},sort_keys=True).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',default='logs/bc-aggregation-20260923T005313919123Z')
    parser.add_argument('--output',default='reports/v044_source_audit.json')
    args=parser.parse_args()
    torch.set_num_threads(1)
    cfg=json.loads(Path('configs/bc_aggregation_v1.json').read_text())
    scaler=json.loads(Path(cfg['scaler']).read_text())
    pools={'original':original_examples(cfg['index'],cfg['teacher']),
           'annotated':load_teacher_examples(cfg['annotated'],cfg['index'])}
    groups={};distribution={}
    for source,samples in pools.items():
        bins={}
        for s in samples:
            if len(s['candidates'])<=1:continue
            key=input_key(s);entry=groups.setdefault(key,{'labels':set(),'sources':set(),'rows':0})
            entry['labels'].add(s['label']);entry['sources'].add(source);entry['rows']+=1
            phase=s['metadata']['decision_type'];size=len(s['deck'])
            band='below18' if size<18 else '18-19' if size<20 else '20-21' if size<22 else '22plus'
            name=f'{phase}/{band}'
            row=bins.setdefault(name,Counter());row['rows']+=1
            action=s['candidates'][s['label']][0]-1;row[f'label_type_{action}']+=1
        distribution[source]=bins
    root=Path(args.run)
    scores={};hashes={}
    for role in ('baseline','candidate'):
        path=root/role/'final.pt';hashes[role]=hashlib.sha256(path.read_bytes()).hexdigest()
        saved=torch.load(path,weights_only=True);model=CandidateModel();model.load_state_dict(saved['state_dict']);model.eval()
        scores[role]={}
        for source,samples in pools.items():
            chosen=[s for s in samples if len(s['candidates'])>1];summary={}
            with torch.no_grad():
                for start in range(0,len(chosen),64):
                    part=chosen[start:start+64];batch=collate_supervision([scale_sample(s,scaler) for s in part])
                    logits=model(tensor_batch(batch)).tolist()
                    for s,row,label,mask in zip(part,logits,batch['label'],batch['candidates_mask']):
                        m=masked_bc_metrics([row],[label],[mask]);phase=s['metadata']['decision_type']
                        for name in ('all',phase):
                            target=summary.setdefault(name,dict(rows=0,correct=0,nll_sum=0.,teacher_pick_model_skip=0,teacher_skip_model_pick=0))
                            target['rows']+=1;target['correct']+=m['correct_count'];target['nll_sum']+=m['loss_sum']
                            predicted=max((i for i,v in enumerate(mask) if v),key=lambda i:row[i])
                            expected_type=s['candidates'][label][0]-1;predicted_type=s['candidates'][predicted][0]-1
                            target['teacher_pick_model_skip']+=expected_type==0 and predicted_type==1
                            target['teacher_skip_model_pick']+=expected_type==1 and predicted_type==0
            for row in summary.values():row['nll']=row['nll_sum']/row['rows'];row['accuracy']=row['correct']/row['rows']
            scores[role][source]=summary
        assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[role]
    report={'checkpoint_hashes':hashes,'source_distribution':distribution,'scores':scores,
        'encoded_inputs':{'unique':len(groups),'duplicate_groups':sum(g['rows']>1 for g in groups.values()),
            'cross_source_groups':sum(len(g['sources'])>1 for g in groups.values()),
            'conflicting_label_groups':sum(len(g['labels'])>1 for g in groups.values())},
        'training_updates':0,'scope':'training-source diagnosis; ordered full encoded inputs only, not model pooled representations'}
    with Path(args.output).open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({'encoded_inputs':report['encoded_inputs'],'scores':{role:{source:value['all'] for source,value in sources.items()} for role,sources in scores.items()}},indent=2))


if __name__=='__main__':main()
