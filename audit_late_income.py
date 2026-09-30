"""Stratified descriptive income attribution; no policy interventions."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from random import Random
from compare_baselines import load_run
from luck_agent.env.game_env import EnvConfig
from luck_agent.evaluation.evaluator import evaluate
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.trajectory import TrajectoryWriter, replay


def spin_accounting(record, coal_ids=frozenset()):
    state=record['next_state']
    board={s['instance_id']:s for s in state['visible_board_instances']}
    incomes=Counter();events=record['info'].get('instance_events',[]);coal_diamond_income=0
    for e in events:
        if e['type']=='payout':
            symbol=board[e['instance_id']]['symbol_id']
            incomes[symbol]+=e['amount']
            if symbol=='diamond' and e['instance_id'] in coal_ids:
                coal_diamond_income+=e['amount']
    if abs(sum(incomes.values())-state['last_spin_income'])>1e-9:
        raise ValueError('Payout attribution does not reconcile with spin income')
    diamonds=sum(s['symbol_id']=='diamond' for s in board.values())
    before=record['state']
    return {'spin':state['spin_count'],'stage_before':before['rent_stage'],
            'income':state['last_spin_income'],'income_by_symbol':dict(incomes),
            'diamond_synergy':diamonds*max(0,diamonds-1),
            'coal_derived_diamond_income':coal_diamond_income,
            'matured':sum(e.get('reason')=='coal_matured' for e in events),
            'rent_margin':before['coins']+state['last_spin_income']-before['current_rent']
                if before['spins_until_rent']==1 else None}


def summarize_spins(spins):
    income=sum(s['income'] for s in spins)
    diamond=sum(s['income_by_symbol'].get('diamond',0) for s in spins)
    return {'spins':len(spins),'total_income':income,'diamond_income':diamond,
            'diamond_income_share':diamond/income if income else 0,
            'diamond_synergy':sum(s['diamond_synergy'] for s in spins),
            'coal_derived_diamond_income':sum(s['coal_derived_diamond_income'] for s in spins),
            'coal_matured':sum(s['matured'] for s in spins)}


def episode_spins(episode):
    coal_ids=set();spins=[]
    for record in episode:
        if record['next_state']['spin_count']<=record['state']['spin_count']:continue
        spins.append(spin_accounting(record,coal_ids))
        coal_ids.update(e['instance_id'] for e in record['info'].get('instance_events',[])
                        if e.get('reason')=='coal_matured')
    return spins


def main():
    source_paths={'baseline':Path('logs/reused/heuristic-20260923T152721958253Z'),
                  'candidate':Path('logs/goldfish-coal-v059')}
    data={k:load_run(p)[1] for k,p in source_paths.items()}
    groups={};lookup={k:{r['seed']:r for r in rows} for k,rows in data.items()}
    for a,b in zip(data['baseline'],data['candidate']):
        assert a['seed']==b['seed']
        groups.setdefault(f"{a['won']}{b['won']}",[]).append(a['seed'])
    rng=Random(60)
    selected={group:sorted(rng.sample(seeds,min(5,len(seeds)))) for group,seeds in sorted(groups.items())}
    out=Path('logs/late-income-v060');out.mkdir(exist_ok=False)
    selection={'group_meaning':'baseline_win,candidate_win','group_sizes':{k:len(v) for k,v in groups.items()},
               'sampling_seed':60,'selected':selected,'selection':'five seeds per outcome stratum; not population weighted',
               'sources':{k:{'path':str(p),'episodes_sha256':hashlib.sha256((p/'episodes.csv').read_bytes()).hexdigest()} for k,p in source_paths.items()}}
    (out/'selection.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
    all_seeds=sorted(s for seeds in selected.values() for s in seeds)
    cfg=EnvConfig(floor=1,rule_version='instance-goldfish-v1');checks={};analysis={}
    for role,adjustment in [('baseline',0),('candidate',-1.2)]:
        path=out/(role+'.jsonl.gz')
        with TrajectoryWriter(path,cfg,'heuristic',policy_config={'coal_score_adjustment':adjustment}) as sink:
            for seed in all_seeds:
                rows,_=evaluate(1,'heuristic',seed,cfg,coal_score_adjustment=adjustment,transition_sink=sink)
                if rows[0]!=lookup[role][seed]: raise ValueError('Source episode did not reproduce')
        checks[role]=replay(path);analysis[role]={}
        for _,episode in read_episodes(path):
            spins=episode_spins(episode)
            analysis[role][episode[0]['episode_seed']]=spins
    pairs=[]
    for group,seeds in selected.items():
        for seed in seeds:
            a=analysis['baseline'][seed];b=analysis['candidate'][seed];horizon=min(len(a),len(b))
            pairs.append({'group':group,'seed':seed,'common_spin_horizon':horizon,
                          'baseline_common':summarize_spins(a[:horizon]),'candidate_common':summarize_spins(b[:horizon]),
                          'baseline_full':summarize_spins(a),'candidate_full':summarize_spins(b),
                          'baseline_timeline':a,'candidate_timeline':b})
    report={'selection':selection,'replay':checks,'pairs':pairs,'training_steps':0,
            'limitations':'Outcome-conditioned small sample, descriptive accounting; common horizon does not imply common RNG path.'}
    with Path('reports/v060_late_income.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    for group in selected:
        ps=[p for p in pairs if p['group']==group]
        print(json.dumps({'group':group,'seeds':selected[group],
            'baseline_common_matured':sum(p['baseline_common']['coal_matured'] for p in ps),
            'candidate_common_matured':sum(p['candidate_common']['coal_matured'] for p in ps),
            'baseline_common_diamond_income':sum(p['baseline_common']['diamond_income'] for p in ps),
            'candidate_common_diamond_income':sum(p['candidate_common']['diamond_income'] for p in ps)}))


if __name__=='__main__':main()
