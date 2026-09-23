"""Knowledge records are the executable source of sandbox effects."""
import hashlib
import json
from pathlib import Path


class Knowledge:
    def __init__(self) -> None:
        root = Path(__file__).parent / "data"
        names = ("symbols", "items", "interactions", "rarity", "effects")
        self.raw = {name: json.loads((root / f"{name}.json").read_text(encoding="utf-8")) for name in names}
        self.digest = hashlib.sha256(json.dumps(self.raw, sort_keys=True).encode()).hexdigest()
        self.symbols = {x["id"]: x for x in self.raw["symbols"]}
        self.items = {x["id"]: x for x in self.raw["items"]}
        self.interactions = self.raw["interactions"]
        self.rarity = self.raw["rarity"]
        assert len(self.symbols) == len(self.raw["symbols"]), "Duplicate symbol IDs"
        assert len(self.items) == len(self.raw["items"]), "Duplicate item IDs"
        for s in self.symbols.values():
            assert s["rarity"] in self.rarity and s["base_income"] >= 0
        for edge in self.interactions:
            assert edge["source"] in self.symbols and edge["target"] in self.symbols
            assert edge["relation"] in {"adjacent_bonus", "destroy", "transform"}
