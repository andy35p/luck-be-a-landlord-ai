"""Matched-update original-only vs teacher-labelled-state BC experiment."""
import csv
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import torch
from train_bc_smoke import offline, online
from luck_agent.agents.candidate_model import CandidateModel, tensor_batch, masked_bc_loss, TorchScorer
from luck_agent.agents.candidate_agent import CandidateAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.teacher_dataset import original_examples,load_teacher_examples,mixed_decision_batches,collate_supervision
from luck_agent.evaluation.preprocessing import scale_sample,validate_scaler
from luck_agent.evaluation.compare_reroll import paired_stats


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",default="configs/bc_aggregation_v1.json")
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    spec=json.loads(Path("configs/bc_smoke_v1.json").read_text())
    scaler=json.loads(Path(cfg["scaler"]).read_text());validate_scaler(scaler,cfg["index"],[cfg["teacher"]])
    original=original_examples(cfg["index"],cfg["teacher"])
    annotated=load_teacher_examples(cfg["annotated"],cfg["index"])
    pools=[[scale_sample(s,scaler) for s in p] for p in (original,annotated)]
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    output=Path("logs")/("bc-aggregation-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"));output.mkdir()
    files=sorted(Path("luck_agent").rglob("*.py"))+[Path(__file__),Path("train_bc_smoke.py"),Path(cfg["index"]),Path(cfg["scaler"]),Path(cfg["annotated"])/"manifest.json",Path(cfg["annotated"])/"learner.jsonl.gz",Path("luck_agent/legacy/catalog.json")]
    manifest={"protocol":cfg,"evaluation_spec":spec,"torch":torch.__version__,"hashes":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2))
    reports={};online_rows={};initial_state=None
    for role in ("baseline","candidate"):
        directory=output/role;directory.mkdir()
        torch.manual_seed(cfg["initialization_seed"]);model=CandidateModel()
        if initial_state is None:initial_state={k:v.clone() for k,v in model.state_dict().items()}
        elif not all(torch.equal(v,initial_state[k]) for k,v in model.state_dict().items()):raise ValueError("Initialization differs")
        optimizer=torch.optim.Adam(model.parameters(),lr=cfg["learning_rate"])
        loss_sum=0;source_counts=[0,0];trace=[]
        for step,selected in enumerate(mixed_decision_batches(*pools,steps=cfg["steps"],batch_size=cfg["batch_size"],seed=cfg["sampler_seed"],annotated_per_batch=cfg[role+"_annotated_per_batch"]),1):
            model.train();b=collate_supervision([s for _,s in selected]);t=tensor_batch(b)
            loss=masked_bc_loss(model(t),torch.tensor(b["label"]),t["candidates_mask"])
            if loss is None or not torch.isfinite(loss):raise ValueError("Invalid training loss")
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),cfg["gradient_clip"],error_if_nonfinite=True);optimizer.step()
            loss_sum+=loss.item()
            for source,_ in selected:source_counts[source]+=1
            if step%178==0:trace.append({"step":step,"cumulative_training_nll":loss_sum/step})
        result={"optimizer_steps":step,"sampled_decisions_by_source":source_counts,"training_trace":trace,
                "validation":offline(model,spec,scaler,"validation"),"test":offline(model,spec,scaler,"test")}
        checkpoint_spec={**spec,"aggregation_role":role,"aggregation_protocol":cfg,"checkpoint_selection":"final fixed update 534"}
        torch.save(dict(state_dict=model.state_dict(),spec=checkpoint_spec,scaler=scaler,encoder="coal-candidates-v1",updates=step),directory/"final.pt")
        restored=CandidateModel();restored.load_state_dict(torch.load(directory/"final.pt",weights_only=True)["state_dict"])
        assert all(torch.equal(v,restored.state_dict()[k]) for k,v in model.state_dict().items())
        result["checkpoint_roundtrip_exact"]=True
        agent=CandidateAgent(TorchScorer(restored),rule_version="instance-coal-v1",scaler=scaler,index_path=cfg["index"],policies=[cfg["teacher"]])
        rows,summary=online(agent,spec);result["online"]=summary;online_rows[role]=rows
        with (directory/"trained.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        (directory/"results.json").write_text(json.dumps(result,indent=2));reports[role]=result
        print(json.dumps({"role":role,"validation":result["validation"]["overall"],"online":summary}),flush=True)
    # Teacher is unchanged; regenerate once for the paired development seeds.
    env=GameEnv(EnvConfig(floor=1,rule_version="instance-coal-v1"))
    teacher_rows,teacher_summary=online(HeuristicAgent(env.catalog,coal_score_adjustment=-1.2),spec)
    for role in reports:
        with (output/role/"teacher.csv").open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(teacher_rows[0]));w.writeheader();w.writerows(teacher_rows)
    stats=paired_stats([{**r,"rerolls_used":0} for r in online_rows["baseline"]],[{**r,"rerolls_used":0} for r in online_rows["candidate"]],43,5000)
    for pair in stats["worst_pairs"]:pair.pop("rerolls_used")
    summary={"runs":reports,"paired":stats,"teacher":teacher_summary,"same_initialization":True,
             "scope":"matched 534 updates of 64 decision rows; development seeds, no independent validation"}
    (output/"comparison.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps({"output":str(output),"paired":stats},indent=2))


if __name__=="__main__":main()
