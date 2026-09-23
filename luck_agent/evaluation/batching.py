"""Stdlib-only candidate batches for the bounded instance-coal-v1 dataset."""
import hashlib
import json
from pathlib import Path
from luck_agent.env.instance_coal_engine import coal_catalog
from luck_agent.env.rule_engine import load_catalog
from luck_agent.evaluation.dataset import read_episodes, split_for_seed


class CandidateEncoder:
    version = "coal-candidates-v1"
    scalar_fields = ("coins", "current_rent", "spins_until_rent", "rent_stage",
                     "reroll_tokens", "removal_tokens", "last_spin_income", "spin_count")

    def __init__(self):
        catalog = coal_catalog(load_catalog())
        # Zero is padding, never a real symbol/item/type.
        self.symbols = {s: i+1 for i, s in enumerate(sorted(catalog["symbol_pool"]))}
        self.items = {s: i+1 for i, s in enumerate(sorted(catalog["item_pool"]))}

    def encode(self, record, policy):
        if "teacher_action" in record:
            raise ValueError("Annotated learner data requires an explicit supervision adapter")
        sample = self.encode_observation(record["state"], record["legal_actions"])
        if record["action_mask"] != [True]*len(record["legal_actions"]):
            raise ValueError("Expected legal candidate mask")
        sample.update(label=record["legal_actions"].index(record["action"]),
                      reward=record["reward"], terminated=record["terminated"], truncated=record["truncated"])
        sample["metadata"].update(policy=policy, seed=record["episode_seed"], step=record["step"])
        return sample

    def encode_observation(self, state, actions):
        if not state["supports_stable_instances"]:
            raise ValueError("Encoder requires stable instances")
        ids = {s["instance_id"]: i for i, s in enumerate(state["symbols"])}
        if len(ids) != len(state["symbols"]):
            raise ValueError("Duplicate instance identity")
        deck = [[self.symbols[s["symbol_id"]], s["permanent_bonus"],
                 s["remaining_appearances"] or 0, int(s["remaining_appearances"] is not None)]
                for s in state["symbols"]]
        candidates = []
        for a in actions:
            t, target = a["action_type"], a["target_id"]
            if a["secondary_target_id"] is not None:
                raise ValueError("Secondary interactions are not encoded in this scope")
            # [type+1, target symbol token, target item token, deck pointer+1]
            row = [t+1, 0, 0, 0]
            if t == 0: row[1] = self.symbols[target]
            elif t == 2: row[2] = self.items[target]
            elif t == 4:
                i = ids[target]; row[1] = deck[i][0]; row[3] = i+1
            elif t not in (1, 3, 5, 7, 8) or target is not None:
                raise ValueError("Unsupported action")
            candidates.append(row)
        if not candidates:
            raise ValueError("Expected nonempty legal candidate list")
        return {"scalars": [state[k] for k in self.scalar_fields], "deck": deck,
                "items": [self.items[x] for x in state["items"]], "candidates": candidates,
                "metadata": {"decision_type": state["decision_type"], "instance_ids": list(ids),
                             "actions": actions}}


def collate(samples):
    if not samples: raise ValueError("Empty batch")
    result = {k: [s[k] for s in samples] for k in
              ("scalars", "label", "reward", "terminated", "truncated", "metadata")}
    for key, pad in (("deck", [0, 0, 0, 0]), ("items", 0), ("candidates", [0, 0, 0, 0])):
        width = max(len(s[key]) for s in samples)
        result[key] = [s[key] + [pad] * (width-len(s[key])) for s in samples]
        result[key+"_mask"] = [[True]*len(s[key]) + [False]*(width-len(s[key])) for s in samples]
    return result


def masked_argmax(scores, mask):
    if len(scores) != len(mask) or not any(mask):
        raise ValueError("Invalid scoring mask")
    return max((i for i, valid in enumerate(mask) if valid), key=lambda i: scores[i])


def iter_samples(index_path, *, split, policies):
    if split not in {"train", "validation", "test"} or not policies:
        raise ValueError("Explicit split, policies and positive batch size required")
    index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    root = Path(index["source"])
    raw = (root/"manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != index["source_manifest_sha256"]:
        raise ValueError("Source manifest changed")
    manifest = json.loads(raw)
    if manifest["config"]["rule_version"] != "instance-coal-v1":
        raise ValueError("Encoder supports instance-coal-v1 only")
    if set(policies) - set(manifest["policies"]): raise ValueError("Unknown policy")
    entries = {}
    for r in index["episodes"]:
        key = (r["policy"], r["episode_seed"])
        if key in entries or r["split"] != split_for_seed(r["episode_seed"], index["salt"]):
            raise ValueError("Invalid split index")
        entries[key] = r
    encoder, seen = CandidateEncoder(), set()
    for name in sorted({r["file"] for r in entries.values() if r["policy"] in policies}):
        path = (root/name).resolve()
        if path.parent != root.resolve(): raise ValueError("Unsafe source path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["files"][name]["sha256"]:
            raise ValueError("Trajectory hash mismatch")
        for header, episode in read_episodes(path):
            policy, seed = header["agent"], episode[0]["episode_seed"]
            key = (policy, seed)
            entry = entries.get(key)
            if (key in seen or entry is None or entry["file"] != name or
                    entry["transitions"] != len(episode) or header["config"] != manifest["config"] or
                    header.get("policy_config", {}) != manifest["policies"][policy]):
                raise ValueError("Episode/index mismatch")
            seen.add(key)
            if policy not in policies or entry["split"] != split: continue
            for record in episode:
                yield encoder.encode(record, policy)
    if {k for k in entries if k[0] in policies} != seen:
        raise ValueError("Missing episodes")


def iter_batches(index_path, *, split, policies, batch_size=64,
                 scaler=None, shuffle_seed=None, epoch=0, shuffle_buffer=1024):
    from luck_agent.evaluation.preprocessing import shuffled, scale_sample, validate_scaler
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("Positive integer batch size required")
    if scaler is not None:
        validate_scaler(scaler, index_path, policies)
    samples = iter_samples(index_path, split=split, policies=policies)
    if shuffle_seed is not None:
        if split != "train": raise ValueError("Shuffle is restricted to training")
        samples = shuffled(samples, shuffle_seed, epoch, shuffle_buffer)
    pending = []
    for sample in samples:
        pending.append(scale_sample(sample, scaler) if scaler is not None else sample)
        if len(pending) == batch_size:
            yield collate(pending); pending = []
    if pending: yield collate(pending)
