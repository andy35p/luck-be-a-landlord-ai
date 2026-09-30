"""Read complete episodes and assign seed groups without transition leakage."""
import gzip
import hashlib
import json
from math import isfinite
from luck_agent.env.rule_revision import validate_rule_identity


def split_for_seed(seed, salt="luck-behavior-v1"):
    bucket = int.from_bytes(hashlib.sha256(f"{salt}:{seed}".encode()).digest()[:8], "big") % 100
    return "train" if bucket < 80 else "validation" if bucket < 90 else "test"


def read_episodes(path):
    """Yield (header, episode). Bounded memory: one complete episode at a time.

    Structural validation only; semantic environment replay is a separate check.
    Truncated episodes are complete records and are explicitly labelled.
    """
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        header = json.loads(next(stream, "{}"))
        if header.get("type") != "header" or header.get("schema_version") != 1:
            raise ValueError("Unsupported or missing trajectory header")
        validate_rule_identity(header)
        seen, episode = set(), []
        for line in stream:
            r = json.loads(line)
            if r.get("type") != "transition" or type(r.get("episode_seed")) is not int:
                raise ValueError("Invalid transition identity")
            if episode and r["episode_seed"] != episode[0]["episode_seed"]:
                if not (episode[-1]["terminated"] or episode[-1]["truncated"]):
                    raise ValueError("Incomplete episode")
                yield header, episode
                episode = []
            if not episode:
                if r["episode_seed"] in seen:
                    raise ValueError("Duplicate episode seed")
                seen.add(r["episode_seed"])
            elif episode[-1]["terminated"] or episode[-1]["truncated"]:
                raise ValueError("Transition after episode ended")
            if r["step"] != len(episode):
                raise ValueError("Nonconsecutive step")
            if episode and episode[-1]["next_state"] != r["state"]:
                raise ValueError("Broken state continuity")
            actions = r["legal_actions"]
            if "teacher_action" in r and r["teacher_action"] not in actions:
                raise ValueError("Illegal teacher label")
            if not actions or r["action_mask"] != [True] * len(actions) or r["action"] not in actions:
                raise ValueError("Invalid legal action or candidate mask")
            if len({json.dumps(a, sort_keys=True) for a in actions}) != len(actions):
                raise ValueError("Duplicate candidate action")
            if not isfinite(r["reward"]):
                raise ValueError("Nonfinite reward")
            if (type(r["terminated"]) is not bool or type(r["truncated"]) is not bool
                    or (r["terminated"] and r["truncated"])
                    or r["terminated"] != r["next_state"]["is_terminal"]
                    or r["truncated"] != r["next_state"]["is_truncated"]):
                raise ValueError("Inconsistent termination flags")
            if r["state"]["is_terminal"] or r["state"]["is_truncated"]:
                raise ValueError("Action from an ended state")
            episode.append(r)
        if not episode or not (episode[-1]["terminated"] or episode[-1]["truncated"]):
            raise ValueError("Empty or incomplete trajectory")
        yield header, episode
