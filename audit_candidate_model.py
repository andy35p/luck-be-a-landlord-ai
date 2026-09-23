"""Untrained forward/loss/inference audit. Never constructs an optimizer."""
import json
from pathlib import Path
import torch
from luck_agent.agents.candidate_model import CandidateModel, tensor_batch, masked_bc_loss, TorchScorer
from luck_agent.agents.candidate_agent import CandidateAgent
from luck_agent.env.game_env import GameEnv, EnvConfig
from luck_agent.evaluation.batching import iter_batches
from luck_agent.evaluation.bc_contract import masked_bc_metrics


def main():
    torch.set_num_threads(1);torch.manual_seed(36)
    index="logs/coal_diagnosis/20260922T031250024070Z/split_index_v1.json"
    scaler=json.loads(Path("logs/preprocessing_v033/scaler.json").read_text())
    model=CandidateModel().eval();before={k:v.clone() for k,v in model.state_dict().items()}
    batches=rows=0; max_error=0
    for batch in iter_batches(index,split="train",policies=["heuristic_coal_v029"],scaler=scaler):
        tensors=tensor_batch(batch)
        with torch.no_grad():
            logits=model(tensors)
            loss=masked_bc_loss(logits,torch.tensor(batch["label"]),tensors["candidates_mask"])
        reference=masked_bc_metrics(logits.tolist(),batch["label"],batch["candidates_mask"])
        if loss is not None:
            error=abs(loss.item()-reference["mean_nll"]);max_error=max(max_error,error)
            if error>1e-5:raise ValueError("Loss disagrees with reference")
        elif reference["decision_count"]:raise ValueError("Missing decision loss")
        batches+=1;rows+=len(batch["label"])
    agent=CandidateAgent(TorchScorer(model),rule_version="instance-coal-v1",scaler=scaler,index_path=index,policies=["heuristic_coal_v029"])
    episodes=[]
    for seed in range(10):
        env=GameEnv(EnvConfig(floor=1,rule_version="instance-coal-v1"));env.reset(seed);decisions=0
        while not(env.state.is_terminal or env.state.is_truncated):
            rng=env._engine.rng.getstate();action=agent.choose(env.state,env.legal_actions())
            if rng!=env._engine.rng.getstate():raise ValueError("Inference changed RNG")
            env.step(action);decisions+=1
        episodes.append({"seed":seed,"decisions":decisions,"truncated":env.state.is_truncated})
    assert all(torch.equal(before[k],v) for k,v in model.state_dict().items())
    report={"torch":torch.__version__,"parameters":sum(p.numel() for p in model.parameters()),
        "batches":batches,"rows":rows,"max_loss_error":max_error,"episodes":episodes,
        "weights_unchanged":True,"optimizer_steps":0,"initialization_seed":36}
    with Path("reports/v036_model_audit.json").open("x") as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
