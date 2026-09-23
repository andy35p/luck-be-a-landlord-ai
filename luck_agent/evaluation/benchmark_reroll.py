"""Exact action/evidence gate followed by alternating-order timing repetitions."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
from luck_agent.agents.reroll_agent import RerollHeuristicAgent, RerollConfig
from luck_agent.env.game_env import GameEnv


def validate(games: int) -> dict:
    env=GameEnv()
    reference=RerollHeuristicAgent(env.catalog,sampler_backend="reference")
    prepared=RerollHeuristicAgent(env.catalog,sampler_backend="prepared")
    decisions=estimates=rerolls=0
    stages=[]
    for seed in range(games):
        state=env.reset(seed)
        while not (state.is_terminal or state.is_truncated):
            legal=env.legal_actions()
            expected=reference.choose(state,legal)
            actual=prepared.choose(state,legal)
            if actual != expected or reference.last_evidence != prepared.last_evidence:
                raise AssertionError(f"Action/evidence mismatch at seed {seed}, spin {state.spin_count}")
            estimates += reference.last_evidence is not None
            rerolls += actual.action_type.name == "REROLL"
            decisions += 1
            state=env.step(actual)[0]
        if state.is_truncated:
            raise AssertionError(f"Truncated episode {seed}")
        stages.append(state.rent_stage)
    return {"games":games,"decisions_compared":decisions,"estimates_compared":estimates,
            "rerolls":rerolls,"mean_stage":statistics.mean(stages),"mismatches":0}


def timed_run(backend: str, games: int) -> dict:
    env=GameEnv()
    agent=RerollHeuristicAgent(env.catalog,sampler_backend=backend)
    outcomes=[]
    start=time.perf_counter()
    for seed in range(games):
        state=env.reset(seed)
        decisions=0
        while not (state.is_terminal or state.is_truncated):
            action=agent.choose(state,env.legal_actions())
            state=env.step(action)[0]
            decisions+=1
        outcomes.append((seed,state.rent_stage,state.spin_count,state.coins,state.won,state.is_truncated,decisions))
    elapsed=time.perf_counter()-start
    return {"backend":backend,"games":games,"seconds":elapsed,"episodes_per_second":games/elapsed,
            "outcome_hash":hashlib.sha256(json.dumps(outcomes).encode()).hexdigest()}


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--validation-games",type=int,default=300)
    parser.add_argument("--timing-games",type=int,default=100)
    parser.add_argument("--repeats",type=int,default=3)
    args=parser.parse_args()
    if min(args.validation_games,args.timing_games,args.repeats)<1:
        parser.error("All counts must be positive")
    root=Path(__file__).resolve().parents[2]
    output=root/"logs"/("v02-sampler-speed-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True)
    sources=sorted((root/"luck_agent").rglob("*.py"))+sorted((root/"luck_agent").rglob("*.json"))
    manifest={"arguments":vars(args),"reroll_config":asdict(RerollConfig()),"python":platform.python_version(),
              "seed_start":0,"source_data_hash":hashlib.sha256(b"".join(str(p.relative_to(root)).encode()+p.read_bytes() for p in sources)).hexdigest(),
              "success_gate":"zero exact evidence/action mismatches and median speedup > 1.1",
              "scope":"All seeds are development seeds; no training or strategy threshold changes."}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("Validating exact evidence and actions...",flush=True)
    validation=validate(args.validation_games)
    print(json.dumps(validation),flush=True)
    timings=[]
    # Warm both paths before measuring. Alternate ordering to reduce timing bias.
    for backend in ("reference","prepared"):
        timed_run(backend,2)
    for repeat in range(args.repeats):
        order=("reference","prepared") if repeat%2==0 else ("prepared","reference")
        for backend in order:
            result=timed_run(backend,args.timing_games)
            result["repeat"]=repeat
            timings.append(result)
            print(json.dumps(result),flush=True)
    if len({r["outcome_hash"] for r in timings}) != 1:
        raise AssertionError("Timed-run outcomes differ")
    medians={b:statistics.median(r["seconds"] for r in timings if r["backend"]==b) for b in ("reference","prepared")}
    speedup=medians["reference"]/medians["prepared"]
    report={"output":str(output),"validation":validation,"timings":timings,
            "median_seconds":medians,"median_speedup":speedup,
            "accepted":validation["mismatches"]==0 and speedup>1.1}
    (output/"benchmark.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
