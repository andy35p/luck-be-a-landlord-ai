"""Closed-loop wiring audit; intentionally uses a first-candidate scorer."""
import json
from pathlib import Path
from luck_agent.agents.candidate_agent import CandidateAgent, first_candidate_scores
from luck_agent.env.game_env import GameEnv, EnvConfig


def main():
    config=EnvConfig(floor=1,rule_version="instance-coal-v1")
    scaler=json.loads(Path("logs/preprocessing_v033/scaler.json").read_text())
    agent=CandidateAgent(first_candidate_scores,rule_version=config.rule_version,scaler=scaler,
        index_path="logs/coal_diagnosis/20260922T031250024070Z/split_index_v1.json",
        policies=["heuristic_coal_v029"])
    rows=[]
    for seed in range(100):
        live,reference=GameEnv(config),GameEnv(config)
        live.reset(seed);reference.reset(seed);decisions=0
        while not(live.state.is_terminal or live.state.is_truncated):
            before_rng=live._engine.rng.getstate()
            action=agent.choose(live.state,live.legal_actions())
            if before_rng!=live._engine.rng.getstate(): raise ValueError("Inference changed environment RNG")
            if live.step(action)!=reference.step(reference.legal_actions()[0]):
                raise ValueError(f"Closed-loop mismatch seed={seed} step={decisions}")
            decisions+=1
        rows.append({"seed":seed,"stage":live.state.rent_stage,"spins":live.state.spin_count,
                     "decisions":decisions,"truncated":live.state.is_truncated})
    report={"games":len(rows),"decisions":sum(r["decisions"] for r in rows),
            "truncated_games":sum(r["truncated"] for r in rows),"every_step_matches_direct_first_action":True,
            "environment_rng_unchanged_by_inference":True,"scaler":"logs/preprocessing_v033/scaler.json",
            "scorer":"first_candidate_scores; wiring audit only, not teacher or learned model", "episodes":rows}
    with Path("reports/v035_online_audit.json").open("x",encoding="utf-8") as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!="episodes"},indent=2))


if __name__=="__main__":main()
