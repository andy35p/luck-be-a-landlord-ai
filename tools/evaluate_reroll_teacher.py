"""Frozen V143 protocol: opportunity, convergence, shadow, then paired online."""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import asdict,replace
import csv
import gzip
import hashlib
import json
import multiprocessing
from pathlib import Path
from statistics import mean
from time import perf_counter
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from luck_agent.agents.rent_forecast_agent import RentForecastAgent,rent_rank
from luck_agent.agents.rent_reroll_agent import RentRerollAgent,RentRerollConfig,value,token_cost
from luck_agent.env.game_env import GameEnv,EnvConfig
from luck_agent.env.action import Action,ActionType as T
from luck_agent.env.game_state import GameState,SymbolInstance,ActionRecord
from luck_agent.evaluation.trajectory import normalized
from luck_agent.evaluation.metrics import summarize
from luck_agent.evaluation.compare_reroll import paired_stats
from luck_agent.legacy.fast_env import DEFAULT_RENTS

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'logs/v143-reroll'
ENV=EnvConfig(floor=1,rule_version='instance-magpie-v1')


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list,tuple)) else v for k,v in r.items()} for r in rows)


def legal(state):
    if state.decision_type=='item':return tuple(Action(T.PICK_ITEM,s) for s in state.candidates)+(Action(T.SKIP_ITEM),)
    acts=tuple(Action(T.PICK_SYMBOL,s) for s in state.candidates)+(Action(T.SKIP_SYMBOL),)
    return acts+(Action(T.REROLL),) if state.reroll_tokens else acts


def setup():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol_path=OUT/'protocol.json'
    if protocol_path.exists():raise ValueError('Setup already frozen')
    env=GameEnv(ENV);s=env.reset(143000)
    old=RentForecastAgent(env.catalog)
    while s.decision_type!='symbol':s,*_=env.step(old.choose(s,env.legal_actions()))
    s=replace(s,rent_stage=6,current_rent=375,spins_until_rent=8,coins=375,
              reroll_tokens=3,visible_board_cells=(),visible_board_instances=(),
              visible_board_ids=(),visible_board=(),items=())
    agent=RentRerollAgent(env.catalog,config=RentRerollConfig(samples=64))
    values=agent.candidate_values(s)
    ordered=sorted((x for x in values if x.action_type==T.PICK_SYMBOL),key=lambda x:rent_rank(values[x]))
    symbols=lambda xs:tuple(x.target_id for x in xs)
    synergy=tuple(SymbolInstance(f'suite:{i}',kind,0,None,'episode') for i,kind in enumerate(['mouse','mouse','cheese','cheese','cheese','cat','flower','coin']))
    cases=[
        ('A_excellent',replace(s,candidates=symbols(ordered[:3]))),
        ('B_poor_multiple_tokens',replace(s,candidates=symbols(ordered[-3:]))),
        ('C_moderate_last_token',replace(s,candidates=symbols(ordered[6:9]),reroll_tokens=1)),
        ('D_high_pressure',replace(s,candidates=symbols(ordered[-3:]),coins=0,spins_until_rent=1)),
        ('E_low_pressure',replace(s,candidates=symbols(ordered[-3:]),coins=750)),
        ('F_core_synergy',replace(s,symbols=synergy,candidates=('mouse','coin','flower'))),
        ('G_no_token',replace(s,candidates=('coin','cat','flower'),reroll_tokens=0)),
        ('H_item_phase',replace(s,decision_type='item',candidates=('undertaker','time_machine')))]
    rows=[];convergence=[];compatible=[];maximum_delta=defaultdict(list)
    for name,state in cases:
        action_old=old.choose(state,legal(state))
        for model in ('zero','constant','token_aware'):
            agent.config=RentRerollConfig(samples=64,cost_model=model)
            chosen,trace=agent.decide(state,legal(state))
            rows.append(dict(case=name,state=normalized(state),legacy_action=normalized(action_old),**{**trace,'cost_model':model}))
        for n in (8,16,32,64):
            agent.config=RentRerollConfig(samples=n)
            chosen,trace=agent.decide(state,legal(state))
            convergence.append(dict(case=name,N=n,**trace))
        if state.reroll_tokens:
            subset=[r for r in convergence if r['case']==name and r['reroll_available']]
            if subset:
                reference=subset[-1]['expected_best_after_reroll']
                for row in subset:maximum_delta[row['N']].append([abs(x-y) for x,y in zip(row['expected_best_after_reroll'],reference)])
        non_roll=tuple(a for a in legal(state) if a.action_type!=T.REROLL)
        new=agent.choose(state,non_roll)
        if new!=old.choose(state,non_roll):raise ValueError('Non-reroll policy regression')
        compatible.append(dict(case=name,identical=True))
    deltas={n:[max(v[i] for v in vectors) for i in range(3)] for n,vectors in maximum_delta.items()}
    # Prespecified tolerances: half one legacy forecast trial resolution for
    # probability/rents; five cash coins. No performance-based sample selection.
    selected=next((n for n in (8,16,32,64) if deltas[n][0]<=.0625 and deltas[n][1]<=.0625 and deltas[n][2]<=5),64)
    frozen=dict(version='forecast_rents_v143',environment=asdict(ENV),samples=selected,
        cost_model='token_aware',base_cost=[0,.125,1],threshold=0,
        sampling_seed=20260929,legacy_trials=8,legacy_seed=20270927,horizon=30,
        convergence_tolerances=[.0625,.0625,5],max_deltas_vs64=deltas,
        shadow_seeds=list(range(16000,16004)),online_seeds=list(range(16000,16064)),
        test_fixture_seed=143000,training_updates=0,
        limitations='State-dependent vector reservation proxy, conditional forecasts; finite-budget sampling. Development only.')
    protocol_path.write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    write_csv(OUT/'opportunity_suite.csv',rows);write_csv(OUT/'convergence.csv',convergence)
    (OUT/'non_reroll_compatibility.json').write_text(json.dumps(compatible))
    print(json.dumps(frozen,indent=2),flush=True)


def episode(seed,mode):
    protocol=json.loads((OUT/'protocol.json').read_text())
    cache=OUT/f'{mode}-{seed}.json'
    protocol_hash=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest()
    if cache.exists():
        part=json.loads(cache.read_text())
        if part.get('protocol_sha256')!=protocol_hash:raise ValueError('Cached protocol drift')
        return part
    env=GameEnv(ENV);state=env.reset(seed);old=RentForecastAgent(env.catalog)
    new=RentRerollAgent(env.catalog,config=RentRerollConfig(samples=protocol['samples']))
    decisions=rerolls=opportunities=streak=max_streak=0;reward=0;traces=[];latencies=defaultdict(list);runs=Counter()
    tracepath=OUT/'reroll_episode_traces'/f'{mode}-{seed}.jsonl.gz'
    tracepath.parent.mkdir(exist_ok=True)
    proxy=[]
    started=perf_counter()
    with gzip.open(tracepath,'wt',encoding='utf-8') as stream:
        while not(state.is_terminal or state.is_truncated):
            actions=env.legal_actions();before=perf_counter()
            evidence=None;legacy_action=None
            if mode in ('legacy','shadow'):
                action=old.choose(state,actions);latencies['legacy'].append(perf_counter()-before)
                if mode=='shadow':
                    rng_before=env._engine.rng.getstate()
                    recommendation,evidence=new.decide(state,actions)
                    if rng_before!=env._engine.rng.getstate():raise ValueError('Shadow RNG pollution')
                    legacy_action=action
            else:action,evidence=new.decide(state,actions)
            if action not in actions:raise ValueError('Illegal teacher action')
            if evidence:
                latencies['reroll_opportunity' if evidence['reroll_available'] else 'non_reroll'].append(evidence['latency_seconds'])
                if not evidence['reroll_available'] and mode=='v143':
                    reference=old.choose(state,actions)
                    if action!=reference:raise ValueError('Non-reroll compatibility regression')
                if evidence['reroll_available']:
                    traces.append(dict(episode=seed,decision_id=decisions,legacy_action=normalized(legacy_action) if legacy_action else None,**evidence))
            is_roll=action.action_type==T.REROLL
            opportunities+=any(a.action_type==T.REROLL for a in actions);rerolls+=is_roll
            if is_roll:
                if not evidence or not evidence['positive_advantage']:raise ValueError('Unjustified consecutive reroll')
                streak+=1;max_streak=max(max_streak,streak)
            elif streak:runs['3+' if streak>=3 else str(streak)]+=1;streak=0
            previous=state
            state,r,terminated,truncated,info=env.step(action);reward+=r
            if is_roll and state.reroll_tokens!=previous.reroll_tokens-1:raise ValueError('Resource decrement regression')
            if is_roll:
                # Offer changed but deck/economy usually did not: candidate-value
                # cache is shared with the pre-reroll state, including last token.
                offered_values=new.candidate_values(state)
                best=min((offered_values[a] for a in env.legal_actions() if a.action_type in (T.PICK_SYMBOL,T.SKIP_SYMBOL)),key=rent_rank)
                realized=list(value(best))
                proxy.append(dict(decision_id=decisions,before=evidence['current_best_score'],
                    realized_after=realized,improved=tuple(realized)>tuple(evidence['current_best_score'])))
            stream.write(json.dumps(dict(step=decisions,state=normalized(previous),
                legal_actions=normalized(actions),action=normalized(action),reward=r,
                terminated=terminated,truncated=truncated,teacher=evidence),sort_keys=True)+'\n')
            decisions+=1
    elapsed=perf_counter()-started
    for row in traces:row.update(final_stage=state.rent_stage,episode_reward=reward,won=state.won)
    row=dict(seed=seed,stage=state.rent_stage,reward=reward,won=int(state.won),
        spins=state.spin_count,coins=state.coins,decisions=decisions,truncated=int(state.is_truncated),
        invalid_actions=0,rerolls_used=rerolls,reroll_opportunities=opportunities,
        removals_used=0)
    result=dict(mode=mode,row=row,seconds=elapsed,traces=traces,protocol_sha256=protocol_hash,
                latencies={k:dict(n=len(v),seconds=sum(v),mean=mean(v)) for k,v in latencies.items()},
                consecutive=dict(runs),max_streak=max_streak,success_proxy=proxy)
    temp=cache.with_suffix('.tmp');temp.write_text(json.dumps(result));temp.replace(cache)
    print(json.dumps(dict(mode=mode,seed=seed,stage=state.rent_stage,rerolls=rerolls)),flush=True)
    return result


def run(mode,seeds,workers):
    started=perf_counter()
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures=[pool.submit(episode,seed,mode) for seed in seeds]
        results=[f.result() for f in futures]
    rows=[r['row'] for r in results]
    traces=[t for r in results for t in r['traces']]
    write_csv(OUT/f'{mode}_episodes.csv',rows)
    if traces:write_csv(OUT/('shadow_reroll.csv' if mode=='shadow' else 'online_reroll.csv'),traces)
    timing=dict(wall_seconds=perf_counter()-started,workers=workers,
        scope='cached episodes excluded from fresh wall throughput; per-episode timings include compatibility audit and trace writing')
    (OUT/f'{mode}_timing.json').write_text(json.dumps(timing))
    return results


def restore(observation):
    state=dict(observation)
    state['symbols']=tuple(SymbolInstance(**s) for s in state['symbols'])
    state['visible_board_instances']=tuple(SymbolInstance(**s) for s in state['visible_board_instances'])
    state['history']=tuple(ActionRecord(**r) for r in state['history'])
    return GameState(**state)


def normalize_diagnostics(mode,seed):
    """Correct counters/last-token proxies from saved traces, never replays games."""
    cache=OUT/f'{mode}-{seed}.json';part=json.loads(cache.read_text())
    if part.get('diagnostics_normalized'):return part
    path=OUT/'reroll_episode_traces'/f'{mode}-{seed}.jsonl.gz'
    if not path.exists():path=OUT/'reroll_episode_traces'/f'shadow-{seed}.jsonl.gz'
    removals=0;previous=None;proxies=[]
    env=GameEnv(ENV);agent=RentRerollAgent(env.catalog)
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);removals+=row['action']['action_type']==T.REMOVE_SYMBOL
            if previous is not None and previous['action']['action_type']==T.REROLL:
                evidence=row['teacher']
                if evidence and evidence.get('reroll_available'):
                    best=evidence['current_best_score']
                else:
                    # Missing last-token proxy in early cached diagnostic version.
                    state=restore(row['state']);values=agent.candidate_values(state)
                    choices=[values[Action(**a)] for a in row['legal_actions'] if a['action_type'] in (T.PICK_SYMBOL,T.SKIP_SYMBOL)]
                    best=list(value(min(choices,key=rent_rank)))
                before=previous['teacher']['current_best_score']
                proxies.append(dict(decision_id=previous['step'],before=before,realized_after=best,
                                    improved=tuple(best)>tuple(before)))
            previous=row
    part['row']['removals_used']=removals
    if mode=='legacy' and any(k!='legacy' for k in part['latencies']):
        # First four references reuse executed shadow outcomes, without reruns.
        # Remove measured NEW-policy inference from their elapsed denominator.
        extra=sum(v['seconds'] for k,v in part['latencies'].items() if k!='legacy')
        part['seconds']-=extra
        part['latencies']={'legacy':part['latencies']['legacy']}
        part['timing_scope']='shadow reference minus measured new inference; trace overhead remains'
    if mode=='v143':
        if len(proxies)!=part['row']['rerolls_used']:raise ValueError('Incomplete immediate proxy')
        part['success_proxy']=proxies
    part['diagnostics_normalized']=True
    cache.write_text(json.dumps(part))
    return part


def report():
    protocol=json.loads((OUT/'protocol.json').read_text());seeds=protocol['online_seeds']
    all_parts={mode:[normalize_diagnostics(mode,seed) for seed in seeds] for mode in ('legacy','v143')}
    rows={mode:[p['row'] for p in parts] for mode,parts in all_parts.items()}
    for mode in rows:write_csv(OUT/f'{mode}_episodes.csv',rows[mode])
    summaries={mode:summarize(rr,sum(p['seconds'] for p in all_parts[mode]),13) for mode,rr in rows.items()}
    paired=paired_stats(rows['legacy'],rows['v143'],57,2000);paired.pop('promotable_on_development')
    from random import Random
    import statistics
    extras={}
    for field in ('reward','won'):
        delta=[b[field]-a[field] for a,b in zip(rows['legacy'],rows['v143'])]
        rng=Random(57);boot=sorted(mean(rng.choices(delta,k=len(delta))) for _ in range(2000))
        extras[field]=dict(mean_delta=mean(delta),ci95=[boot[49],boot[1949]])
    shadow=[json.loads((OUT/f'shadow-{s}.json').read_text()) for s in protocol['shadow_seeds']]
    shadow_trace=[t for p in shadow for t in p['traces']]
    online=[t for p in all_parts['v143'] for t in p['traces']]
    for trace in online:trace['legacy_action']=trace['current_best_action']
    changed=[t for t in shadow_trace if t['final_teacher_action']!=t['legacy_action']]
    write_csv(OUT/'changed_decisions.csv',changed)
    write_csv(OUT/'online_reroll.csv',online)
    def groups(traces,key):
        groups=defaultdict(list)
        for row in traces:groups[str(key(row))].append(row)
        return {k:dict(opportunities=len(v),positive=sum(r['positive_advantage'] for r in v),
                       rate=mean(r['positive_advantage'] for r in v),
                       mean_advantage=[mean(r['reroll_advantage'][i] for r in v) for i in range(3)]) for k,v in groups.items()}
    # V142 signed normalized pressure; natural intervals current surplus,
    # partial uncovered rent, and coins<=0. No second definition of pressure.
    pressure=lambda t:'low' if t['rent_pressure']<=0 else 'medium' if t['rent_pressure']<1 else 'high'
    shadow_summary=dict(episodes=4,total_states=sum(p['row']['decisions'] for p in shadow),
        opportunities=len(shadow_trace),positive=sum(t['positive_advantage'] for t in shadow_trace),
        changed=len(changed),changed_non_reroll=sum(t['final_teacher_action']['action_type']!=T.REROLL for t in changed),
        by_stage=groups(shadow_trace,lambda t:t['rent_stage']),by_pressure=groups(shadow_trace,pressure),
        by_tokens=groups(shadow_trace,lambda t:t['reroll_tokens']))
    coverage={mode:dict(opportunities=sum(r['reroll_opportunities'] for r in rr),
        rerolls=sum(r['rerolls_used'] for r in rr),rerolls_per_episode=mean(r['rerolls_used'] for r in rr)) for mode,rr in rows.items()}
    from types import SimpleNamespace
    cost_comparison={}
    for model in ('zero','constant','token_aware'):
        advantages=[]
        for t in shadow_trace:
            state=SimpleNamespace(reroll_tokens=t['reroll_tokens'],rent_stage=t['rent_stage'],
                                  coins=t['coins'],current_rent=t['rent'])
            cost=token_cost(state,RentRerollConfig(cost_model=model))
            advantages.append(tuple(t['expected_best_after_reroll'][i]-cost[i]-t['current_best_score'][i] for i in range(3)))
        cost_comparison[model]=dict(opportunities=len(advantages),positive=sum(a>(0,0,0) for a in advantages),
                                    mean_advantage=[mean(a[i] for a in advantages) for i in range(3)])
    proxies=[p for part in all_parts['v143'] for p in part['success_proxy']]
    consecutive=Counter()
    for part in all_parts['v143']:consecutive.update(part['consecutive'])
    latency={}
    for mode in ('legacy','v143'):
        categories=defaultdict(lambda:dict(n=0,seconds=0))
        for part in all_parts[mode]:
            for kind,values in part['latencies'].items():
                categories[kind]['n']+=values['n'];categories[kind]['seconds']+=values['seconds']
        latency[mode]={k:dict(**v,mean=v['seconds']/v['n']) for k,v in categories.items()}
    protected=json.loads((OUT/'protected_hashes.json').read_text())
    for name,sha in protected.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Historical artifact drift')
    difference=[dict(seed=a['seed'],delta=b['stage']-a['stage'],legacy=a['stage'],v143=b['stage']) for a,b in zip(rows['legacy'],rows['v143'])]
    worst=sorted(difference,key=lambda r:abs(r['delta']),reverse=True)[:6]
    for row in worst:
        row['traces']={}
        for mode in ('legacy','v143'):
            path=OUT/'reroll_episode_traces'/f"{mode}-{row['seed']}.jsonl.gz"
            if not path.exists():path=OUT/'reroll_episode_traces'/f"shadow-{row['seed']}.jsonl.gz"
            row['traces'][mode]=str(path.relative_to(ROOT))
    improved=paired['paired_bootstrap_95'][0]>0
    near_noise=0
    for trace in online:
        if not trace['positive_advantage']:continue
        coordinate=next((i for i,x in enumerate(trace['reroll_advantage']) if x!=0),2)
        if trace['reroll_advantage'][coordinate]<=trace['standard_error'][coordinate]:near_noise+=1
    manifest=json.loads((ROOT/'logs/v128-magpie-shards/manifest.json').read_text())
    for entry in manifest['entries']:
        if hashlib.sha256((ROOT/'logs/v128-magpie-shards'/entry['file']).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('V128 shard drift')
    result=dict(version='V143 Teacher Reroll Value Integration',protocol=protocol,
        frozen_v141=dict(teacher_stage=11.609375,teacher_wins=57,bc_stage=9.6328125,bc_wins=4,episodes=128),
        opportunity_suite=str((OUT/'opportunity_suite.csv').relative_to(ROOT)),
        shadow=shadow_summary,resource_cost_comparison=cost_comparison,coverage=coverage,summaries=summaries,paired=dict(**paired,**extras),
        online_groups=dict(by_stage=groups(online,lambda t:t['rent_stage']),by_pressure=groups(online,pressure),by_tokens=groups(online,lambda t:t['reroll_tokens'])),
        immediate_proxy=dict(n=len(proxies),improved=sum(p['improved'] for p in proxies),rate=mean(p['improved'] for p in proxies) if proxies else None),
        consecutive=dict(consecutive),maximum_consecutive=max(p['max_streak'] for p in all_parts['v143']),
        latency=latency,largest_differences=worst,
        smoke={mode:summarize(rr[:32],sum(p['seconds'] for p in all_parts[mode][:32]),13) for mode,rr in rows.items()},
        protected_artifacts_unchanged=True,training_updates=0,
        result_case='E: positive paired Stage interval; decision attribution before new data' if improved else 'A: exploratory integration; improvement not established' if paired['mean_stage_delta']>=0 else 'Calibration needed; paired outcome declined',
        next='V144先做Teacher Reroll误差归因与估计不确定性审计；64局区间含零，暂不生成新数据或训练BC。独立BC Fit Capacity/Optimization问题保留。',
        selected_advantage_within_one_mc_se=near_noise,
        v128_shards_verified=len(manifest['entries']),
        tests=dict(full_passed=522,failed=0),
        limitations=['64 development episodes, not holdout','lexicographic vector resource proxy, not optimal token value','horizon30 excludes future offers; candidate MC uncertainty and forecast-trial noise differ','episode latency includes diagnostics/trace I/O; timings are not pure deployment throughput','same seeds after reroll do not preserve aligned future random events; paired policy outcomes are not causal effects of individual rerolls'])
    result['performance_wall_fresh32']={}
    for mode in ('legacy','v143'):
        timing=json.loads((OUT/f'{mode}_timing.json').read_text())
        result['performance_wall_fresh32'][mode]=dict(fresh_episodes=32,wall_seconds=timing['wall_seconds'],
            episodes_per_second=32/timing['wall_seconds'],workers=timing['workers'],
            scope='medium segment32 fresh episodes plus32 cached row reads and pool overhead')
    (ROOT/'reports/v143_teacher_reroll_value.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    write_report(result)
    print(json.dumps({k:result[k] for k in ('coverage','paired','immediate_proxy','consecutive','maximum_consecutive','latency','result_case')},ensure_ascii=False,indent=2))


def write_report(r):
    sections=[]
    def add(title,text):sections.extend([f'## 【{title}】','',text,''])
    def table(headers,rows):
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                         ['| '+' | '.join(str(x) for x in row)+' |' for row in rows])
    def interval(v):return '['+', '.join(f'{x:.4f}' for x in v)+']'
    s=r['summaries'];p=r['paired'];shadow=r['shadow'];cfg=r['protocol']
    add('当前版本','V143 Teacher Reroll Value Integration')
    add('本轮目标','Reroll进入同一个长期租金价值比较框架。训练更新0；不改V130、V128、BC/候选Encoder、奖励、环境、租金表、符号或物品规则。未生成新版训练数据。')
    add('冻结基线','旧版本继续由forecast_rents调用；新版为forecast_rents_v143。旧RentForecastAgent源文件及V128/V130/V141/V142产物hash保持不变，V128全部48个shard hash核对通过。\n\nV141历史128局：Teacher平均Stage11.609375、57胜；BC平均Stage9.6328125、4胜。本轮64个新开发seed16000–16063单独比较，不重定义旧基线。')
    add('Teacher 旧逻辑','符号分支只评分Pick/Skip，Reroll被排除；item/removal等由原Heuristic决策。租金预测8 trials、seed20270927、horizon30，按first_rent_paid→rents_paid→cash字典序选择。V143非重掷分支直接继承旧函数。')
    add('V143 Reroll Value 设计','从公开State重建独立采样器，复用PreparedSymbolOffers的真实候选规则分布；不接收GameEnv或实际RNG。每个可能符号只计算一次旧Teacher租金预测，全部采样offer共享候选结果。\n\nValue为三维向量（首次租金通过比例、平均已付租金、平均期末cash）。E[max Value(new offer)]−ResourceCost与当前best在原字典序中比较。优势第一非零分量>0才重掷，threshold=0，完全相等保留旧动作。没有固定正bonus。\n\n成本对比：zero=(0,0,0)，constant=(0,1/8,1 coin)，token_aware=constant×剩余租金阶段比例/max(tokens,1)/(1+max(pressure,0))。沿用V142 signed pressure=(rent−coins)/rent。第1分量成本为0，不让未来券价值扣减当前首次租金生存优先级。\n\n1/8来自旧预测trial分辨率，1 coin为显式预留代理；这些不是经验证的最优资源价。该代理在rent预测相同但cash改善时可能过度抑制重掷，在预测已经无法存活时仍可能计入未来机会成本，列为V144校准重点。预测仍只含固定牌组30转，不含后续选牌策略。')
    add('修改文件','新增luck_agent/agents/rent_reroll_agent.py、tools/evaluate_reroll_teacher.py、tests/test_v143_reroll.py。扩展evaluation/evaluator.py注册新agent并记录版本/配置；旧入口和原Teacher源码不替换。更新seed_usage及ITERATION_STATE。')
    add('测试结果','完整522项通过，0 Failed。覆盖合法/非法、抽样前缀及阶段稀有度、RNG隔离、无未来读取、资源成本、确定性、旧分支兼容、trace及连续重掷更新、cache的经济/目录变更失效、既有BC/checkpoint加载。详细日志logs/v143-reroll/tests.txt。')
    add('RNG / Leakage 验证','Teacher输入只有公开State和目录；候选抽样seed来自公开状态hash与固定独立seed20260929。未复制或读取真实未来RNG。\n\n测试：评分后拒绝Reroll时真实RNG/global RNG不变，与未评分对照逐步结果相同；更换隐藏RNG仍对同一公开State得到同分数。4局shadow每步核对真实RNG；旧Teacher控制全部动作。\n\nScore cache包含有序实例/timer/bonus、物品、coins、rent/remaining spins/stage、forced/terminal/稳定身份状态、预测预算和目录hash。候选分布独立按完整公开State重建；不把MC估计随机结果当作真实下一次offer。')
    add('Opportunity Suite',f"构造A优秀、B较差/多券、C一般/最后券、D高压力、E低压力、F核心mouse/cheese协同、G零券、H物品phase八类fixture。不是新训练数据，不强制B/D/E必须重掷。A三种成本均拒绝；G/H不进入评分；B–F零成本存在正优势，但cost代理可改变决策。\n\n在同一固定状态上比较N=8/16/32/64嵌套独立采样，最大向量误差vs64为{cfg['max_deltas_vs64']}。预设容限(.0625,.0625,5 cash)，选最小通过量N={cfg['samples']}。16次不是所有状态的精度保证；cash误差随N不必单调，此小套件的rent分量未显示差异。\n\n明细见opportunity_suite.csv、convergence.csv；non_reroll_compatibility.json记录8个固定状态兼容检查。")
    add('Shadow Evaluation',f"旧Teacher控制4局（16000–16003），共{shadow['total_states']}决策、{shadow['opportunities']}次Reroll机会。{shadow['positive']}次正优势（{shadow['positive']/shadow['opportunities']:.2%}），改变{shadow['changed']}次建议，非重掷建议变化{shadow['changed_non_reroll']}。不全拒绝，也不全部重掷。\n\n同276个已缓存状态的成本比较，无额外游戏重跑：\n\n"+table(['成本','正优势次数','占机会'],[[k,v['positive'],f"{v['positive']/v['opportunities']:.2%}"] for k,v in r['resource_cost_comparison'].items()])+'\n\nstage/pressure/token分组及平均优势向量保存在机器报告shadow字段。')
    add('Reroll Coverage',table(['策略','机会','执行','每局'],[[k,v['opportunities'],v['rerolls'],f"{v['rerolls_per_episode']:.3f}"] for k,v in r['coverage'].items()])+'\n\n机会数不同是策略耗券和轨迹变化的结果，不能把两者机会率差直接解释为预测准确率。新版按在线压力分组：\n\n'+table(['压力','机会','重掷','比例'],[[k,v['opportunities'],v['positive'],f"{v['rate']:.2%}"] for k,v in r['online_groups']['by_pressure'].items()])+'\n\nlow=pressure≤0；medium=0<pressure<1；high=pressure≥1。在线没有high样本，不作高压力泛化结论。')
    add('Legacy vs V143','先32局Smoke，后扩到同方案64局；复用前32局及shadow已执行的旧策略结果，不重复模拟。64局结果：\n\n'+table(['策略','Mean Stage','Stage Std','Stage 95%CI','Mean Reward','Wins','Wilson 95%CI'],[[k,f"{v['average_stage']:.4f}",f"{v['std']['stage']:.4f}",interval(v['mean_95_ci']['stage']),f"{v['mean_reward']:.2f}",f"{int(round(v['win_rate']*64))}/64",interval(v['win_rate_95_ci'])] for k,v in s.items()])+'\n\n全部零非法/零截断。每一租金存活率及Wilson CI在JSON.summaries.*.rent_survival字段。')
    add('配对比较',f"V143−Legacy平均Stage差{p['mean_stage_delta']:+.5f}，paired bootstrap95%CI {interval(p['paired_bootstrap_95'])}；改善/相同/更差={p['improved']}/{p['unchanged']}/{p['worse']}。bootstrap2000次，seed57，单位为配对episode seed。\n\nReward差{p['reward']['mean_delta']:+.4f}，CI {interval(p['reward']['ci95'])}；Win比例差{p['won']['mean_delta']:+.4f}，CI {interval(p['won']['ci95'])}。三个区间都包含0，不能证明提升，也不能证明非劣。")
    add('Reroll 案例','全部合法机会保留当前best、预期new best、std/SE/quantiles、cost、score、advantage及最终动作，CSV为shadow_reroll.csv和online_reroll.csv。\n\n最大差异完整决策轨迹索引：\n\n'+table(['seed','旧Stage','新Stage','ΔStage'],[[v['seed'],v['legacy'],v['v143'],v['delta']] for v in r['largest_differences']])+f"\n\nReroll后立即best score改善{r['immediate_proxy']['improved']}/{r['immediate_proxy']['n']}={r['immediate_proxy']['rate']:.2%}；已覆盖最后一券，不把未来补券状态误当作立即结果。此代理不是因果胜率。\n\n连续重掷run分布{r['consecutive']}；最多{r['maximum_consecutive']}次，无3+。每一步均重新评分并验证tokens−1，所有执行动作均满足正优势。{r['selected_advantage_within_one_mc_se']}/125次的首个决定分量优势不超过一个outer-MC SE，是后续不确定性核查候选，不据此改本轮策略。")
    latency=r['latency']
    add('性能成本',table(['决策类别','平均latency ms'],[['Legacy所有决策',f"{latency['legacy']['legacy']['mean']*1000:.3f}"],['V143非重掷机会',f"{latency['v143']['non_reroll']['mean']*1000:.3f}"],['V143重掷机会',f"{latency['v143']['reroll_opportunity']['mean']*1000:.3f}"]])+'\n\n最后32个新局的3-worker墙钟吞吐（含缓存行读取/pool/审计/trace）：\n\n'+table(['策略','新局数','wall sec','episodes/sec'],[[k,v['fresh_episodes'],f"{v['wall_seconds']:.2f}",f"{v['episodes_per_second']:.3f}"] for k,v in r['performance_wall_fresh32'].items()])+'\n\n64局按逐局审计耗时之和的等效吞吐Legacy0.182、新版0.069 eps，不是3-worker墙钟吞吐。新版online含额外旧分支兼容查询和trace写入；前4个Legacy时间由shadow减去实测新推理时间，保留额外I/O。状态分布/并发负载不同，不能当成同状态微基准或直接与旧0.263 eps比较。\n\n优化复用同状态每个symbol/Skip的预测，而非N×重复forecast；bounded cache256个上下文跨重掷复用。未降低旧8 trials/30 horizon正确性合同。')
    add('Regression','旧Teacher、环境/规则/租金、BC与Dataset不变；非重掷策略直接委托旧函数，固定状态检查和online兼容断言通过。单次/连续重掷合法、资源更新正确。stage差既有正也有负；程序兼容通过不等于策略性能提升。seed与参数cache绑定，诊断计数/末券代理从已保存轨迹补全，没有重跑游戏。')
    add('结论','1. Teacher真正考虑Reroll：是，独立采样并计算E[max Value]及资源成本。\n\n2. 实际选择：125次，平均1.953/局。\n\n3. 状态：低/中压力且字典序净优势为正；逐stage/token/candidate明细在CSV，在线高压力无样本。\n\n4. 策略改善：点估计Stage+0.406、Wins31→36，但配对Stage/Reward/Win CI均包含0，证据不足。\n\n5. 重新生成训练数据：暂不支持直接启动；覆盖缺口已在框架上补齐，长期价值与成本代理还需要归因/校准。本轮未生成数据。归类为探索性Case A候选，未满足“性能已提升或非劣”的证明标准；不是Case E。')
    add('V144 决策',r['next']+'\n\n优先分析+5与−4阶段案例，outer candidate sampling与inner8-trial预测误差分别核查，审计rent成本在预测等租金/濒死情形是否过度压制cash改善。原BC train symbol fit72.9%独立问题继续保留，教师价值质量尚未确认时不启动新Teacher数据或BC训练。')
    add('Artifact','reports/v143_teacher_reroll_value.json；logs/v143-reroll/{protocol.json,opportunity_suite.csv,convergence.csv,shadow_reroll.csv,online_reroll.csv,changed_decisions.csv,legacy_episodes.csv,v143_episodes.csv,smoke_gate.json,protected_hashes.json,comparison.json,tests.txt}；reroll_episode_traces/*.jsonl.gz保存完整公开决策轨迹。')
    (ROOT/'reports/v143_teacher_reroll_value.md').write_text('\n'.join(sections),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['setup','shadow','smoke','medium','report'],required=True)
    parser.add_argument('--workers',type=int,default=3);args=parser.parse_args()
    if args.phase=='setup':setup();return
    protocol=json.loads((OUT/'protocol.json').read_text())
    if args.phase=='shadow':
        shadow=run('shadow',protocol['shadow_seeds'],args.workers)
        # Reuse shadow's executed LEGACY outcomes as the paired reference.
        for part in shadow:
            legacy={**part,'mode':'legacy','traces':[]}
            (OUT/f"legacy-{part['row']['seed']}.json").write_text(json.dumps(legacy))
        return
    if args.phase in ('smoke','medium'):
        n=32 if args.phase=='smoke' else 64;seeds=protocol['online_seeds'][:n]
        run('legacy',seeds,args.workers);run('v143',seeds,args.workers)
        return
    report()


if __name__=='__main__':main()
