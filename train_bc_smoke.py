"""Fixed-budget BC experiment with reference metrics and closed-loop controls."""
import csv
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import torch
from luck_agent.agents.candidate_model import CandidateModel, tensor_batch, masked_bc_loss, TorchScorer
from luck_agent.agents.candidate_agent import CandidateAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.batching import iter_batches
from luck_agent.evaluation.bc_contract import masked_bc_metrics


def offline(model, spec, scaler, split):
    model.eval(); phases={}
    with torch.no_grad():
        for batch in iter_batches(spec["index"],split=split,policies=[spec["teacher"]],scaler=scaler,batch_size=spec["batch_size"]):
            scores=model(tensor_batch(batch)).tolist()
            for row,label,mask,meta in zip(scores,batch["label"],batch["candidates_mask"],batch["metadata"]):
                m=masked_bc_metrics([row],[label],[mask])
                target=phases.setdefault(meta["decision_type"],dict(decision_count=0,correct_count=0,loss_sum=0.0,forced_count=0))
                for k in target: target[k]+=m[k]
    overall={k:sum(v[k] for v in phases.values()) for k in ("decision_count","correct_count","loss_sum","forced_count")}
    for v in [overall,*phases.values()]:
        n=v["decision_count"];v["accuracy"]=v["correct_count"]/n if n else None;v["nll"]=v["loss_sum"]/n if n else None
    return {"overall":overall,"phases":phases}


def online(agent, spec):
    env=GameEnv(EnvConfig(floor=1,rule_version="instance-coal-v1"));rows=[]
    for seed in range(spec["online_seed_start"],spec["online_seed_start"]+spec["online_games"]):
        state=env.reset(seed);steps=0
        while not(state.is_terminal or state.is_truncated):
            state,*_=env.step(agent.choose(state,env.legal_actions()));steps+=1
        rows.append(dict(seed=seed,stage=state.rent_stage,spins=state.spin_count,won=int(state.won),truncated=int(state.is_truncated),decisions=steps))
    n=len(rows)
    return rows,{"games":n,"average_stage":sum(r["stage"] for r in rows)/n,
        "third_rent_survival":sum(r["stage"]>=3 for r in rows)/n,
        "wins":sum(r["won"] for r in rows),"truncations":sum(r["truncated"] for r in rows)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",default="configs/bc_smoke_v1.json")
    args=parser.parse_args()
    spec=json.loads(Path(args.config).read_text())
    scaler=json.loads(Path(spec["scaler"]).read_text())
    torch.set_num_threads(1);torch.manual_seed(spec["seed"]);torch.use_deterministic_algorithms(True)
    model=CandidateModel(deck_count=spec.get("deck_count",False));initial=CandidateModel(deck_count=spec.get("deck_count",False));initial.load_state_dict(model.state_dict())
    output=Path("logs")/("bc-smoke-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"));output.mkdir()
    sources=sorted(Path("luck_agent").rglob("*.py"))+[Path(__file__),Path(spec["index"]),Path(spec["scaler"]),Path("luck_agent/legacy/catalog.json")]
    manifest={"spec":spec,"torch":torch.__version__,"sha256":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2))
    report={"initial_validation":offline(initial,spec,scaler,"validation"),"epochs":[]}
    optimizer=torch.optim.Adam(model.parameters(),lr=spec["learning_rate"]);updates=0
    for epoch in range(spec["epochs"]):
        model.train();weighted_loss=0;count=0
        for b in iter_batches(spec["index"],split="train",policies=[spec["teacher"]],scaler=scaler,
                              batch_size=spec["batch_size"],shuffle_seed=spec["shuffle_seed"],epoch=epoch):
            tensors=tensor_batch(b);logits=model(tensors)
            loss=masked_bc_loss(logits,torch.tensor(b["label"]),tensors["candidates_mask"])
            if loss is None:continue
            if not torch.isfinite(loss):raise ValueError("Nonfinite loss")
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0,error_if_nonfinite=True);optimizer.step()
            n=int((tensors["candidates_mask"].sum(1)>1).sum());weighted_loss+=loss.item()*n;count+=n;updates+=1
        result={"epoch":epoch+1,"online_training_nll":weighted_loss/count,"decisions":count,
                "validation":offline(model,spec,scaler,"validation")}
        report["epochs"].append(result)
        print(json.dumps({"epoch":epoch+1,"training_nll":weighted_loss/count,"validation":result["validation"]["overall"]}),flush=True)
    report["final_train"]=offline(model,spec,scaler,"train")
    report["final_test"]=offline(model,spec,scaler,"test")
    checkpoint={"state_dict":model.state_dict(),"spec":spec,"scaler":scaler,"encoder":"coal-candidates-v1","updates":updates}
    torch.save(checkpoint,output/"final.pt")
    restored=CandidateModel(deck_count=spec.get("deck_count",False));restored.load_state_dict(torch.load(output/"final.pt",weights_only=True)["state_dict"])
    if not all(torch.equal(v,restored.state_dict()[k]) for k,v in model.state_dict().items()):raise ValueError("Checkpoint mismatch")
    report["checkpoint_roundtrip_exact"]=True;report["optimizer_steps"]=updates;report["online"]={}
    env=GameEnv(EnvConfig(floor=1,rule_version="instance-coal-v1"))
    for name,agent in [("initial",CandidateAgent(TorchScorer(initial),rule_version="instance-coal-v1",scaler=scaler,index_path=spec["index"],policies=[spec["teacher"]])),
                       ("trained",CandidateAgent(TorchScorer(restored),rule_version="instance-coal-v1",scaler=scaler,index_path=spec["index"],policies=[spec["teacher"]])),
                       ("teacher",HeuristicAgent(env.catalog,coal_score_adjustment=-1.2))]:
        rows,summary=online(agent,spec);report["online"][name]=summary
        with (output/(name+".csv")).open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        print(json.dumps({name:summary}),flush=True)
    (output/"results.json").write_text(json.dumps(report,indent=2))
    print("Output:",output)


if __name__=="__main__":main()
