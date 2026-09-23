"""Frozen policy coverage audit by exact deck size, without retraining."""
import csv
import hashlib
import json
from pathlib import Path
import torch
from luck_agent.agents.candidate_model import CandidateModel, TorchScorer
from luck_agent.agents.candidate_agent import CandidateAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.batching import CandidateEncoder, masked_argmax
from luck_agent.evaluation.preprocessing import scale_sample


def tally(table, size, teacher_type, model_type=None):
    row=table.setdefault(str(size),dict(total=0,teacher_pick=0,teacher_skip=0,model_skip_teacher_pick=0,model_pick_teacher_skip=0))
    if teacher_type not in (0,1):raise ValueError("Expected symbol pick or skip")
    row["total"]+=1;row["teacher_pick" if teacher_type==0 else "teacher_skip"]+=1
    if model_type is not None:
        row["model_skip_teacher_pick"]+=teacher_type==0 and model_type==1
        row["model_pick_teacher_skip"]+=teacher_type==1 and model_type==0


def main():
    torch.set_num_threads(1)
    runs={"baseline":"logs/bc-smoke-20260922T132337693785Z","count":"logs/bc-smoke-20260922T134741620666Z"}
    report={"runs":{},"training_updates":0}
    env_config=EnvConfig(floor=1,rule_version="instance-coal-v1")
    teacher=HeuristicAgent(GameEnv(env_config).catalog,coal_score_adjustment=-1.2)
    encoder=CandidateEncoder()
    for name,run in runs.items():
        path=Path(run)/"final.pt";digest=hashlib.sha256(path.read_bytes()).hexdigest()
        saved=torch.load(path,weights_only=True);spec=saved["spec"]
        model=CandidateModel(deck_count=spec.get("deck_count",False));model.load_state_dict(saved["state_dict"])
        scorer=TorchScorer(model)
        agent=CandidateAgent(scorer,rule_version="instance-coal-v1",scaler=saved["scaler"],index_path=spec["index"],policies=[spec["teacher"]])
        index=json.loads(Path(spec["index"]).read_text())
        split_by_seed={r["episode_seed"]:r["split"] for r in index["episodes"] if r["policy"]==spec["teacher"]}
        offline={split:{} for split in ("train","validation","test")}
        for _,episode in read_episodes(Path(index["source"])/(spec["teacher"]+".jsonl.gz")):
            split=split_by_seed[episode[0]["episode_seed"]]
            for r in episode:
                if r["state"]["decision_type"]!="symbol":continue
                sample=scale_sample(encoder.encode(r,spec["teacher"]),saved["scaler"])
                f={k:sample[k] for k in ("scalars","deck","items","candidates")};f["candidate_mask"]=r["action_mask"]
                predicted=r["legal_actions"][masked_argmax(scorer(f),r["action_mask"])]
                tally(offline[split],len(r["state"]["symbols"]),r["action"]["action_type"],predicted["action_type"])
        online={};episodes=[]
        expected={int(r["seed"]):r for r in csv.DictReader((Path(run)/"trained.csv").open())}
        for seed in sorted(expected):
            env=GameEnv(env_config);env.reset(seed);mismatches=0
            while not(env.state.is_terminal or env.state.is_truncated):
                s=env.state;actions=env.legal_actions();chosen=agent.choose(s,actions)
                if s.decision_type=="symbol":
                    target=teacher.choose(s,actions)
                    tally(online,len(s.symbols),int(target.action_type),int(chosen.action_type))
                    mismatches+= {int(target.action_type),int(chosen.action_type)}=={0,1}
                env.step(chosen)
            if env.state.rent_stage!=int(expected[seed]["stage"]) or env.state.spin_count!=int(expected[seed]["spins"]):raise ValueError("Replay changed")
            episodes.append(dict(seed=seed,stage=env.state.rent_stage,pick_skip_disagreements=mismatches))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError("Checkpoint changed")
        report["runs"][name]={"checkpoint_sha256":digest,"offline_by_size":offline,"online_by_size":online,"episodes":episodes}
    with Path("reports/v040_threshold_coverage.json").open("x") as f:json.dump(report,f,indent=2)
    for name,data in report["runs"].items():
        print(name)
        for label,table in [("train",data["offline_by_size"]["train"]),("online",data["online_by_size"])]:
            print(label, json.dumps({str(lo)+"-"+str(hi):{k:sum(v[k] for n,v in table.items() if lo<=int(n)<=hi) for k in next(iter(table.values()))} for lo,hi in [(0,17),(18,19),(20,21),(22,999)]}))


if __name__=="__main__":main()
