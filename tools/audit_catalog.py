"""Audit value sources without changing the recovered rules."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
metadata = root/"luck_agent/data/symbols.json"
catalog_file = root/"luck_agent/legacy/catalog.json"
records = json.loads(metadata.read_text(encoding="utf-8"))
catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
missing, differences = [], []
for row in records:
    raw = row.get("base_value")
    actual = catalog["symbol_values"].get(row["id"])
    if raw is None or actual is None:
        missing.append(row["id"])
    elif raw != actual:
        differences.append({"id": row["id"], "raw": raw, "effective": actual})
report = {"symbols_checked": len(records), "missing": missing, "differences": differences,
          "metadata_sha256": hashlib.sha256(metadata.read_bytes()).hexdigest(),
          "catalog_sha256": hashlib.sha256(catalog_file.read_bytes()).hexdigest(),
          "conclusion": "Only checks value consistency in recovered snapshots, not all game mechanics."}
(root/"reports").mkdir(exist_ok=True)
(root/"reports/v02_catalog_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
