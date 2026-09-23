"""Observe the unchanged reroll policy before selecting a single-variable experiment."""
import argparse
from collections import Counter
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
from luck_agent.agents.reroll_agent import RerollConfig, RerollHeuristicAgent
from luck_agent.env.action import ActionType as T
from luck_agent.env.game_env import GameEnv


def classify(evidence: dict) -> str:
    gain = evidence["expected_offer_utility"] - evidence["current_utility"]
    if gain <= 0:
        return "no_positive_mean_gain"
    if gain <= evidence["token_cost_proxy"]:
        return "blocked_by_cost"
    if evidence["conservative_gain"] <= evidence["token_cost_proxy"]:
        return "blocked_by_uncertainty"
    return "reroll"


def distribution(values: list[float]) -> dict:
    if not values:
        return {"count":0}
    ordered=sorted(values)
    return {"count":len(values),"mean":statistics.mean(values),
            **{key:ordered[int(p*(len(ordered)-1))] for key,p in (("p10",.1),("median",.5),("p90",.9))}}


def run(games: int, seed_start: int, output: Path) -> dict:
    if games < 1:
        raise ValueError("games must be positive")
    output.mkdir(parents=True,exist_ok=True)
    env=GameEnv()
    agent=RerollHeuristicAgent(env.catalog)
    counts=Counter(); stages={}; observations=[]; episodes=[]
    for seed in range(seed_start,seed_start+games):
        state=env.reset(seed)
        used=0; had_token=False
        while not (state.is_terminal or state.is_truncated):
            actions=env.legal_actions()
            action=agent.choose(state,actions)
            if state.decision_type == "symbol":
                counts["symbol_decisions"]+=1
                counts["with_tokens" if state.reroll_tokens else "without_tokens"]+=1
            had_token |= state.reroll_tokens > 0
            evidence=agent.last_evidence
            if evidence is not None:
                reason=classify(evidence)
                counts[reason]+=1
                stages.setdefault(str(state.rent_stage),Counter())[reason]+=1
                observations.append({"seed":seed,"spin":state.spin_count,"stage":state.rent_stage,
                    "tokens":state.reroll_tokens,"current_utility":evidence["current_utility"],
                    "mean_gain":evidence["expected_offer_utility"]-evidence["current_utility"],
                    "conservative_gain":evidence["conservative_gain"],"cost":evidence["token_cost_proxy"],
                    "standard_error":evidence["standard_error"],"reason":reason,
                    "chosen_reroll":action.action_type==T.REROLL})
            used+=action.action_type==T.REROLL
            state=env.step(action)[0]
        episodes.append({"seed":seed,"stage":state.rent_stage,"tokens_remaining":state.reroll_tokens,
                         "had_token":had_token,"rerolls_used":used,"truncated":state.is_truncated})
    for name,rows in (("decisions",observations),("episodes",episodes)):
        with (output/f"{name}.csv").open("w",newline="",encoding="utf-8") as f:
            if rows:
                writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
    report={"games":games,"seed_start":seed_start,"counts":dict(counts),"by_stage":stages,
            "episodes_with_tokens":sum(r["had_token"] for r in episodes),
            "episodes_ending_with_tokens":sum(r["tokens_remaining"]>0 for r in episodes),
            "mean_stage":statistics.mean(r["stage"] for r in episodes),
            "truncations":sum(r["truncated"] for r in episodes),
            "distributions":{key:distribution([r[key] for r in observations]) for key in ("mean_gain","conservative_gain","cost","tokens")},
            "state_only_margin_sensitivity":{str(m):sum(r["conservative_gain"] > m+.5/max(1,r["tokens"]) for r in observations) for m in (.5,.25,0)},
            "limitation":"Sensitivity counts reuse observed states; they are not new-policy outcomes or causal effects."}
    (output/"diagnosis.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--games",type=int,default=300)
    parser.add_argument("--seed-start",type=int,default=0)
    args=parser.parse_args()
    output=Path("logs")/("v022-reroll-diagnosis-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True)
    sources=sorted(Path("luck_agent").rglob("*.py"))+sorted(Path("luck_agent").rglob("*.json"))
    manifest={"arguments":vars(args),"agent_config":asdict(RerollConfig()),"python":platform.python_version(),
              "source_data_hash":hashlib.sha256(b"".join(str(p).encode()+p.read_bytes() for p in sources)).hexdigest()}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(output),**run(args.games,args.seed_start,output)},indent=2))


if __name__=="__main__":
    main()
