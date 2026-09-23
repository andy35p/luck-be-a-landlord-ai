"""Normalize recovered catalog metadata without inventing declarative effects."""
import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="Previous task's w directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root / "luck_agent" / "data"
    target.mkdir(exist_ok=True)
    raw = args.source / "work" / "game_catalog_raw"
    catalog = json.loads((root/"luck_agent/legacy/catalog.json").read_text(encoding="utf-8"))
    coverage = json.loads((args.source/"outputs/规则覆盖报告.json").read_text(encoding="utf-8"))
    edges = []
    for kind, plural in (("symbol", "symbols"), ("item", "items"), ("essence", "essences")):
        records = json.loads((raw/f"{plural}.json").read_text(encoding="utf-8"))
        result = []
        descriptions = coverage.get(f"implemented_{kind}_rules", {})
        for key in catalog[f"{kind}_pool"]:
            entry = records.get(key, {})
            record = {"id": key, "name": key, "rarity": entry.get("rarity"),
                      "tags": entry.get("groups", []), "effects": [], "synergies": [],
                      "effect_backend": "legacy.fast_env", "effect_dsl_status": "not_migrated",
                      "historical_rule_description": descriptions.get(key),
                      "source": "installed_game_catalog" if key in records else "collector",
                      "original_game_verified": False}
            if kind == "symbol":
                record["base_value"] = float(entry["value"]) if entry.get("value") is not None else None
                record["legacy_effective_value"] = catalog["symbol_values"].get(key)
            result.append(record)
            for tag in record["tags"]:
                edges.append({"source": key, "relation": "member_of", "target": tag, "kind": kind})
        (target/f"{plural}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (target/"interactions.json").write_text(json.dumps({"status": "tag_membership_only_not_effect_DSL", "edges": edges}, ensure_ascii=False, indent=2), encoding="utf-8")
    (target/"historical_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
