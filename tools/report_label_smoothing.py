"""Build the human and machine V149 reports from frozen audit outputs."""
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'logs/v149-label-smoothing'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def pct(x):return f'{100*x:.2f}%'
def pp(x):return f'{100*x:+.3f}pp'
def pm(x):return f"{x['mean']:.4f} ± {x['std']:.4f}"

def aggregate_frequency(rows,epsilon,split,bucket):
    values=[x['accuracy'] for x in rows if x['epsilon']==epsilon and x['split']==split and x['bucket']==bucket]
    return statistics.mean(values),statistics.stdev(values),next(x['n'] for x in rows if x['epsilon']==epsilon and x['split']==split and x['bucket']==bucket)

def aggregate_confusion(confusions,epsilon,pair):
    values=[confusions[f'{epsilon:.2f}/{seed}/validation']['tracked'][pair] for seed in (123,456,789,24680,13579)]
    return statistics.mean(values),statistics.stdev(values)

def main():
    cfg=read(ROOT/'configs/v149_label_smoothing.json');a=read(OUT/'analysis.json');frozen=read(OUT/'frozen_verification.json')
    summaries={x['epsilon']:x for x in a['summaries']};freq=a['frequency_bucket_metrics'];conf=a['confusions']
    report={'version':'V149 Label Smoothing Audit','config':cfg,'analysis':a,
        'test_result':{'targeted':7,'full_suite':568,'failures':0,'sandbox_permission_errors_first_attempt':5},
        'historical_assets':frozen,'decision':'No epsilon passed; no candidate and no online smoke; V150 Weight Decay Audit.',
        'limitations':['Development validation has been repeatedly observed since V146; it is not an untouched holdout.',
            'Validation tail has 25 samples per seed and is exploratory only.','32-episode online smoke was not triggered.']}
    (ROOT/'reports/v149_label_smoothing_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['# V149 Label Smoothing Regularization Audit','',
        '## 【当前版本】','','V149 Label Smoothing Audit。','',
        '## 【本轮目标】','','在固定 500 updates 的 V147 强基线上，只改变 label smoothing ε，判断它能否减少错误过度自信，同时稳定改善开发验证集的符号决策泛化。','',
        '## 【冻结资产】','',
        '- V128 train 9000–9031 与 development validation 10000–10007；test 11000–11007 继续封存。','- 宽度 16、28,785 参数、Adam、LR 0.001、batch 64、clip 1、无 weight decay/dropout/scheduler。','- V128 encoder、teacher、全 train scaler、V146 frequency mapping 与 0.8 高置信错误阈值。',f"- 历史文件核对 {frozen['checked']} 项，变化 0；实验进程未打开 test 分片或 V128 manifest。",'',
        '## 【预注册合同】','',
        '- ε = 0.00 / 0.02 / 0.05 / 0.10，5 个相同种子，共 20 个固定 500-update 运行。','- 正 ε 的平滑质量只分配给当前合法候选；padding 不参与。ε=0 直接调用原 CE。','- 所有横向验证统一使用普通 hard-label CE。','- 晋升要求同时满足：平均 Top1 严格提高、至少 4/5 种子不低、平均 Rank 不差、hard CE 恶化不超过 0.005、平均高置信错误严格下降。多个通过时选最小 ε。','- Online 候选种子预注册为验证 Top1 中位种子；只有离线门槛通过才使用 17000–17031。','',
        '## 【测试结果】','','V149 定向回归 7/7 通过；完整测试 **568/568 通过，0 失败**。沙箱内首次执行有 5 项 Windows 多进程测试因管道权限报 WinError 5；同一测试集在允许创建进程管道的环境中全部通过。','',
        '## 【ε=0 Regression】','','5/5 种子的 ε=0 最终权重均与 V147 Fixed500 历史 checkpoint **bitwise 一致**；scaler、Validation Symbol Top1 与 hard CE 也逐值一致。正 ε 训练只在该门槛通过后启动。','',
        '## 【Multi-Seed Results】','',
        '| ε | Train Symbol | Val Symbol | Standard Val CE | Val Top2 | Mean Rank | HC Wrong | Wrong Conf. |','|---:|---:|---:|---:|---:|---:|---:|---:|']
    for e in cfg['epsilons']:
        s=summaries[e];lines.append(f"| {e:.2f} | {pct(s['train_symbol']['mean'])} ± {100*s['train_symbol']['std']:.2f}pp | {pct(s['val_symbol']['mean'])} ± {100*s['val_symbol']['std']:.2f}pp | {pm(s['standard_val_ce'])} | {pct(s['val_top2']['mean'])} | {pm(s['mean_rank'])} | {s['hc_wrong']['mean']:.1f} ± {s['hc_wrong']['std']:.1f} | {s['wrong_confidence']['mean']:.4f} |")
    lines += ['', '## 【Paired Comparison】','',
        '| ε vs 0 | Mean ΔVal Top1 | 95% bootstrap CI | Better | Equal | Worse |','|---:|---:|---:|---:|---:|---:|']
    for x in a['paired_comparison']:
        lines.append(f"| {x['epsilon']:.2f} | {pp(x['mean_delta'])} | [{pp(x['bootstrap_ci95'][0])}, {pp(x['bootstrap_ci95'][1])}] | {x['better']} | {x['equal']} | {x['worse']} |")
    lines += ['', '三个区间都跨 0。ε=0.10 的平均增益最大（+0.420pp），但仅 3/5 种子改善，仍小于种子波动，不能称为稳定提升。','',
        '## 【Generalization Gap】','',
        '| ε | Train−Val gap | 相对 ε=0 |','|---:|---:|---:|']
    base_gap=summaries[0.]['generalization_gap']['mean']
    for e in cfg['epsilons']:
        g=summaries[e]['generalization_gap']['mean'];lines.append(f'| {e:.2f} | {100*g:.3f}pp | {100*(g-base_gap):+.3f}pp |')
    lines += ['', 'Gap 没有压缩；正 ε 的 train fit 反而略高，validation 的变化较小。这里没有“牺牲训练准确率换验证泛化”的证据。','',
        '## 【Confidence Calibration】','',
        '| ε | HC Wrong | Wrong Confidence | ECE-10 | Brier |','|---:|---:|---:|---:|---:|']
    for e in cfg['epsilons']:
        s=summaries[e];lines.append(f"| {e:.2f} | {s['hc_wrong']['mean']:.1f} | {s['wrong_confidence']['mean']:.4f} | {s['ece10']['mean']:.4f} | {s['brier']['mean']:.4f} |")
    lines += ['', '错误置信度与高置信错误随 ε 单调下降；但正确预测置信度也下降，ECE 从 0.0257 增至 0.0828，表现为整体偏保守，而非校准全面改善。ε=0.10 的 wrong-confidence P95 从约 0.919 降至 0.841；正确预测 P95 也从约 0.989 降至 0.947。','',
        '## 【Teacher Rank】','',
        '| ε | Mean Rank | Δ vs 0 |','|---:|---:|---:|']
    for e in cfg['epsilons']:
        r=summaries[e]['mean_rank']['mean'];lines.append(f"| {e:.2f} | {r:.6f} | {r-summaries[0.]['mean_rank']['mean']:+.6f} |")
    lines += ['', '所有正 ε 的平均教师排名都比基线略差。ε=0.10 退化最小，但仍未满足“不恶化”门槛。','',
        '## 【Head / Medium / Tail】','',
        '| ε | Val Head (n=648) | Val Medium (n=89) | Val Tail (n=25) |','|---:|---:|---:|---:|']
    for e in cfg['epsilons']:
        vals=[aggregate_frequency(freq,e,'validation',b)[0] for b in ('head','medium','tail')]
        lines.append(f'| {e:.2f} | {pct(vals[0])} | {pct(vals[1])} | {pct(vals[2])} |')
    lines += ['', 'Medium 在 ε=0.05/0.10 上升约 2.47/2.25pp，但 Tail 低于基线，Head 基本持平。Tail 每种子仅 25 条，以上只作探索性观察；不符合 Frequency-Generalization 分支。','',
        '## 【Confusion Audit】','',
        '| ε | bar_of_soap→SKIP | goldfish→bar_of_soap |','|---:|---:|---:|']
    for e in cfg['epsilons']:
        soap=aggregate_confusion(conf,e,'bar_of_soap->SKIP');fish=aggregate_confusion(conf,e,'goldfish->bar_of_soap')
        lines.append(f'| {e:.2f} | {soap[0]:.1f} ± {soap[1]:.1f} | {fish[0]:.1f} ± {fish[1]:.1f} |')
    lines += ['', '这些主要混淆没有被一致消除；改善集中在部分 seed，不能单独支持晋升。完整 Top-10 见 `logs/v149-label-smoothing/confusions.json`。','',
        '## 【Candidate Gate】','',
        '| ε | Top1↑ | ≥4/5 non-lower | Rank不差 | CE≤+0.005 | HC Wrong↓ | Pass |','|---:|:---:|:---:|:---:|:---:|:---:|:---:|']
    for x in a['candidate_gate']:
        c=x['checks'];mark=lambda v:'✓' if v else '✗'
        lines.append(f"| {x['epsilon']:.2f} | {mark(c['mean_top1_strictly_higher'])} | {mark(c['at_least_four_non_lower'])} | {mark(c['mean_rank_not_worse'])} | {mark(c['standard_ce_not_clearly_worse'])} | {mark(c['hc_wrong_decreased'])} | **FAIL** |")
    lines += ['', '没有 ε 通过全部门槛；不选择 canonical seed，不晋升 checkpoint。','',
        '## 【32局 Online Smoke】','','**NOT TRIGGERED**。离线门槛失败，预注册在线种子 17000–17031 未消耗。','',
        '## 【结论】','','Label smoothing 能稳定压低错误置信度，但没有稳定提高 unseen development states 上的决策泛化。ε=0.05/0.10 的平均 Top1 略升，paired CI 仍跨 0，方向只有 2/5 与 3/5；三个正 ε 的教师排名和统一 hard CE 都退化。结果更接近“把分数整体压平”，不满足生产候选条件。','',
        '十个问题：','',
        '1. **没有**稳定提高 Validation Symbol Top1。','2. **没有有效的最小 ε**；三个候选均失败。','3. **是**，平均 HC Wrong 从 32.6 降至 27.6 / 22.0 / 14.2。','4. **是**，错误置信度从 0.6414 降至 0.6192 / 0.5988 / 0.5681。','5. **是**，所有正 ε 的 Mean Teacher Rank 均轻微恶化。','6. Medium 有探索性改善，Tail 没有改善，不能称为中长尾整体泛化提升。','7. **不是**；Train Accuracy 没下降，反而略升，gap 也扩大。','8. **没有**；所有 paired bootstrap 95% CI 跨 0。','9. **没有**触发 32 局 Online Smoke。','10. V150 应进入 **Weight Decay Audit**。','',
        '## 【V150决策】','','进入单变量 **Weight Decay Audit**，继续固定 500 updates、同一 5 seeds 和 hard-label 验证指标。不要细调 ε，也不要组合 label smoothing + weight decay；Label Smoothing 支线到此停止。','',
        '原始资产：`logs/v149-label-smoothing/`；机器报告：`reports/v149_label_smoothing_audit.json`。开发验证集从 V146 起已被多次观察，不是未触碰 holdout；test 继续 SEALED。']
    (ROOT/'reports/v149_label_smoothing_audit.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'report':'reports/v149_label_smoothing_audit.md','selected_epsilon':a['selected_epsilon'],'tests':568},ensure_ascii=False))

if __name__=='__main__':main()
