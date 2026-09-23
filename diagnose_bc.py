"""Frozen-checkpoint disagreement audit; never updates weights."""
import csv
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import torch
from luck_agent.agents.candidate_model import CandidateModel, TorchScorer
from luck_agent.agents.candidate_agent import CandidateAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.batching import CandidateEncoder, masked_argmax
from luck_agent.evaluation.preprocessing import scale_sample
from luck_agent.evaluation.dataset import read_episodes
from luck_agent.evaluation.trajectory import normalized


def classify_disagreement(state, expected, predicted, teacher):
    if expected == predicted: return "exact_match"
    if expected["action_type"] == predicted["action_type"] == 0:
        view=SimpleNamespace(catalog=teacher.catalog,deck=[s["symbol_id"] for s in state["symbols"]],
                             items=state["items"],coins=state["coins"],state=lambda:{"rent":state["current_rent"]})
        gap=teacher.prior.score_symbol(view,expected["target_id"])-teacher.prior.score_symbol(view,predicted["target_id"])
        return "equal_teacher_score" if abs(gap)<1e-9 else "lower_teacher_score" if gap>0 else "higher_teacher_score"
    if {expected["action_type"],predicted["action_type"]}=={0,1}:return "pick_skip_disagreement"
    return "other_disagreement"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",default="logs/bc-smoke-20260922T132337693785Z")
    parser.add_argument("--output",default="reports/v038_bc_diagnosis.json")
    args=parser.parse_args()
    torch.set_num_threads(1)
    root=Path(args.run)
    checkpoint=root/"final.pt";digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    saved=torch.load(checkpoint,weights_only=True);spec=saved["spec"]
    model=CandidateModel(deck_count=spec.get("deck_count",False));model.load_state_dict(saved["state_dict"]);scorer=TorchScorer(model)
    agent=CandidateAgent(scorer,rule_version="instance-coal-v1",scaler=saved["scaler"],index_path=spec["index"],policies=[spec["teacher"]])
    config=EnvConfig(floor=1,rule_version="instance-coal-v1")
    teacher=HeuristicAgent(GameEnv(config).catalog,coal_score_adjustment=-1.2)
    index=json.loads(Path(spec["index"]).read_text());encoder=CandidateEncoder()
    seeds={r["episode_seed"] for r in index["episodes"] if r["split"]=="test" and r["policy"]==spec["teacher"]}
    counts=Counter();confusion=Counter();examples=[]
    path=Path(index["source"])/(spec["teacher"]+".jsonl.gz")
    for _,episode in read_episodes(path):
        if episode[0]["episode_seed"] not in seeds:continue
        for r in episode:
            if r["state"]["decision_type"]!="symbol":continue
            sample=scale_sample(encoder.encode(r,spec["teacher"]),saved["scaler"])
            features={k:sample[k] for k in ("scalars","deck","items","candidates")}
            features["candidate_mask"]=r["action_mask"]
            predicted=r["legal_actions"][masked_argmax(scorer(features),r["action_mask"])]
            kind=classify_disagreement(r["state"],r["action"],predicted,teacher);counts[kind]+=1
            if kind!="exact_match":
                confusion[(r["action"]["target_id"] or "skip",predicted["target_id"] or "skip")]+=1
                if len(examples)<20:examples.append(dict(seed=r["episode_seed"],step=r["step"],kind=kind,teacher=r["action"],model=predicted,deck_size=len(r["state"]["symbols"])))
    def rows(name):return list(csv.DictReader((root/(name+".csv")).open()))
    trained,teachers=rows("trained"),rows("teacher")
    pairs=[dict(seed=int(a["seed"]),model_stage=int(a["stage"]),teacher_stage=int(b["stage"]),delta=int(a["stage"])-int(b["stage"])) for a,b in zip(trained,teachers)]
    assert [r["seed"] for r in trained]==[r["seed"] for r in teachers]
    worst=sorted(pairs,key=lambda r:(r["delta"],r["seed"]))[:5]
    for pair in worst:
        env=GameEnv(config);env.reset(pair["seed"]);disagreements=[];step=0
        while not(env.state.is_terminal or env.state.is_truncated):
            state=env.state;actions=env.legal_actions();chosen=agent.choose(state,actions);expected=teacher.choose(state,actions)
            if chosen!=expected:
                disagreements.append(dict(step=step,stage=state.rent_stage,spin=state.spin_count,
                    kind=classify_disagreement(normalized(state),normalized(expected),normalized(chosen),teacher),
                    model=normalized(chosen),teacher=normalized(expected),deck_size=len(state.symbols),coins=state.coins))
            env.step(chosen);step+=1
        if env.state.rent_stage!=pair["model_stage"]:raise ValueError("Frozen replay differs")
        pair.update(disagreement_count=len(disagreements),first_disagreements=disagreements[:10],
                    terminal_coins=env.state.coins,rent_due=env.state.current_rent)
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==digest
    report={"checkpoint_sha256":digest,"offline_test_symbol_counts":dict(counts),
        "confusions":[dict(teacher=a,model=b,count=n) for (a,b),n in confusion.most_common()],"examples":examples,
        "online_paired":dict(improved=sum(p["delta"]>0 for p in pairs),equal=sum(p["delta"]==0 for p in pairs),worse=sum(p["delta"]<0 for p in pairs)),
        "worst_pairs":worst,"training_updates":0,"limitation":"Teacher scores are heuristic preferences, not measured action values; differing actions alter subsequent paths."}
    with Path(args.output).open("x",encoding="utf-8") as f:json.dump(report,f,indent=2)
    print(json.dumps({k:report[k] for k in ('offline_test_symbol_counts','online_paired')},indent=2))


if __name__=="__main__":main()
