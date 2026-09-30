"""Render V148 analysis after the checkpoint-choice lock and audit exist."""
import json
from pathlib import Path
import re
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'logs/v148-checkpoint-selection'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def pct(x):return f'{100*x:.2f}%'
def pp(x):return f'{100*x:+.3f}pp'
def tv(a,b):
    keys=set(a)|set(b);sa=sum(a.values());sb=sum(b.values())
    return .5*sum(abs(a.get(k,0)/sa-b.get(k,0)/sb) for k in keys)
def hist_mean(x):return sum(float(k)*v for k,v in x.items())/sum(x.values())

def main():
    a=read(OUT/'analysis.json');config=read(ROOT/'configs/v148_checkpoint_selection.json');lock=read(OUT/'checkpoint_choices.lock.json')
    tests=(OUT/'tests.txt').read_text(encoding='utf-8') if (OUT/'tests.txt').exists() else ''
    match=re.search(r'Ran (\d+) tests',tests);test={'count':int(match.group(1)) if match else None,'passed':bool(match and re.search(r'\nOK\s*$',tests))}
    choices=a['choices'];policies={x['policy']:x for x in a['policy_summary']};gate=a['gate_vs_fixed500'];coverage=a['coverage']['primary-a']
    selected=policies['ce_selected'];fixed300=policies['fixed300'];fixed500=policies['fixed500']
    d300=[selected['top1']['values'][str(s)]-fixed300['top1']['values'][str(s)] for s in config['splits'][0]['training_seeds']]
    d500=[selected['top1']['values'][str(s)]-fixed500['top1']['values'][str(s)] for s in config['splits'][0]['training_seeds']]
    interpretation={
      'conclusion':'CE选择器的更新位置很稳定，但没有胜过固定500：主拆分Top1平均低0.262pp，2胜1平2负，外部开发验证regret也高于固定500。它使CE降低0.0149、高置信错误减少11.6个、错误置信度下降，属于soft generalization/calibration信号；Mean Teacher Rank却恶化0.0042，预注册总门槛失败。',
      'v149':'不生产化Early Stopping。把固定500作为简单诊断基线，V149进入单变量Regularization Audit，优先针对高置信错误和中长尾泛化；继续封存test，预注册后再决定是否full-train refit或online smoke。',
      'answers':[
        '能。主拆分选择400/400/400/300/400，5/5落在300–600；三拆分11次选择为300一次、400九次、500一次。',
        '主拆分mean380、median400、sample SD44.7、范围300–400；未出现750/1000失控。',
        '没有更好，且仅在预注册0.5pp容忍下达到4/5“不明显差”：CE-selected平均76.69%，固定500为76.96%，差−0.262pp，2胜1平2负。',
        '降低。平均Validation CE从固定500的0.5991降至0.5841，差−0.0149；三拆分次级6次比较平均差−0.0120。',
        '未改善。Mean Rank为1.3024，固定500为1.2982，差+0.0042。',
        '减少。高置信错误31.0对42.6，平均少11.6；错误平均置信度0.629对0.658。',
        '主拆分5个seed中3个选择update完全一致；另外两个相差100和350 updates，说明Top1选择更跳跃。Top1规则仅作诊断。',
        '标签频次、候选频次、stage差异小；Selection相对开发validation的TV分别0.060/0.030/0.048。deck size与全决策candidate-count TV为0.184/0.096，存在中等episode组成偏移。',
        '不足。更新位置稳定、CE/置信错误改善，但Primary Top1、rank与regret未超过简单固定500，预注册门槛失败。',
        'Regularization Audit；固定500作为比较基线，不进行Full-Train Refit或Early-Stopping生产化。'
      ],
      'limitations':['主拆分只有8个selection episodes；虽然另做两拆分×3seed，split variance仍有限',
        'V128 validation在V146/V147已反复观察，只是本轮选择独立的开发审计，不是新holdout',
        'Validation tail仅25个状态，bucket结果探索性','FIT从32局减为24局，绝对性能不能与V147 full-train直接做唯一因果比较',
        'test shard与嵌入test outcome的V128 manifest在V148实验进程均未打开']}
    out={**a,'tests':test,'interpretation':interpretation,'checkpoint_lock':{'sha256':a['choice_lock_sha256'],
        'development_validation_access_before_lock':lock['development_validation_access_before_lock']},
        'online_smoke':'NOT APPLICABLE','test_metrics':'SEALED'}
    write(ROOT/'reports/v148_checkpoint_selection_audit.json',out)
    lines=['# V148 Checkpoint Selection & Early-Stopping Contract Audit','',
      '## 【当前版本】','V148 Checkpoint Selection Audit','',
      '## 【本轮目标】','只用V128原train episodes内部的FIT/SELECTION信息选择checkpoint，再锁定选择，最后用V128 development validation审计泛化；test继续封存。','',
      '## 【冻结资产】',f"历史文件校验{read(OUT/'frozen_verification.json')['checked']}项，0变化；V128原split/Teacher、V130与V143–V147资产未覆盖。",'',
      '## 【Leakage Guard】','V148专用读取器不调用会遍历全corpus的旧API；训练阶段只打开train shards。Scaler只由FIT episodes的全部转移拟合，SELECTION/validation均排除；固定游戏规则词表不从样本学习。选择锁SHA为 `'+a['choice_lock_sha256']+'`，锁前validation未打开。V148实验进程未打开test shard，也未读取包含test outcome的V128 manifest。','',
      '## 【Selection Split】','主拆分：24 FIT episodes、8 SELECTION episodes，episode完全隔离；FIT/SELECTION多候选决策2782/1067，其中Symbol 2150/693。另预注册两组24/8拆分，各3个训练seed。三个split hash及episode IDs见split_manifest.json。','',
      '## 【预注册合同】','宽16/28,785参数、Adam0.001、batch64、CE、clip1；每条FIT轨迹训练1000更新，保存200/300/400/500/600/750/1000。Primary为state-weighted SELECTION Symbol CE最低，完全相同取更早；Top1选择只作次级诊断。固定比较200/300/500。','',
      '## 【测试结果】',f"完整{test['count']}项测试{'通过' if test['passed'] else '未确认'}；新增检查覆盖episode隔离/确定性/hash、FIT-only scaler、validation锁、tie-break、test不加载及历史资产。",'',
      '## 【Coverage Audit】','主拆分SELECTION与development validation：Symbol决策693/762；head/medium/tail为582/86/25与648/89/25。标签频次/候选频次/rent-stage TV为'+
      f"{tv(coverage['selection']['symbol_target_frequency'],coverage['development_validation']['symbol_target_frequency']):.3f}/"+
      f"{tv(coverage['selection']['symbol_candidate_frequency'],coverage['development_validation']['symbol_candidate_frequency']):.3f}/"+
      f"{tv(coverage['selection']['rent_stage'],coverage['development_validation']['rent_stage']):.3f}。"+
      f"deck-size/candidate-count TV为{tv(coverage['selection']['deck_size'],coverage['development_validation']['deck_size']):.3f}/"+
      f"{tv(coverage['selection']['candidate_count'],coverage['development_validation']['candidate_count']):.3f}；平均deck {hist_mean(coverage['selection']['deck_size']):.2f} vs {hist_mean(coverage['development_validation']['deck_size']):.2f}，存在episode组成偏移但无极端标签偏移。",'',
      '## 【Checkpoint Choices】','',
      '| Seed | CE-selected update | Top1-selected update | Fixed300 Val | Fixed500 Val | CE-selected Val | Selection CE |','|---:|---:|---:|---:|---:|---:|---:|']
    for x in choices:lines.append(f"| {x['seed']} | {x['ce_selected_update']} | {x['top1_selected_update']} | {pct(x['fixed300_val'])} | {pct(x['fixed500_val'])} | {pct(x['ce_selected_val'])} | {x['selection_ce']:.4f} |")
    lines+=['',f"主拆分selected update mean/median/SD/min/max = {a['selection_stability']['mean']:.1f}/{a['selection_stability']['median']:.0f}/{a['selection_stability']['std']:.1f}/{a['selection_stability']['min']}/{a['selection_stability']['max']}；CE与Top1选择3/5完全相同。三拆分11次选择全部300–500。",'',
      '## 【CE-selected vs Fixed300/500】','',
      '| Policy | Mean Val Top1 | Std | Val CE | Mean Rank | High-conf Wrong | Wrong Confidence | Generalization Gap |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for key in ('ce_selected','fixed300','fixed500'):
        p=policies[key];lines.append(f"| {key} | {pct(p['top1']['mean'])} | {100*p['top1']['std']:.2f}pp | {p['ce']['mean']:.4f} | {p['mean_rank']['mean']:.4f} | {p['high_conf_wrong']['mean']:.1f} | {p['mean_wrong_confidence']:.3f} | {100*p['generalization_gap_mean']:+.2f}pp |")
    lines+=['',f"CE-selected−Fixed300 Top1逐seed：{', '.join(pp(x) for x in d300)}，平均{pp(statistics.mean(d300))}。CE-selected−Fixed500：{', '.join(pp(x) for x in d500)}，平均{pp(gate['mean_top1_delta'])}，bootstrap95%CI[{pp(gate['bootstrap_ci95'][0])}, {pp(gate['bootstrap_ci95'][1])}]，better/equal/worse={gate['better']}/{gate['equal']}/{gate['worse']}。预注册综合门槛：FAILED。",'',
      '## 【Selection Regret】','Regret=hindsight最佳预注册validation Top1−对应policy Top1；oracle仅诊断，不用于选择。','',
      '| Seed | CE-selected Regret | Fixed300 Regret | Fixed500 Regret | Oracle update |','|---:|---:|---:|---:|---:|']
    for x in a['regret']:lines.append(f"| {x['seed']} | {100*x['ce_selected_regret']:.2f}pp | {100*x['fixed300_regret']:.2f}pp | {100*x['fixed500_regret']:.2f}pp | {x['oracle_update']} |")
    means={k:statistics.mean(x[k] for x in a['regret']) for k in ('ce_selected_regret','fixed300_regret','fixed500_regret')}
    lines+=['',f"平均regret：CE-selected {100*means['ce_selected_regret']:.3f}pp，Fixed300 {100*means['fixed300_regret']:.3f}pp，Fixed500 {100*means['fixed500_regret']:.3f}pp；CE选择未降低相对Fixed500的regret。",'',
      '## 【Teacher Rank】',f"CE-selected Mean Rank {selected['mean_rank']['mean']:.4f}，Fixed300 {fixed300['mean_rank']['mean']:.4f}，Fixed500 {fixed500['mean_rank']['mean']:.4f}；相对Fixed500恶化{gate['rank_delta']:+.4f}。Rank2/Rank≥3逐seed明细保存在audit_metrics.csv。",'',
      '## 【Confidence Errors】',f"CE-selected高置信错误均值{selected['high_conf_wrong']['mean']:.1f}，Fixed500为{fixed500['high_conf_wrong']['mean']:.1f}，减少{-gate['high_conf_wrong_delta']:.1f}；错误平均置信度{selected['mean_wrong_confidence']:.3f} vs {fixed500['mean_wrong_confidence']:.3f}。这是soft improvement，但不能覆盖Primary Top1/rank门槛失败。",'',
      '## 【Head / Medium / Tail】','Validation每seed n=648/89/25；tail仅探索性。','',
      '| Policy | Head | Medium | Tail |','|---|---:|---:|---:|']
    for key in ('ce_selected','fixed300','fixed500'):
        p=policies[key];lines.append('| '+key+' | '+' | '.join(pct(p['frequency_buckets'][b]['accuracy_mean']) for b in ('head','medium','tail'))+' |')
    lines+=['',
      '## 【Split Limitations】','；'.join(interpretation['limitations'])+'。两组次级拆分共6次：CE-selected相对Fixed500的Top1平均+0.066pp、CE平均−0.0120；与主拆分Top1−0.262pp不完全一致，说明外部Top1收益仍受split/seed噪声影响。','',
      '## 【Online Smoke】','NOT APPLICABLE。V148模型仅用FIT subset训练，是选择合同诊断模型；未refit完整train、未运行在线游戏。','',
      '## 【结论】',interpretation['conclusion'],'',
      '## 【V149决策】',interpretation['v149'],'','## 十个问题','']
    lines += [f'{n}. {answer}' for n,answer in enumerate(interpretation['answers'],1)]
    lines+=['','完整拆分、锁文件、训练曲线、选择/审计CSV、coverage与原始指标位于logs/v148-checkpoint-selection。']
    (ROOT/'reports/v148_checkpoint_selection_audit.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'tests':test,'gate_passed':gate['passed'],'selected_updates':[x['ce_selected_update'] for x in choices]}))

if __name__=='__main__':main()
