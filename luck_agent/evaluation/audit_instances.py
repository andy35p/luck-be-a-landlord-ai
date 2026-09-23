"""Executable representation-loss witnesses and the new instance contract.

This is a migration audit, not an original-game oracle or a new complete engine.
"""
import hashlib
import json
from pathlib import Path
from luck_agent.env.game_env import GameEnv
from luck_agent.env.action import Action, ActionType as T
from luck_agent.env.instance_store import InstanceStore
from luck_agent.env.rule_engine import load_catalog
from luck_agent.legacy.fast_env import FastLandlordEnv


def audit() -> dict:
    catalog=load_catalog()
    env=FastLandlordEnv(catalog,seed=7,floor=1)
    env.deck=["archaeologist","pearl","coin","coin","archaeologist"]
    env.pending_shown=env.deck.copy()
    env.spins_left=100
    env.spin()
    shared=env.permanent_bonuses["archaeologist"]
    if shared != 1:
        raise AssertionError("Growth witness no longer matches legacy rules")
    store=InstanceStore(set(catalog["symbol_pool"]))
    first=store.add("archaeologist");second=store.add("archaeologist")
    store.add_bonus(first.instance_id,1)
    growth={"legacy_shared_bonus":shared,"legacy_bonus_applied_to_two_copies":2*shared,
            "instance_bonuses":[store.get(first.instance_id).permanent_bonus,store.get(second.instance_id).permanent_bonus],
            "explanation":"One observed actor triggers growth, but the legacy type-keyed bonus applies to both copies."}

    # The old shown=['spirit'] cannot encode which of two copies was selected.
    timer=FastLandlordEnv(catalog,seed=8,floor=1)
    timer.deck=["spirit","spirit"];timer.spirit_ttls=[1,4]
    timer.pending_shown=["spirit"];timer.spins_left=100
    timer.spin()
    precise=InstanceStore(set(catalog["symbol_pool"]))
    old=precise.add("spirit",remaining_appearances=1)
    fresh=precise.add("spirit",remaining_appearances=4)
    precise.tick((fresh.instance_id,))
    timers={"legacy_input_ttls":[1,4],"legacy_shown":["spirit"],
            "legacy_remaining_ttls":timer.spirit_ttls,
            "specified_second_instance_shown":fresh.instance_id,
            "instance_remaining_ttls":[precise.get(old.instance_id).remaining_appearances,precise.get(fresh.instance_id).remaining_appearances],
            "explanation":"Legacy data cannot specify second-copy selection; the instance contract can. Not an inferred hidden board identity."}

    game=GameEnv();game._engine.deck=["coin","coin"];game._engine.removals=1;game._phase="remove"
    before=[s.instance_id for s in game.state.symbols]
    game.step(Action(T.REMOVE_SYMBOL,"coin:0"))
    after=[s.instance_id for s in game.state.symbols]
    ids=InstanceStore(set(catalog["symbol_pool"]))
    a,b=ids.add("coin"),ids.add("coin")
    ids.remove(a.instance_id)
    identity={"legacy_before":before,"legacy_after":after,
              "instance_before":[a.instance_id,b.instance_id],"instance_after":[s.instance_id for s in ids.snapshot()],
              "explanation":"Legacy snapshot indices are renumbered; instance IDs of survivors remain unchanged."}
    return {"growth":growth,"timers":timers,"identity":identity,
            "integration_status":"InstanceStore is tested migration infrastructure, not yet the live game backend.",
            "next_gate":"Migrate one rule with explicit board IDs, actor/target events and state parity tests; never reconstruct post-spin identity by matching type strings."}


def main() -> None:
    report=audit()
    core=Path(__file__).resolve().parents[1]/"legacy/fast_env.py"
    report["legacy_core_sha256"]=hashlib.sha256(core.read_bytes()).hexdigest()
    output=Path("reports/v024_instance_audit.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
