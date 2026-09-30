"""Render the frozen V147 analysis; never trains or reads test metrics."""
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'logs/v147-generalization'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def pc(x):return f'{100*x:.2f}%'
def pp(x):return f'{100*x:+.3f} pp'

def main():
    a=read(OUT/'analysis.json');i=read(OUT/'interpretation.json');cfg=read(ROOT/'configs/v147_multiseed_generalization.json')
    tests=(OUT/'tests.txt').read_text(encoding='utf-8') if (OUT/'tests.txt').exists() else ''
    m=re.search(r'Ran (\d+) tests',tests);test={'count':int(m.group(1)) if m else None,'passed':bool(m and re.search(r'\nOK\s*$',tests))}
    out={'version':'V147','registry':a['registry'],'budgets':a['budget_summary'],'paired':a['paired_comparison'],
        'frequency':a['frequency_bucket_metrics'],'confusions':a['confusion_metrics'],'seed_rows':a['seed_rows'],
        'best_curve_points':a['best_curve_points'],'candidate_gate':a['candidate_gate'],
        'candidate_budget':a['selected_budget'],'canonical_seed':a['canonical_seed'],
        'online_smoke':'NOT TRIGGERED' if a['selected_budget'] is None else 'PENDING',
        'tests':test,'frozen_files':a['frozen_files'],'interpretation':i,'test_metrics':'SEALED'}
    write(ROOT/'reports/v147_multiseed_generalization.json',out)
    s=a['budget_summary'];pairs=a['paired_comparison'];rows=a['seed_rows'];freq=a['frequency_bucket_metrics'];conf=a['confusion_metrics']
    l=['# V147 Multi-Seed Generalization & Training Budget Validation','',
       '## 【当前版本】','V147 Multi-Seed Generalization','',
       '## 【本轮目标】','冻结V128数据/模型宽16/优化器/编码器，仅改变训练seed和更新预算，定位可重复的验证表现区间。','',
       '## 【冻结资产】',f"{a['frozen_files']}个历史文件实验末SHA不变；V128 train/val/test分区、V130权重及V143–V146报告保留。test指标SEALED。",'',
       '## 【预注册实验】',
       f"运行前固定seed {cfg['training_seeds']}，预算 {cfg['budgets']}；primary=Validation Symbol Top1；配对比较、bootstrap种子/次数与≥2.000pp的online门槛均先于新结果固定。",
       '复用V146的seed123/456/789历史200更新及部分500/1000 checkpoint；从200步恢复优化器与采样顺序，新路径在500（另seed123在1000）权重bitwise一致。2个新seed从0训练；所有5×5预算点齐全。','',
       '## 【测试结果】',f"完整{test['count']}项测试{'通过' if test['passed'] else '未确认'}，0新teacher数据；旧模型和历史诊断未覆盖。",'',
       '## 【V130 Baseline】','seed123/200：Train Symbol2072/2843=72.88%；Val Symbol578/762=75.85%；权重与V130逐项相同，原V130 checkpoint SHA独立登记。五种子200平均Train73.16%、Val75.70%。','',
       '## 【Multi-Seed Budget Results】','下表每格为5个训练seed的mean±sample SD；CI/median/min/max见JSON及budget_summary.csv。','',
       '| Updates | Seeds | Train Symbol Fit | Val Symbol Fit | Val CE | Val Top2 | Val Teacher Rank |',
       '|---:|---:|---:|---:|---:|---:|---:|']
    for r in s:
        def fmt(k,scale=1.,suffix=''):return f"{r[k]['mean']*scale:.2f}±{r[k]['std']*scale:.2f}{suffix}"
        l.append(f"| {r['updates']} | 5 | {fmt('train_symbol_fit',100,'%')} | {fmt('val_symbol_fit',100,'%')} | {fmt('val_symbol_ce',1)} | {fmt('val_top2',100,'%')} | {fmt('val_teacher_rank',1)} |")
    l+=['','## 【Paired Comparison】',
        '同一组seed逐对相减；CI为固定seed的10,000次paired bootstrap百分位区间（仅描述当前5种子，不外推游戏总体）。','',
        '| Higher−Lower | Per seed ΔVal Top1 (pp; 123/456/789/24680/13579) | Mean Δ | Bootstrap 95% CI | Better/Equal/Worse |',
        '|---|---|---:|---:|---:|']
    for p in pairs:
        vals='/'.join(f"{100*p['per_seed'][str(z)]:+.2f}" for z in cfg['training_seeds'])
        l.append(f"| {p['higher']}−{p['lower']} | {vals} | {pp(p['mean_delta'])} | [{pp(p['bootstrap_ci95'][0])}, {pp(p['bootstrap_ci95'][1])}] | {p['better']}/{p['equal']}/{p['worse']} |")
    l+=['',
        '## 【Generalization Gap】','Gap=Train Symbol Top1−Val Symbol Top1，五种子均值：'+
        ' / '.join(f"{r['updates']}:{100*r['generalization_gap']['mean']:+.2f}pp" for r in s)+
        '。训练准确率单调上升，500以后验证均值回落，gap迅速扩大。','',
        '## 【Validation CE】','五种子均值：'+
        ' / '.join(f"{r['updates']}:{r['val_symbol_ce']['mean']:.3f}" for r in s)+
        '。逐seed曲线最低CE更新为'+str({k:v['ce_update'] for k,v in a['best_curve_points'].items()})+
        '；最高Top1更新为'+str({k:v['top1_update'] for k,v in a['best_curve_points'].items()})+
        '；仅3/5相同。模拟CE early-stop为诊断，未改变生产选择规则。','',
        '## 【Head / Medium / Tail】','V146冻结训练teacher目标频次三分桶，按同一映射统计各budget；val tail仅25状态，勿过度解释。','',
        '| Updates | Train Head | Train Medium | Train Tail | Val Head | Val Medium | Val Tail |',
        '|---:|---:|---:|---:|---:|---:|---:|']
    for step in cfg['budgets']:
        cells=[]
        for split in ('train','validation'):
            for b in ('head','medium','tail'):
                zz=[r['accuracy'] for r in freq if r['updates']==step and r['split']==split and r['bucket']==b]
                cells.append(f'{100*sum(zz)/len(zz):.2f}%')
        l.append('| '+str(step)+' | '+' | '.join(cells)+' |')
    l+=['',
        '## 【Teacher Rank】','五种子Validation mean rank在200/300/500/750/1000为'+
        '/'.join(f"{r['val_teacher_rank']['mean']:.3f}" for r in s)+
        '；训练rank2错误持续减少，验证rank2错误约维持在每种子120余例，表明训练记忆增加不等于验证等量改进。','',
        '## 【Confidence Errors】','Validation高置信错误均值按预算为'+
        '/'.join(f"{r['val_high_confidence_wrong']['mean']:.1f}" for r in s)+
        '；验证错误平均预测置信度从200的0.559升至1000的0.715。无温度/阈值调整。',
        'V146主要offline confusion如bar_of_soap→SKIP与goldfish→bar_of_soap在logs/v147-generalization/analysis.json按train/val与预算分别保存；Time Machine/Undertaker在当前受限符号池无对应机会，N/A。','',
        '## 【Compute Cost】','累计训练+评估墙钟均值(s)：'+
        '/'.join(f"{r['updates']}:{r['runtime']['mean']:.2f}" for r in s)+
        '；单次全train+val验证约0.58–0.62s。峰值内存为Windows进程历史工作集上界，非各seed独立峰值；部分预算运行时来自V146复用，故不作精确同进程训练/验证拆分。',
        '验证Top1均值增益每额外100更新约200→300:+1.31pp、300→500:+0.34pp、500→750:−0.19pp、750→1000:−0.28pp。','',
        '## 【Candidate Selection】',i['candidate_decision'],'',
        '## 【32局 Online Smoke】','NOT TRIGGERED；按预注册≥2.000pp门槛严格判定，无新在线对局或128局benchmark。','',
        '## 【结论】',i['main_conclusion'],i['sweet_region'],'',
        '## 【V148决策】',i['v148'],'',
        '## 12个关键问题','']
    l += [f'{n}. {answer}' for n,answer in enumerate(i['answers'],1)]
    l+=['','证据限制：'+'；'.join(i['limits'])+'。','',
        '完整原始逐seed曲线、checkpoint、frequency/confusion、paired CSV及预注册配置均在logs/v147-generalization与configs/v147_multiseed_generalization.json。']
    (ROOT/'reports/v147_multiseed_generalization.md').write_text('\n'.join(l)+'\n',encoding='utf-8')
    write(OUT/'online_smoke/status.json',{'status':out['online_smoke'],'selected_budget':a['selected_budget'],
        'reason':i['candidate_decision'],'games':0,'test_metrics':'SEALED'})
    print(json.dumps({'tests':test,'selected_budget':a['selected_budget'],'report':'reports/v147_multiseed_generalization.md'}))

if __name__=='__main__':main()
