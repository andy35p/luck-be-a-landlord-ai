"""One frozen development-selected checkpoint comparison on reserved seeds."""
import csv
import hashlib
import json
from pathlib import Path
import torch
from train_bc_smoke import online
from luck_agent.agents.candidate_model import CandidateModel,TorchScorer
from luck_agent.agents.candidate_agent import CandidateAgent
from luck_agent.evaluation.compare_reroll import paired_stats


def main():
    config_path=Path('configs/bc_frozen_validation_v1.json')
    cfg=json.loads(config_path.read_text());output=Path(cfg['output']);output.mkdir()
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    result={};episodes={}
    for role in ('baseline','candidate'):
        path=Path(cfg[role]['checkpoint'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=cfg[role]['sha256']:raise ValueError('Checkpoint changed')
        saved=torch.load(path,weights_only=True);spec={**saved['spec'],'online_seed_start':cfg['seed_start'],'online_games':cfg['games']}
        model=CandidateModel();model.load_state_dict(saved['state_dict'])
        agent=CandidateAgent(TorchScorer(model),rule_version='instance-coal-v1',scaler=saved['scaler'],index_path=spec['index'],policies=[spec['teacher']])
        rows,summary=online(agent,spec);episodes[role]=rows;result[role]=summary
        with (output/(role+'.csv')).open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        print(json.dumps({role:summary}),flush=True)
    stats=paired_stats([{**r,'rerolls_used':0} for r in episodes['baseline']], [{**r,'rerolls_used':0} for r in episodes['candidate']],cfg['bootstrap_seed'],cfg['bootstrap_samples'])
    for r in stats['worst_pairs']:r.pop('rerolls_used')
    report={'config':cfg,'summaries':result,'paired':stats,'training_updates':0,
        'passes_primary_gate':stats['paired_bootstrap_interval'][0]>0 and all(r['truncations']==0 for r in result.values()),
        'scope':'fixed checkpoints, held-out environment seeds, restricted simulator; not multi-initialization validation'}
    (output/'results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'paired':stats,'passes_primary_gate':report['passes_primary_gate']},indent=2))


if __name__=='__main__':main()
