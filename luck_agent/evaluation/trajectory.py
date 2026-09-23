"""Versioned public-observation transitions; engine RNG is never serialized."""
import gzip
import json
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from luck_agent.env.action import Action, ActionType
from luck_agent.env.game_env import GameEnv, EnvConfig


def normalized(value):
    # dataclasses.asdict reconstructs Counter from (key, value) pairs, which
    # creates tuple keys. Traverse mappings directly to preserve real counts.
    if is_dataclass(value):
        return {f.name: normalized(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {str(k): normalized(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalized(v) for v in value]
    return value


class TrajectoryWriter:
    def __init__(self, path, config, agent, *, policy_config=None):
        self.path = Path(path)
        self.stream = gzip.open(self.path, "xt", encoding="utf-8")
        self.write({"type": "header", "schema_version": 1,
                    "config": asdict(config), "agent": agent,
                    "policy_config": policy_config or {},
                    "identity_key": ["episode_seed", "instance_id"]})

    def write(self, record):
        self.stream.write(json.dumps(record, sort_keys=True) + "\n")

    def __call__(self, seed, step, state, actions, action, reward, next_state,
                 terminated, truncated, info, *, teacher_action=None):
        if teacher_action is not None and teacher_action not in actions:
            raise ValueError("Teacher label must be legal in the pre-action state")
        record = {"type": "transition", "episode_seed": seed, "step": step,
                    "state": normalized(state), "legal_actions": [asdict(a) for a in actions],
                    "action_mask": [True] * len(actions), "action": asdict(action),
                    "reward": reward, "next_state": normalized(next_state),
                    "terminated": terminated, "truncated": truncated, "info": info}
        if teacher_action is not None:
            record["teacher_action"] = asdict(teacher_action)
        self.write(record)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()


def replay(path):
    """Reexecute recorded actions and compare every public transition exactly."""
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        header = json.loads(next(stream))
        if header.get("schema_version") != 1:
            raise ValueError("Unsupported trajectory schema")
        env = GameEnv(EnvConfig(**header["config"]))
        seed = None
        count = episodes = expected_step = 0
        finished = True
        for line in stream:
            record = json.loads(line)
            if record["episode_seed"] != seed:
                if not finished:
                    raise ValueError("Incomplete episode")
                seed = record["episode_seed"]
                env.reset(seed); episodes += 1; expected_step = 0
            if record["step"] != expected_step:
                raise ValueError("Nonconsecutive transition")
            checks = {"state": normalized(env.state),
                      "legal_actions": [asdict(a) for a in env.legal_actions()],
                      "action_mask": [True] * len(env.legal_actions())}
            action = dict(record["action"])
            action["action_type"] = ActionType(action["action_type"])
            state, reward, terminated, truncated, info = env.step(Action(**action))
            checks.update(next_state=normalized(state), reward=reward, terminated=terminated,
                          truncated=truncated, info=info)
            for key, value in checks.items():
                # Additive observation field introduced after schema-1 traces.
                # Omit only when absent in the saved state; still verify all old fields.
                if key in {"state", "next_state"} and "visible_board_cells" not in record[key]:
                    value = {k:v for k,v in value.items() if k != "visible_board_cells"}
                if normalized(value) != record[key]:
                    raise ValueError(f"Replay mismatch: seed={seed} step={expected_step} field={key}")
            finished = terminated or truncated
            count += 1; expected_step += 1
        if not finished or not episodes:
            raise ValueError("Empty or incomplete trajectory")
        return {"episodes": episodes, "transitions": count, "exact_replay": True}
