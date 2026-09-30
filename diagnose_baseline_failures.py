"""Public-trace audit; no rollout intervention or policy changes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from luck_agent.agents.heuristic_agent import CoalScoreHeuristic
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.trajectory import replay


def episode_summary(episode, catalog):
    scorer=CoalScoreHeuristic(0)
    decisions=[];spins=[];rents=[];events=Counter()
    for record in episode:
        state=record['state'];after=record['next_state'];action=record['action']
        for event in record['info'].get('instance_events',[]):
            events[event.get('reason',event['type'])]+=1
        if after['spin_count']>state['spin_count']:
            spins.append({'spin':after['spin_count'],'income':after['last_spin_income'],
                          'coins_after':after['coins'],'stage_after':after['rent_stage']})
            if state['spins_until_rent']==1:
                available=state['coins']+after['last_spin_income']
                rents.append({'rent_number':state['rent_stage']+1,'rent':state['current_rent'],
                              'available':available,'margin':available-state['current_rent'],
                              'passed':after['rent_stage']>state['rent_stage']})
        if action['action_type'] in (0,1):
            view=SimpleNamespace(catalog=catalog,deck=[s['symbol_id'] for s in state['symbols']],
                                 items=state['items'],coins=state['coins'],
                                 force_add_next_choice=state['forced_choice'],
                                 state=lambda:{'rent':state['current_rent']})
            scores=[{'symbol':c,'score':scorer.score_symbol(view,c),
                     'base_value':catalog['symbol_values'][c]} for c in state['candidates']]
            decisions.append({'step':record['step'],'spin':state['spin_count'],
                              'selected':action['target_id'] if action['action_type']==0 else 'skip',
                              'scores':scores,'coal_in_deck':view.deck.count('coal')})
    final=episode[-1]['next_state']
    return {'seed':episode[0]['episode_seed'],'final_stage':final['rent_stage'],
            'spins':spins,'rents':rents,'symbol_decisions':decisions,'events':dict(events),
            'action_counts':dict(Counter(str(r['action']['action_type']) for r in episode)),
            'remaining_coal':[s for s in final['symbols'] if s['symbol_id']=='coal']}


def first_divergence(left,right):
    for a,b in zip(left,right):
        if a['state'] != b['state'] or a['legal_actions'] != b['legal_actions']:
            return {'step':a['step'],'same_state':False}
        if a['action'] != b['action']:
            return {'step':a['step'],'same_state':True,'candidates':a['state']['candidates'],
                    'random_action':a['action'],'heuristic_action':b['action']}
    return None


def audit(directory):
    paths={name:Path(directory)/(name+'.jsonl.gz') for name in ('random','heuristic')}
    episodes={};checks={};catalog=None
    for name,path in paths.items():
        checks[name]=replay(path)
        episodes[name]={}
        for header,episode in read_episodes(path):
            if header['config']['rule_version']!='instance-goldfish-v1':
                raise ValueError('This diagnostic is scoped to the goldfish baseline')
            catalog=GameEnv(EnvConfig(**header['config'])).catalog
            episodes[name][episode[0]['episode_seed']]=episode
    if episodes['random'].keys()!=episodes['heuristic'].keys():
        raise ValueError('Paired seeds differ')
    pairs=[]
    for seed in episodes['heuristic']:
        left=episodes['random'][seed];right=episodes['heuristic'][seed]
        pairs.append({'seed':seed,'first_divergence':first_divergence(left,right),
                      'random':episode_summary(left,catalog),'heuristic':episode_summary(right,catalog)})
    return {'sources':{k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in paths.items()},
            'replay':checks,'pairs':pairs,'training_steps':0,
            'scope':'Five selected worst development pairs; descriptive scoring audit, not causal attribution.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',default='logs/baseline-failures-v057')
    parser.add_argument('--output',required=True);args=parser.parse_args()
    result=audit(args.directory)
    with Path(args.output).open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    for p in result['pairs']:
        h=p['heuristic']
        print(json.dumps({'seed':p['seed'],'stage':h['final_stage'],'coal_picks':sum(d['selected']=='coal' for d in h['symbol_decisions']),
                          'last_rent':h['rents'][-1],'events':h['events'],'first_divergence':p['first_divergence']}))
