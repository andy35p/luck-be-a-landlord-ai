"""Decision opportunity, selection and BC teacher-disagreement summaries."""
import hashlib
import json
from dataclasses import asdict

from luck_agent.env.action import ActionType
from luck_agent.evaluation.trajectory import normalized


def new_diagnostics(agent_metadata):
    return {
        "agent_metadata": dict(agent_metadata),
        "coverage": {kind.name: {"available_count": 0, "chosen_count": 0,
                                  "illegal_count": 0} for kind in ActionType},
        "bc_by_decision_type": {},
        "high_confidence_errors": [],
        "inference": {"decisions": 0, "seconds": 0.0},
    }


def record_decision(result, *, seed, step, state, actions, chosen, policy=None, teacher=None):
    available_types = {action.action_type for action in actions}
    for kind in available_types:
        result["coverage"][kind.name]["available_count"] += 1
    legal = chosen in actions
    result["coverage"][chosen.action_type.name]["chosen_count"] += 1
    if not legal:
        result["coverage"][chosen.action_type.name]["illegal_count"] += 1
    if policy is None:
        return legal

    result["inference"]["decisions"] += 1
    result["inference"]["seconds"] += policy["latency_seconds"]
    group = result["bc_by_decision_type"].setdefault(state.decision_type, {
        "total_decisions": 0, "multi_action_decisions": 0, "teacher_agreement_count": 0,
        "teacher_disagreement_count": 0, "high_confidence_errors": 0,
        "confidence_sum": 0.0, "margin_sum": 0.0, "margin_count": 0,
    })
    group["total_decisions"] += 1
    if len(actions) <= 1:
        return legal
    group["multi_action_decisions"] += 1
    group["confidence_sum"] += policy["top1_confidence"]
    if policy["score_margin"] is not None:
        group["margin_sum"] += policy["score_margin"]
        group["margin_count"] += 1
    if teacher is not None:
        agreement = chosen == teacher
        group["teacher_agreement_count" if agreement else "teacher_disagreement_count"] += 1
        if not agreement and policy["top1_confidence"] >= .8:
            group["high_confidence_errors"] += 1
            state_json = json.dumps(normalized(state), sort_keys=True, separators=(",", ":"))
            result["high_confidence_errors"].append({
                "state_id": hashlib.sha256(state_json.encode()).hexdigest(),
                "episode": seed, "step": step, "spin": state.spin_count,
                "decision_type": state.decision_type,
                "legal_actions": [asdict(action) for action in actions],
                "bc_choice": asdict(chosen), "teacher_choice": asdict(teacher),
                "top1_confidence": policy["top1_confidence"],
                "score_margin": policy["score_margin"],
            })
    return legal


def finish_episode(result, start_error_index, *, reward, stage, won):
    for error in result["high_confidence_errors"][start_error_index:]:
        error.update(eventual_episode_return=reward, final_stage=stage, won=bool(won))


def merge_diagnostics(parts):
    if not parts:
        return None
    result = new_diagnostics(parts[0]["agent_metadata"])
    for part in parts:
        if part["agent_metadata"] != result["agent_metadata"]:
            raise ValueError("Cannot merge different policy diagnostics")
        for kind, counts in part["coverage"].items():
            for key, value in counts.items():
                result["coverage"][kind][key] += value
        for phase, counts in part["bc_by_decision_type"].items():
            target = result["bc_by_decision_type"].setdefault(phase, {key: 0 for key in counts})
            for key, value in counts.items():
                target[key] += value
        result["high_confidence_errors"].extend(part["high_confidence_errors"])
        for key in result["inference"]:
            result["inference"][key] += part["inference"][key]
    return result


def finalize_diagnostics(result):
    for counts in result["coverage"].values():
        opportunities = counts["available_count"]
        counts["chosen_rate"] = counts["chosen_count"] / opportunities if opportunities else None
        counts["status"] = ("never_available" if not opportunities else
                            "available_never_selected" if not counts["chosen_count"] else "selected")
    for counts in result["bc_by_decision_type"].values():
        multi = counts["multi_action_decisions"]
        labelled = counts["teacher_agreement_count"] + counts["teacher_disagreement_count"]
        counts["teacher_agreement"] = counts["teacher_agreement_count"] / labelled if labelled else None
        confidence_sum = counts.pop("confidence_sum")
        counts["average_top1_confidence"] = confidence_sum / multi if multi else None
        margin_count = counts.pop("margin_count")
        margin_sum = counts.pop("margin_sum")
        counts["average_score_margin"] = margin_sum / margin_count if margin_count else None
    decisions = result["inference"]["decisions"]
    result["inference"]["mean_decision_latency_seconds"] = (
        result["inference"]["seconds"] / decisions if decisions else None)
    return result
