"""Create an auditable episode split index; leave source trajectories intact."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from luck_agent.evaluation.dataset import read_episodes, split_for_seed


def prepare(source, output, salt="luck-behavior-v1"):
    source, output = Path(source).resolve(), Path(output)
    manifest = json.loads((source/"manifest.json").read_text(encoding="utf-8"))
    rows, coverage, identities = [], {}, set()
    for name, expected in sorted(manifest["files"].items()):
        if not name.endswith(".jsonl.gz"):
            continue
        path = (source/name).resolve()
        if path.parent != source:
            raise ValueError("Trajectory must be inside source directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError(f"File hash mismatch: {name}")
        for header, episode in read_episodes(path):
            policy = header["agent"]
            if header["config"] != manifest["config"] or header.get("policy_config", {}) != manifest["policies"].get(policy):
                raise ValueError("Header and manifest disagree")
            seed = episode[0]["episode_seed"]
            if (policy, seed) in identities:
                raise ValueError("Duplicate policy/seed episode")
            identities.add((policy, seed))
            split = split_for_seed(seed, salt)
            end = episode[-1]
            rows.append({"file": name, "policy": policy, "episode_seed": seed, "split": split,
                         "transitions": len(episode), "terminated": end["terminated"],
                         "truncated": end["truncated"], "won": end["next_state"]["won"]})
            group = coverage.setdefault(f"{policy}/{split}", {"episodes": 0, "transitions": 0,
                "truncated": 0, "chosen_actions": Counter(), "available_actions": Counter()})
            group["episodes"] += 1; group["transitions"] += len(episode)
            group["truncated"] += end["truncated"]
            for r in episode:
                group["chosen_actions"][r["action"]["action_type"]] += 1
                group["available_actions"].update({a["action_type"] for a in r["legal_actions"]})
    expected_ids = {(p, s) for p in manifest["policies"] for s in range(manifest["seed_start"], manifest["seed_start"]+manifest["games"])}
    if identities != expected_ids:
        raise ValueError("Missing or unexpected policy/seed episodes")
    report = {"schema_version": 1, "source": str(source), "source_manifest_sha256": hashlib.sha256((source/"manifest.json").read_bytes()).hexdigest(),
              "salt": salt, "assignment": "SHA256(salt:seed) first 8 bytes big endian modulo 100; <80 train, <90 validation, otherwise test",
              "role": "development dataset partitions, not independent policy validation",
              "episodes": rows, "coverage": coverage}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(json.dumps({"episodes": len(result["episodes"]), "coverage": result["coverage"]}, indent=2))
