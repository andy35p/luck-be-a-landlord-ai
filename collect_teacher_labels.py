"""Collect frozen learner trajectories with separate same-state teacher labels."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import torch
from luck_agent.agents.candidate_model import CandidateModel, TorchScorer
from luck_agent.agents.candidate_agent import CandidateAgent
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.dataset import read_episodes, split_for_seed
from luck_agent.evaluation.trajectory import TrajectoryWriter, replay


def training_seeds(index, policy):
    selected={r["episode_seed"] for r in index["episodes"] if r["policy"]==policy and r["split"]=="train"}
    excluded={r["episode_seed"] for r in index["episodes"] if r["split"]!="train"}
    if not selected or selected & excluded or any(split_for_seed(s,index["salt"])!="train" for s in selected):
        raise ValueError("Invalid training seed selection")
    return sorted(selected)


def main():
    torch.set_num_threads(1)
    checkpoint=Path("logs/bc-smoke-20260922T132337693785Z/final.pt")
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    saved=torch.load(checkpoint,weights_only=True);spec=saved["spec"]
    index=json.loads(Path(spec["index"]).read_text());seeds=training_seeds(index,spec["teacher"])
    model=CandidateModel();model.load_state_dict(saved["state_dict"])
    learner=CandidateAgent(TorchScorer(model),rule_version="instance-coal-v1",scaler=saved["scaler"],index_path=spec["index"],policies=[spec["teacher"]])
    config=EnvConfig(floor=1,rule_version="instance-coal-v1");env=GameEnv(config)
    teacher=HeuristicAgent(env.catalog,coal_score_adjustment=-1.2)
    output=Path("logs")/("teacher-labels-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"));output.mkdir()
    path=output/"learner.jsonl.gz"
    manifest={"source_index":spec["index"],"source_index_sha256":hashlib.sha256(Path(spec["index"]).read_bytes()).hexdigest(),
        "checkpoint":str(checkpoint),"checkpoint_sha256":digest,"seeds":seeds,"split":"train",
        "teacher":spec["teacher"],"teacher_config":{"coal_score_adjustment":-1.2},
        "executed_action_field":"action","supervision_field":"teacher_action","training_updates":0,
        "source_hashes":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('luck_agent').rglob('*.py'))+[Path(__file__),Path('luck_agent/legacy/catalog.json')]}}
    counts=Counter();by_size={};episodes=[]
    with TrajectoryWriter(path,config,"bc_v037",policy_config={"checkpoint_sha256":digest,"teacher":spec["teacher"],"annotation":"teacher_action"}) as writer:
        for seed in seeds:
            state=env.reset(seed);step=0
            while not(state.is_terminal or state.is_truncated):
                actions=env.legal_actions();rng=env._engine.rng.getstate()
                executed=learner.choose(state,actions);label=teacher.choose(state,actions)
                if rng!=env._engine.rng.getstate():raise ValueError("Annotation changed environment RNG")
                next_state,reward,terminated,truncated,info=env.step(executed)
                writer(seed,step,state,actions,executed,reward,next_state,terminated,truncated,info,teacher_action=label)
                counts["transitions"]+=1;counts["decisions"]+=len(actions)>1;counts["disagreements"]+=executed!=label
                if state.decision_type=="symbol":
                    group=by_size.setdefault(str(len(state.symbols)),Counter())
                    group["total"]+=1
                    group["teacher_pick_model_skip"]+=int(label.action_type)==0 and int(executed.action_type)==1
                    group["teacher_skip_model_pick"]+=int(label.action_type)==1 and int(executed.action_type)==0
                state=next_state;step+=1
            episodes.append(dict(seed=seed,stage=state.rent_stage,steps=step,truncated=state.is_truncated))
    replay_result=replay(path)
    verified=0
    for _,episode in read_episodes(path):
        if episode[0]["episode_seed"] not in seeds:raise ValueError("Split leak")
        verified+=len(episode)
        if any("teacher_action" not in r for r in episode):raise ValueError("Missing labels")
    assert verified==counts["transitions"]
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==digest
    manifest["trajectory_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
    report={"counts":dict(counts),"replay":replay_result,"by_deck_size":by_size,"episodes":episodes,
            "no_validation_or_test_seeds":True,"all_teacher_labels_legal":True,"checkpoint_unchanged":True}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2))
    (output/"audit.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({"output":str(output),"counts":dict(counts),"replay":replay_result,"truncations":sum(r['truncated'] for r in episodes)},indent=2))


if __name__=="__main__":main()
