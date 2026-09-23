"""实机日志驱动的轻量级《幸运房东》近似环境。

这是课程项目的高速原型，不宣称复刻全部原版效果。规则缺口会显式列在
coverage_report.json 中，方便后续用真实游戏日志逐项校准。
"""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
from dataclasses import dataclass, field
import json
import random
from pathlib import Path


DEFAULT_RENTS = [(25, 5), (50, 5), (100, 6), (150, 6), (225, 7),
                 (300, 7), (375, 8), (450, 8), (600, 9), (650, 9),
                 (700, 10), (777, 10), (1000, 10)]
STARTING = ["coin", "flower", "cat", "pearl", "cherry"]


def load_jsonl(path: str | Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def build_catalog(path: str | Path) -> dict:
    values, groups, symbol_candidates, item_candidates = defaultdict(list), defaultdict(set), [], []
    symbol_rarity, item_rarity, essence_rarity = {}, {}, {}
    rents = {}
    last_choice_signature = {"add_tile": None, "add_item": None}
    for row in load_jsonl(path):
        state = row.get("state") or {}
        progress = state.get("progress") or {}
        paid = progress.get("times_rent_paid")
        rv = progress.get("rent_values") or []
        if isinstance(paid, int) and rv:
            try:
                rents[paid] = max(rents.get(paid, 0), int(rv[0]))
            except (TypeError, ValueError):
                pass
        for sym in state.get("symbols") or []:
            sid = sym.get("type")
            if sid and sid != "empty":
                try:
                    values[sid].append(float(sym.get("value", 0)))
                except (TypeError, ValueError):
                    pass
                groups[sid].update(sym.get("groups") or [])
        prompt = (state.get("prompt") or {}).get("type", "")
        cards = state.get("cards") or []
        ids = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            args = card.get("args") or []
            data = card.get("data") or {}
            cid = (args[0] if args and isinstance(args[0], str)
                   else card.get("id") or data.get("type"))
            if cid:
                ids.append(cid)
                if prompt == "add_tile":
                    if data.get("rarity"):
                        symbol_rarity[cid] = data["rarity"]
                    raw_value = data.get("value")
                    if raw_value is None:
                        raw_values = data.get("values") or []
                        raw_value = raw_values[0] if raw_values else None
                    try:
                        if raw_value is not None:
                            values[cid].append(float(raw_value))
                    except (TypeError, ValueError):
                        pass
                    groups[cid].update(data.get("groups") or [])
                elif prompt == "add_item" and data.get("rarity"):
                    item_rarity[cid] = data["rarity"]
        if prompt in last_choice_signature and ids:
            signature = tuple(ids)
            if signature != last_choice_signature[prompt]:
                (symbol_candidates if prompt == "add_tile" else item_candidates).extend(ids)
                last_choice_signature[prompt] = signature
        elif not ids or prompt not in last_choice_signature:
            # 离开候选界面后允许未来再次出现相同三选一组合。
            last_choice_signature = {"add_tile": None, "add_item": None}
    base = {k: sum(v) / len(v) for k, v in values.items() if v}

    # 若已从用户安装的正版游戏包提取目录，则以完整目录补足实机未见条目。
    raw_dir = Path(path).parent / "game_catalog_raw"
    full_symbols, full_items, full_essences = {}, {}, {}
    for filename, target in (("symbols.json", full_symbols), ("items.json", full_items),
                             ("essences.json", full_essences)):
        candidate = raw_dir / filename
        if candidate.exists():
            target.update(json.loads(candidate.read_text(encoding="utf-8")))
    for sid, data in full_symbols.items():
        try:
            base.setdefault(sid, float(data.get("value", 0)))
        except (TypeError, ValueError):
            base.setdefault(sid, 0.0)
        groups[sid].update(data.get("groups") or [])
        if data.get("rarity"):
            symbol_rarity[sid] = data["rarity"]
    for iid, data in full_items.items():
        if data.get("rarity"):
            item_rarity[iid] = data["rarity"]
    for eid, data in full_essences.items():
        essence_rarity[eid] = data.get("rarity", "essence")
    pool = sorted(set(symbol_candidates) | set(base) | set(full_symbols))
    return {
        "symbol_values": base,
        "symbol_groups": {k: sorted(v) for k, v in groups.items()},
        "symbol_pool": pool,
        "item_pool": sorted(set(item_candidates) | set(full_items)),
        "essence_pool": sorted(full_essences),
        "symbol_candidate_counts": dict(Counter(symbol_candidates)),
        "item_candidate_counts": dict(Counter(item_candidates)),
        "essence_candidate_counts": {},
        "symbol_rarity": symbol_rarity,
        "item_rarity": item_rarity,
        "essence_rarity": essence_rarity,
        "rents_observed": rents,
        "observed_symbols": len(set(symbol_candidates)),
        "observed_items": len(set(item_candidates)),
        "catalog_symbols": len(pool),
        "catalog_items": len(set(item_candidates) | set(full_items)),
        "catalog_essences": len(full_essences),
        "catalog_source": "installed_game_pck" if full_symbols else "collector_only",
    }


@dataclass
class FastLandlordEnv:
    catalog: dict
    seed: int | None = None
    floor: int = 20
    deck: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    essences: list[str] = field(default_factory=list)
    coins: float = 0
    rent_index: int = 0
    spins_left: int = 0
    rerolls: int = 0
    removals: int = 0
    total_spins: int = 0
    dud_ttls: list[int] = field(default_factory=list)
    bubble_ttls: list[int] = field(default_factory=list)
    present_ttls: list[int] = field(default_factory=list)
    coal_ttls: list[int] = field(default_factory=list)
    light_bulb_uses: list[int] = field(default_factory=list)
    pending_symbol_groups: list[str] = field(default_factory=list)
    gambler_saved: int = 0
    item_counters: Counter = field(default_factory=Counter)
    permanent_bonuses: Counter = field(default_factory=Counter)
    last_interactions: list[str] = field(default_factory=list)
    display_counts: Counter = field(default_factory=Counter)
    last_shown: list[str] = field(default_factory=list)
    done: bool = False
    won: bool = False
    pending_rent: bool = False
    pillow_rare_choices: int = 0
    destroyed_history: list[str] = field(default_factory=list)
    destroyed_count: int = 0
    essence_tokens: int = 0
    pending_essence_choices: int = 0
    rare_candidate_slots: int = 0
    offered_rare_slots: int = 0
    current_offer: list[str] = field(default_factory=list)
    essence_lifetimes: list[dict] = field(default_factory=list)
    golem_ttls: list[int] = field(default_factory=list)
    soap_ttls: list[int] = field(default_factory=list)
    matryoshka_ttls: dict[str, list[int]] = field(default_factory=dict)
    spirit_ttls: list[int] = field(default_factory=list)
    fossil_ttls: list[int] = field(default_factory=list)
    mine_ttls: list[int] = field(default_factory=list)
    pending_symbol_rarities: list[str] = field(default_factory=list)
    force_skip_next_choice: bool = False
    force_add_next_choice: bool = False
    pending_shown: list[str] | None = None
    pending_lint_removed: int = 0
    pending_item_choices: int = 0

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        self.reset()

    def reset(self):
        self.deck = STARTING.copy()
        self.items, self.essences, self.coins, self.rent_index = [], [], 0.0, 0
        self.rerolls = self.removals = 0
        self.total_spins = 0
        self.dud_ttls = []
        self.bubble_ttls = []
        self.present_ttls = []
        self.coal_ttls = []
        self.light_bulb_uses = []
        self.pending_symbol_groups = []
        self.gambler_saved = 0
        self.item_counters = Counter()
        self.permanent_bonuses = Counter()
        self.last_interactions = []
        self.display_counts = Counter()
        self.last_shown = []
        if self.floor >= 20:
            self.deck.extend(["dud"] * 3)
            self.dud_ttls.extend([33] * 3)
        self.done = self.won = False
        self.pending_rent = False
        self.pillow_rare_choices = 0
        self.destroyed_history = []
        self.destroyed_count = 0
        self.essence_tokens = self.pending_essence_choices = 0
        self.rare_candidate_slots = self.offered_rare_slots = 0
        self.current_offer = []
        self.essence_lifetimes = []
        self.golem_ttls = []
        self.soap_ttls = []
        self.matryoshka_ttls = {}
        self.spirit_ttls = []
        self.fossil_ttls = []
        self.mine_ttls = []
        self.pending_symbol_rarities = []
        self.force_skip_next_choice = False
        self.force_add_next_choice = False
        self.pending_shown = None
        self.pending_lint_removed = 0
        self.pending_item_choices = 0
        self.spins_left = DEFAULT_RENTS[0][1]
        return self.state()

    def state(self):
        rent = DEFAULT_RENTS[min(self.rent_index, len(DEFAULT_RENTS)-1)][0]
        return {"coins": self.coins, "rent": rent, "spins_left": self.spins_left,
                "deck": Counter(self.deck), "items": tuple(self.items), "essences": tuple(self.essences),
                "item_counters": dict(self.item_counters),
                "pending_item_choices": self.pending_item_choices,
                "permanent_bonuses": dict(self.permanent_bonuses),
                "available_interactions": self.available_interactions(),
                "pending_symbol_groups": tuple(self.pending_symbol_groups),
                "pending_symbol_rarities": tuple(self.pending_symbol_rarities),
                "pending_rent": self.pending_rent,
                "rerolls": self.rerolls, "removals": self.removals,
                "essence_tokens": self.essence_tokens,
                "rare_candidate_slots": self.rare_candidate_slots,
                "essence_lifetimes": [dict(entry) for entry in self.essence_lifetimes],
                "pending_essence_choices": self.pending_essence_choices}

    def preview_spin(self):
        """展示本转20格结果，但暂不结算，供位置类物品选择动作。"""
        if self.pending_shown is None:
            self.pending_lint_removed = (self.deck.count("rabbit_fluff")
                                         if "lint_roller" in self.items else 0)
            if self.pending_lint_removed:
                self.deck = [s for s in self.deck if s != "rabbit_fluff"]
            self.pending_shown = self.rng.sample(self.deck, min(20, len(self.deck)))
            if "oil_can" in self.items:
                self.item_counters["oil_can"] += 1
        return list(self.pending_shown)

    def position_interactions(self):
        """返回展示后、结算前合法的位置动作。"""
        shown = self.preview_spin()
        actions = ["skip"]
        if "swapping_device" in self.items:
            actions.extend(f"swap:{a}:{b}" for a in range(len(shown))
                           for b in range(a + 1, len(shown)))
        if "oil_can" in self.items and self.item_counters["oil_can"] >= 5:
            actions.extend(f"respin:{column}" for column in range(5))
        return actions

    def candidates(self, kind="symbol", n=3):
        if kind == "symbol": self.current_offer = []
        if kind == "symbol": self.offered_rare_slots = 0
        if kind == "symbol" and self.force_skip_next_choice:
            return []
        credit_spins = self.item_counters["credit_card_spins"]
        if kind == "symbol" and credit_spins > 0 and credit_spins % 7 == 0:
            n += 17 * self.items.count("credit_card")
        pool_key = {"symbol": "symbol_pool", "item": "item_pool", "essence": "essence_pool"}[kind]
        pool = self.catalog[pool_key]
        if kind == "symbol" and "highlander" in self.deck:
            pool = [entry for entry in pool if entry != "highlander"]
        if kind == "symbol" and self.pending_symbol_groups and self.pending_symbol_groups[0] != "__any__":
            required = self.pending_symbol_groups[0]
            pool = [x for x in pool if required in self.catalog.get("symbol_groups", {}).get(x, [])]
        if kind == "symbol" and self.pending_symbol_rarities:
            ranks={"common":0,"uncommon":1,"rare":2,"very_rare":3}
            requested=self.pending_symbol_rarities[0]
            if requested.startswith("="):
                exact=requested[1:]
                forced=[x for x in pool if self.catalog.get("symbol_rarity",{}).get(x)==exact]
            else:
                minimum=ranks[requested]
                forced=[x for x in pool if ranks.get(self.catalog.get("symbol_rarity",{}).get(x),0)>=minimum]
            pool=forced
        if kind == "item" and self.pillow_rare_choices:
            rare_pool = [x for x in pool if self.catalog.get("item_rarity", {}).get(x) == "rare"]
            if rare_pool: pool = rare_pool
        if not pool:
            return []
        count_key = {"symbol":"symbol_candidate_counts","item":"item_candidate_counts","essence":"essence_candidate_counts"}[kind]
        rarity_key = {"symbol":"symbol_rarity","item":"item_rarity","essence":"essence_rarity"}[kind]
        observed_counts = self.catalog.get(count_key, {})
        rarities = self.catalog.get(rarity_key, {})
        def effective_rarity(entry):
            if kind == "symbol" and entry == "rain" and "rain_cloud" in self.items:
                return "common"
            if kind == "symbol" and entry == "comedian" and "dark_humor" in self.items:
                return "uncommon"
            if kind == "symbol" and entry in ("clubs","diamonds","hearts","spades") and "flush" in self.items:
                return "common"
            if kind == "symbol" and entry in ("void_creature","void_fruit","void_stone") and "void_party" in self.items:
                return "common"
            return rarities.get(entry)
        if self.rent_index == 0:
            rarity_probs = {"common": 1.0}
        elif self.rent_index <= 2:
            rarity_probs = {"common": .75, "uncommon": .25}
        elif self.rent_index <= 5:
            rarity_probs = {"common": .70, "uncommon": .25, "rare": .05}
        else:
            rarity_probs = {"common": .65, "uncommon": .25, "rare": .08, "very_rare": .02}
        if kind == "symbol":
            rarity_multiplier = 1.1 ** self.last_shown.count("shiny_pebble")
            rarity_multiplier *= 3 ** self.items.count("lucky_carrot")
            rarity_multiplier *= 5 ** self.items.count("golden_carrot")
            if "lucky_cat" in self.items:
                rarity_multiplier *= 1.3 ** (self.last_shown.count("cat") * self.items.count("lucky_cat"))
            for rarity in ("uncommon", "rare", "very_rare"):
                if rarity in rarity_probs:
                    rarity_probs[rarity] *= rarity_multiplier
                    rarity_probs[rarity] *= .7 ** self.last_shown.count("hex_of_tedium")
        available = list(pool); selected = []
        for slot in range(min(n, len(available))):
            slot_pool = available
            if kind == "symbol" and slot < self.rare_candidate_slots:
                slot_pool = [x for x in available if effective_rarity(x) in ("rare","very_rare")]
                if not slot_pool: break
                self.offered_rare_slots += 1
            valid_rarities = [r for r in rarity_probs if any(effective_rarity(x) == r for x in slot_pool)]
            if valid_rarities:
                rarity = self.rng.choices(valid_rarities,
                    weights=[rarity_probs[r] for r in valid_rarities], k=1)[0]
                subset = [x for x in slot_pool if effective_rarity(x) == rarity]
            else:
                subset = slot_pool
            # 同稀有度内使用实机频次轻度校准；未见条目仍保留抽取机会。
            weights = [1 + observed_counts.get(x, 0) for x in subset]
            chosen = self.rng.choices(subset, weights=weights, k=1)[0]
            selected.append(chosen); available.remove(chosen)
        if kind == "symbol": self.current_offer = list(selected)
        return selected

    def reroll(self, kind="symbol"):
        if self.rerolls <= 0:
            return []
        self.rerolls -= 1
        self.coins += 6 * self.items.count("lime_pepper")
        return self.candidates(kind)

    def remove(self, symbol):
        if self.removals and symbol in self.deck:
            self.deck.remove(symbol); self.removals -= 1
            if symbol == "pufferfish":
                self.rerolls += 1
            elif symbol == "jellyfish":
                self.removals += 1
            elif symbol == "sand_dollar":
                self.coins += 10
            self.coins += 6 * self.items.count("gray_pepper")
            if symbol == "dud" and self.dud_ttls:
                self.dud_ttls.pop(0)
            if symbol == "bubble" and self.bubble_ttls:
                self.bubble_ttls.pop(0)
            if symbol == "present" and self.present_ttls:
                self.present_ttls.pop(0)
            if symbol == "coal" and self.coal_ttls:
                self.coal_ttls.pop(0)
            if symbol == "light_bulb" and self.light_bulb_uses:
                self.light_bulb_uses.pop(0)
            if symbol == "spirit" and self.spirit_ttls:
                self.spirit_ttls.pop(0)
            if symbol == "frozen_fossil" and self.fossil_ttls:
                self.fossil_ttls.pop(0)
            if symbol == "mine" and self.mine_ttls:
                self.mine_ttls.pop(0)
            return True
        return False

    def choose(self, choice, kind="symbol"):
        if kind == "symbol" and choice == "highlander" and "highlander" in self.deck:
            return False
        if kind == "symbol" and not (choice in (None,"skip") and self.force_add_next_choice):
            self.rare_candidate_slots = max(0,self.rare_candidate_slots-self.offered_rare_slots)
            self.offered_rare_slots = 0
        if choice in (None, "skip"):
            if kind == "item" and self.pending_item_choices:
                self.pending_item_choices -= 1
            if kind == "symbol" and self.force_add_next_choice:
                return False
            if kind == "symbol":
                self.force_skip_next_choice = False
                if self.pending_symbol_groups:
                    self.pending_symbol_groups.pop(0)
                if self.pending_symbol_rarities:
                    self.pending_symbol_rarities.pop(0)
            if choice == "skip":
                self.coins += 2 * self.items.count("pink_pepper")
            return
        if kind == "symbol":
            # 蛋盒在鸡蛋进入牌组时立即收纳，并永久提供每转1枚。
            if choice == "egg" and "egg_carton" in self.items:
                self.items.append("egg_carton_charge")
            elif choice == "goldfish" and "fish_bowl" in self.items:
                self.item_counters["fish_bowl"] += 1
            else:
                self.deck.append(choice)
                if choice == "bubble":
                    self.bubble_ttls.append(3)
                elif choice == "present":
                    self.present_ttls.append(7 if "time_machine" in self.items else 12)
                elif choice == "coal":
                    self.coal_ttls.append(15 if "time_machine" in self.items else 20)
                elif choice == "light_bulb":
                    self.light_bulb_uses.append(0)
                elif choice == "spirit":
                    self.spirit_ttls.append(4)
                elif choice == "mine":
                    self.mine_ttls.append(4)
            if self.pending_symbol_groups:
                self.pending_symbol_groups.pop(0)
            if self.pending_symbol_rarities:
                self.pending_symbol_rarities.pop(0)
            self.force_add_next_choice = False
        elif kind == "item":
            self.items.append(choice)
            if choice == "popsicle":
                for entry in self.essence_lifetimes:
                    if entry["lives"] == 0:
                        entry["lives"] = 1 + self.items.count("popsicle")
            if self.pending_item_choices:
                self.pending_item_choices -= 1
            if choice == "void_portal":
                self.item_counters["void_portal_value"] = self.destroyed_count // 8
            if self.pillow_rare_choices:
                self.pillow_rare_choices -= 1
        else:
            self.essences.append(choice)
            self.essence_lifetimes.append({"type":choice,"age":0,
                "lives":1 + self.items.count("popsicle") if "popsicle" in self.items else 0})
            if self.pending_essence_choices:
                self.pending_essence_choices -= 1

    def available_interactions(self):
        """返回当前可主动触发的物品动作。"""
        actions = []
        if self.pending_rent:
            if "piggy_bank" in self.items:
                actions.append("cashout:piggy_bank")
            if "swear_jar" in self.items:
                actions.append("cashout:swear_jar")
            if "coffee" in self.items:
                actions.append("use:coffee")
            if "devils_deal" in self.items:
                actions.append("use:devils_deal")
        if "comfy_pillow" in self.items and self.spins_left == 1 and not self.pending_rent:
            actions.append("use:comfy_pillow")
        for item in ("barrel_o_dwarves", "goldilocks", "symbol_bomb_quantum", "booster_pack"):
            if item in self.items: actions.append(f"use:{item}")
        thresholds = {"red_suits": 7, "blue_suits": 7, "treasure_map": 20}
        for item, threshold in thresholds.items():
            if item in self.items and self.item_counters[item] >= threshold:
                actions.append(f"use:{item}")
        if "adoption_papers" in self.items:
            actions.append("use:adoption_papers")
        for item in ("lunchbox", "symbol_bomb_small", "symbol_bomb_big", "symbol_bomb_very_big"):
            if item in self.items:
                actions.append(f"use:{item}")
        return actions

    def consume_essence(self, entry):
        """完成一次精华触发；冰棒保留的下一周期独立重新计时。"""
        index = next((i for i,current in enumerate(self.essence_lifetimes) if current is entry), None)
        if index is None:
            return False
        if entry["lives"] > 1:
            entry["lives"] -= 1
            entry["age"] = 0
        else:
            self.essences.remove(entry["type"])
            self.essence_lifetimes.pop(index)
        return True

    def interact(self, action):
        """执行一个可选交互；成功时返回 True。"""
        if action not in self.available_interactions():
            return False
        if action.startswith("cashout:"):
            item = action.removeprefix("cashout:")
            multiplier = 2.5 if item == "piggy_bank" else 3
            self.coins += self.item_counters[item] * multiplier
            self.items.remove(item); self.item_counters.pop(item, None)
            self.last_interactions.append(action)
            self._resolve_due_rent()
            return True
        if action == "use:comfy_pillow":
            self.spins_left = 0
            self.pillow_rare_choices += self.items.count("comfy_pillow")
            self.pending_rent = True
            self.last_interactions.append(action)
            self._resolve_due_rent()
            return True
        if action == "use:coffee":
            self.items.remove("coffee")
            self.pending_rent = False
            self.spins_left = 1
            self.last_interactions.append(action)
            return True
        if action == "use:devils_deal":
            self.items.remove("devils_deal")
            self.deck.extend(["dud"] * 6)
            self.dud_ttls.extend([33] * 6)
            rent,_ = DEFAULT_RENTS[self.rent_index]
            self.coins += rent
            self.last_interactions.append(action)
            self._resolve_due_rent()
            return True
        if action in ("use:barrel_o_dwarves", "use:goldilocks", "use:symbol_bomb_quantum", "use:booster_pack"):
            item=action.removeprefix("use:"); self.items.remove(item)
            if item=="barrel_o_dwarves": self.deck.extend(["dwarf"]*7)
            elif item=="goldilocks": self.deck.extend(["bear"]*3)
            elif item=="symbol_bomb_quantum": self.pending_symbol_groups.extend(["__any__"]*9)
            else: self.pending_symbol_rarities.extend(["=common"]*4+["=uncommon"]*3+["=rare"])
            self.last_interactions.append(action); return True
        item = action.removeprefix("use:")
        self.items.remove(item)
        self.item_counters.pop(item, None)
        queued = {"adoption_papers": ("animal", 3), "lunchbox": ("food", 3),
                  "symbol_bomb_small": ("__any__", 2),
                  "symbol_bomb_big": ("__any__", 4),
                  "symbol_bomb_very_big": ("__any__", 8)}
        if item in queued:
            group, count = queued[item]
            self.pending_symbol_groups.extend([group] * count)
            self.last_interactions.append(action)
            return True
        additions = {"red_suits": ["diamonds", "hearts"],
                     "blue_suits": ["clubs", "spades"],
                     "treasure_map": ["key", "treasure_chest"]}
        self.deck.extend(additions[item])
        self.last_interactions.append(action)
        return True

    def _resolve_due_rent(self):
        """支付当前到期房租；资金不足时保留救租交互机会。"""
        if not self.pending_rent:
            return
        rent, _ = DEFAULT_RENTS[self.rent_index]
        if self.coins < rent:
            possible = 0
            if "piggy_bank" in self.items: possible += self.item_counters["piggy_bank"] * 2.5
            if "swear_jar" in self.items: possible += self.item_counters["swear_jar"] * 3
            has_non_cash_rescue = "coffee" in self.items or "devils_deal" in self.items
            if self.coins + possible < rent and not has_non_cash_rescue:
                self.pending_rent = False; self.done = True
            return
        self.coins -= rent; self.pending_rent = False; self.rent_index += 1
        if self.essence_tokens:
            self.essence_tokens -= 1
            self.pending_essence_choices += 1
        if self.rent_index >= len(DEFAULT_RENTS):
            self.done = self.won = True
        else:
            self.spins_left = DEFAULT_RENTS[self.rent_index][1]
            self.pending_item_choices += 1 + self.items.count("bag_of_holding")

    def decline_rent_rescue(self):
        if self.pending_rent:
            self.pending_rent = False; self.done = True

    def spin(self, position_action="skip"):
        shown = self.preview_spin()
        lint_removed = self.pending_lint_removed
        self.pending_lint_removed = 0
        position_bonus_indices = set()
        if position_action.startswith("swap:") and "swapping_device" in self.items:
            _,a,b = position_action.split(":")
            a,b = int(a),int(b)
            if 0 <= a < len(shown) and 0 <= b < len(shown) and a != b:
                shown[a],shown[b] = shown[b],shown[a]
                position_bonus_indices.update((a,b))
        elif position_action.startswith("respin:") and "oil_can" in self.items and self.item_counters["oil_can"] >= 5:
            column = int(position_action.split(":")[1])
            respin_indices = list(range(column,len(shown),5))
            retained = Counter(shown[i] for i in range(len(shown)) if i not in respin_indices)
            available = []
            for symbol in self.deck:
                if retained[symbol]:
                    retained[symbol] -= 1
                else:
                    available.append(symbol)
            replacements = self.rng.sample(available, min(len(respin_indices),len(available)))
            for i,symbol in zip(respin_indices,replacements):
                shown[i] = symbol
                position_bonus_indices.add(i)
            self.item_counters["oil_can"] = 0
        self.pending_shown = None
        self.last_shown = list(shown)
        values = self.catalog["symbol_values"]
        groups = self.catalog.get("symbol_groups", {})
        # 随机摆入4x5格；第一批规则使用八邻域，螃蟹使用同行。
        positions = {i: (i // 5, i % 5) for i in range(len(shown))}
        protractor_active = False
        if "protractor" in self.items:
            self.item_counters["protractor"] += 1
            if self.item_counters["protractor"] >= 3:
                protractor_active = True
                self.item_counters["protractor"] = 0
        telescope_active = False
        if "telescope" in self.items:
            self.item_counters["telescope"] += 1
            if self.item_counters["telescope"] >= 3:
                telescope_active = True
                self.item_counters["telescope"] = 0
        corners = {(0, 0), (0, 4), (3, 0), (3, 4)}
        adjacent = lambda a, b: a != b and (telescope_active or max(abs(positions[a][0] - positions[b][0]),
                                     abs(positions[a][1] - positions[b][1])) == 1 or
                                 (protractor_active and
                                  (positions[a] in corners or positions[b] in corners)))
        destroyed = set()
        removed = set()
        protected = set()
        for di,symbol in enumerate(shown):
            if symbol == "dove":
                protected.update(ti for ti in range(len(shown))
                                 if ti != di and adjacent(di,ti))
        self.last_interactions = []
        payout = sum(0.0 if s == "dud" else values.get(s, 1.0) for s in shown)
        payout += sum(max(0.0, values.get(shown[i], 0)) for i in position_bonus_indices)
        payout += 12 * lint_removed * self.items.count("lint_roller")
        payout += sum(self.permanent_bonuses[s] for s in shown)
        # 每份精华独立记录年龄，避免后获得的同类精华继承旧倒计时。
        timed_essences = {"pool_ball_essence":(60,1), "horseshoe_essence":(30,2),
                          "bowling_ball_essence":(20,3), "four_leaf_clover_essence":(15,4)}
        for entry in list(self.essence_lifetimes):
            rule = timed_essences.get(entry["type"])
            if rule is None:
                continue
            duration, income = rule
            payout += income
            entry["age"] += 1
            if entry["age"] >= duration:
                self.consume_essence(entry)
        self.display_counts.update(shown)

        # 红/蓝花色每转积累1点；达到7点后可由策略选择销毁并生成对应花色。
        if "credit_card" in self.items:
            self.item_counters["credit_card_spins"] += 1
        if "frozen_pizza" in self.items:
            self.item_counters["frozen_pizza"] += 1
            if self.item_counters["frozen_pizza"] >= 2:
                self.item_counters["frozen_pizza"] = 0
                self.pending_symbol_groups.extend(["__any__"] * self.items.count("frozen_pizza"))
        for item in ("red_suits", "blue_suits", "treasure_map"):
            if item in self.items:
                self.item_counters[item] += 1

        # 骰子使用离散点数，避免只用均值掩盖交租风险。
        rolled_one = False
        for die, sides in (("d3", 3), ("d5", 5)):
            for _ in range(shown.count(die)):
                roll = sides if "lucky_dice" in self.items else self.rng.randint(1, sides)
                # 重掷物品会将D3的1、D5的1或2各重投一次。
                if "reroll" in self.items and roll < (2 if die == "d3" else 3):
                    roll = self.rng.randint(1, sides)
                rolled_one |= roll == 1
                payout += roll - max(0.0, values.get(die, (sides + 1) / 2))

        # 赌徒每次出场存2；任一骰子投出1时，场上赌徒被消除并兑现。
        gambler_indices = [i for i, s in enumerate(shown) if s == "gambler"]
        self.gambler_saved += 2 * len(gambler_indices)
        if rolled_one and gambler_indices:
            payout += self.gambler_saved
            destroyed.update(gambler_indices)
            self.gambler_saved = 0

        # 狗的“抚摸”是可选交互；高速基线默认接受并记录动作。
        for _ in range(shown.count("dog")):
            payout += 2
            self.last_interactions.append("pet_dog")

        # 泡泡给3次收益后消除。这里按同类实例的稳定顺序匹配计数器。
        bubble_indices = [i for i, s in enumerate(shown) if s == "bubble"]
        for bi, deck_counter_index in zip(bubble_indices, range(len(bubble_indices))):
            if deck_counter_index >= len(self.bubble_ttls):
                self.bubble_ttls.append(3)
            self.bubble_ttls[deck_counter_index] -= 1
            if self.bubble_ttls[deck_counter_index] <= 0:
                destroyed.add(bi)

        # 无需棋盘位置的常见物品。
        payout += self.items.count("egg_carton_charge")
        payout += self.items.count("pool_ball")
        payout += 2 * self.items.count("horseshoe")
        payout += 3 * self.items.count("bowling_ball")
        payout += 4 * self.items.count("four_leaf_clover")
        self.rerolls += self.items.count("recycling")
        pepper_total = 2 * sum(1 for item in self.items if item.endswith("_pepper"))
        self.item_counters["total_peppers"] = max(self.item_counters["total_peppers"], pepper_total)
        payout += self.items.count("chili_powder") * self.item_counters["total_peppers"]
        if self.removals >= 3:
            self.removals += self.items.count("sunglasses")
        payout += self.item_counters["fish_bowl"] * self.items.count("fish_bowl")
        payout += 3 * self.items.count("white_pepper")
        carrot_multiplier = 3 ** self.items.count("lucky_carrot") * 5 ** self.items.count("golden_carrot")
        payout += (carrot_multiplier - 1) * shown.count("rabbit") * max(
            0.0, values.get("rabbit", 1.0) + self.permanent_bonuses["rabbit"])
        # 两种储蓄物品从每转收益中存钱，只在交租不足时作为主动兑现选项。
        for item, amount in (("piggy_bank", 2), ("swear_jar", 1)):
            count = self.items.count(item)
            if count:
                payout -= amount * count
                self.item_counters[item] += amount * count
        # 破碎的镜子每7转提供24枚；计数随后归零。
        if "shattered_mirror" in self.items:
            self.item_counters["shattered_mirror"] += 1
            cycles = self.item_counters["shattered_mirror"] // 7
            payout += 24 * cycles * self.items.count("shattered_mirror")
            self.item_counters["shattered_mirror"] %= 7
        # 每凑齐3个幸运七，自动消耗3个并提供77枚。
        lucky_sets = self.items.count("lucky_seven") // 3
        if lucky_sets:
            payout += 77 * lucky_sets
            for _ in range(3 * lucky_sets):
                self.items.remove("lucky_seven")
        if "pizza_the_cat" in self.items:
            payout += shown.count("cat")
        payout += 9 * self.items.count("black_cat")
        payout += self.items.count("black_cat") * shown.count("cat") * max(0.0, values.get("cat",1))
        if "blue_pepper" in self.items and len(shown) < 20:
            payout += 3
        if "tax_evasion" in self.items:
            payout += sum(1 for s in shown if values.get(s, 0) < 0)
        payout += self.items.count("anthropology_degree") * sum(
            1 for s in shown if "human" in groups.get(s, []))
        payout += 2 * self.items.count("chicken_coop") * sum(
            1 for s in shown if "chickenstuff" in groups.get(s, []))

        # 慢速符号按各自出场次数周期结算；方格旗把周期缩短1。
        slow_rules = {"snail": (5, 4), "turtle": (4, 3), "owl": (1, 3), "sloth": (4, 2),
                      "magpie": (9, 4), "crow": (-3, 4), "robin_hood": (25, 4)}
        flag_reduction = 1 if "checkered_flag" in self.items else 0
        for symbol, (bonus, period) in slow_rules.items():
            actual_period = max(1, period - flag_reduction)
            before = self.display_counts[symbol] - shown.count(symbol)
            after = self.display_counts[symbol]
            payout += bonus * (after // actual_period - before // actual_period)

        # 每个邪教徒获得“其他邪教徒数量”，3个及以上时每个再+1。
        cultists = shown.count("cultist")
        if cultists:
            payout += cultists * max(0, cultists - 1)
            if cultists >= 3:
                payout += cultists

        # 生锈齿轮使同一连通块中至少3个相同符号全部翻倍。
        if "rusty_gear" in self.items:
            unseen=set(range(len(shown)))
            while unseen:
                start=unseen.pop(); stack=[start]; component=[start]
                while stack:
                    current=stack.pop()
                    linked=[i for i in list(unseen) if shown[i]==shown[start] and adjacent(current,i)]
                    for i in linked: unseen.remove(i); stack.append(i); component.append(i)
                if len(component)>=3:
                    payout += sum(max(0.0,values.get(shown[i],0)) for i in component)

        # 左撇子兔子：最左列兔/兔毛翻倍，每10转生成1个兔毛。
        if "lefty_the_rabbit" in self.items:
            payout += sum(max(0.0,values.get(s,0)) for i,s in enumerate(shown)
                          if positions[i][1]==0 and s in ("rabbit","rabbit_fluff"))
            self.item_counters["lefty_the_rabbit"] += 1
            fluff=self.item_counters["lefty_the_rabbit"]//10
            if fluff:
                self.deck.extend(["rabbit_fluff"]*fluff)
                payout += fluff*self.items.count("brown_pepper")
                self.item_counters["lefty_the_rabbit"]%=10

        # 多个忍者彼此减值；忍者与老鼠物品使相邻双方变为6倍。
        ninjas = shown.count("ninja")
        payout -= ninjas * max(0, ninjas - 1)
        payout += 2 * self.items.count("cursed_katana") * ninjas * max(0,ninjas-1)
        if "ninja_and_mouse" in self.items:
            for ni, symbol in enumerate(shown):
                if symbol == "ninja":
                    for mi, other in enumerate(shown):
                        if other == "mouse" and adjacent(ni, mi):
                            ninja_value = max(0.0, values.get("ninja", 2) - max(0, ninjas - 1))
                            payout += 5 * (ninja_value + max(0.0, values.get("mouse", 1)))

        # 雨使相邻花朵变为2倍；多个雨的效果按独立倍数叠加。
        for fi, symbol in enumerate(shown):
            if symbol == "flower":
                rain_count = sum(1 for ri, other in enumerate(shown)
                                 if other == "rain" and adjacent(fi, ri))
                if rain_count:
                    payout += max(0.0, values.get("flower", 1.0)) * ((2 ** rain_count) - 1)

        # 箭头随机选择八个方向之一，射线上的非箭头符号获得倍率。
        directions = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        arrow_extra = {"bronze_arrow": 1, "silver_arrow": 2, "golden_arrow": 3}
        by_position = {pos: i for i, pos in positions.items()}
        for ai, arrow in enumerate(shown):
            if arrow not in arrow_extra:
                continue
            first = self.rng.choice(directions)
            chosen_directions = [first]
            if "quiver" in self.items:
                chosen_directions.append(self.rng.choice([d for d in directions if d != first]))
            for dr, dc in chosen_directions:
                row, col = positions[ai]
                row += dr; col += dc
                while (row, col) in by_position:
                    ti = by_position[(row, col)]; target = shown[ti]
                    if target not in arrow_extra:
                        payout += max(0.0, values.get(target, 1.0)) * arrow_extra[arrow]
                        if target == "target" and ti not in destroyed:
                            payout += 10
                            destroyed.add(ti)
                    row += dr; col += dc

        # 同行的其他螃蟹各让该螃蟹额外+3。
        crab_indices = [i for i, s in enumerate(shown) if s == "crab"]
        for ci in crab_indices:
            payout += 3 * sum(1 for cj in crab_indices
                              if ci != cj and positions[ci][0] == positions[cj][0])

        groups = self.catalog.get("symbol_groups", {})

        # 晴空使太阳/月亮与全盘对应目标相邻。
        celestial_adjacent = lambda giver, target: (adjacent(giver, target) or
                                                     "clear_sky" in self.items)
        # 月亮使相邻夜晚符号变为3倍；太阳使相邻花朵变为5倍。
        for mi,symbol in enumerate(shown):
            if symbol == "moon":
                for ti,target in enumerate(shown):
                    if ti != mi and celestial_adjacent(mi,ti) and "night" in groups.get(target,[]):
                        payout += 2 * max(0.0,values.get(target,0))
            elif symbol == "sun":
                for ti,target in enumerate(shown):
                    if ti != mi and celestial_adjacent(mi,ti) and target == "flower":
                        payout += 4 * max(0.0,values.get(target,0))

        # 驯兽师使每个相邻动物变为2倍。
        for bi,symbol in enumerate(shown):
            if symbol == "beastmaster":
                payout += sum(max(0.0,values.get(target,0))
                              for ti,target in enumerate(shown)
                              if ti != bi and adjacent(bi,ti)
                              and "animal" in groups.get(target,[]))

        # 厨师/贵妇/农夫分别倍增相邻食物/宝石/农夫喜爱符号。
        for ai,actor in enumerate(shown):
            target_group = ("food" if actor == "chef" else
                            "gem" if actor == "dame" else
                            "farmerlikes" if actor == "farmer" else None)
            if not target_group:
                continue
            for ti,target in enumerate(shown):
                if ti != ai and adjacent(ai,ti) and target_group in groups.get(target,[]):
                    payout += max(0.0,values.get(target,0)+self.permanent_bonuses[target])
                    if target in ("pear","amethyst"):
                        self.permanent_bonuses[target] += 1

        # 清洁布/水果篮按物品数量分别让宝石/水果每个额外提供1枚。
        payout += self.items.count("cleaning_rag") * sum(
            1 for s in shown if "gem" in groups.get(s, []))
        payout += self.items.count("fruit_basket") * sum(
            1 for s in shown if "fruit" in groups.get(s, []))
        payout += self.items.count("lemon") * max(0, 20 - len(shown))
        payout += self.items.count("ritual_candle") * sum(
            1 for s in shown if "fossillikes" in groups.get(s, []))
        payout += 2 * self.items.count("triple_coins") * shown.count("coin") * max(
            0.0, values.get("coin", 1.0))
        # 硬币绳自身每转提供1枚；它的符号相关效果由硬币基础收益保留。
        payout += self.items.count("coin_on_a_string")

        counts = Counter(shown)
        # 牌组中至少有2个同类时，草莓、红宝石和祖母绿各额外提供1枚。
        for counted_symbol in ("strawberry", "ruby", "emerald"):
            if counts[counted_symbol] >= 2:
                payout += counts[counted_symbol]
        payout += counts["diamond"] * max(0, counts["diamond"] - 1)
        payout += counts["watermelon"] * max(0, counts["watermelon"] - 1)
        if "green_pepper" in self.items and any(n >= 3 for n in counts.values()):
            payout += 3 * self.items.count("green_pepper")
        if "cyan_pepper" in self.items and counts and all(n < 3 for n in counts.values()):
            payout += 3 * self.items.count("cyan_pepper")
        if "red_pepper" in self.items and len(counts) == len(shown):
            payout += 5 * self.items.count("red_pepper")
        if "yellow_pepper" in self.items and len(shown) == 20:
            payout += 2 * self.items.count("yellow_pepper")
        if "birdhouse" in self.items:
            payout += sum(self.items.count("birdhouse") for s in shown
                          if "bird" in groups.get(s, []))
        payout += sum(self.items.count("happy_hour") for s in shown
                      if "booze" in groups.get(s, []))
        payout += sum(self.items.count("jackolantern") * max(0.0, values.get(s, 0))
                      for s in shown if "halloween" in groups.get(s, []))
        payout += sum(self.items.count("kyle_the_kernite") for s in shown
                      if "kyle" in groups.get(s, []))
        payout += sum(self.items.count("nori_the_rabbit") for s in shown
                      if s in ("rabbit", "rabbit_fluff"))
        payout += .5 * self.items.count("maxwell_the_bear") * shown.count("bear") * max(0.0, values.get("bear", 2))
        payout += self.items.count("oswald_the_monkey") * shown.count("monkey") * max(0.0, values.get("monkey", 1))
        payout += 2 * self.items.count("ricky_the_banana") * sum(shown.count(s) for s in ("banana", "banana_peel"))
        # 洒水壶让种子每次出现额外提供12枚。
        payout += 12 * self.items.count("watering_can") * shown.count("seed")

        # 喜剧演员使相邻搞笑符号变为3倍；黑色幽默将范围扩展到黑色幽默组。
        for ci, symbol in enumerate(shown):
            if symbol != "comedian": continue
            for ti, target in enumerate(shown):
                if not adjacent(ci, ti): continue
                target_groups = groups.get(target, [])
                if "funny" in target_groups:
                    payout += 2 * max(0.0, values.get(target, 0))
                if "dark_humor" in self.items and "darkhumor" in target_groups:
                    payout += (3 ** self.items.count("dark_humor") - 1) * max(0.0, values.get(target, 0))

        # 普通奎格利会把出场的狗转成狼；狼额外+1。
        if "quigley_the_wolf" in self.items:
            payout += shown.count("wolf") * self.items.count("quigley_the_wolf")
            for _ in range(shown.count("dog")):
                if "dog" in self.deck:
                    self.deck.remove("dog"); self.deck.append("wolf")

        # 紫辣椒：至少3个相同符号通过八邻域连成一组时提供5枚。
        if "purple_pepper" in self.items:
            triggered = False
            unseen = set(range(len(shown)))
            while unseen and not triggered:
                start = unseen.pop(); stack = [start]; size = 1
                while stack:
                    current = stack.pop()
                    linked = [i for i in list(unseen)
                              if shown[i] == shown[start] and adjacent(current, i)]
                    for i in linked:
                        unseen.remove(i); stack.append(i); size += 1
                triggered = size >= 3
            if triggered:
                payout += 5 * self.items.count("purple_pepper")

        # 龟在最右列且兔在最左列时，龟兔赛跑销毁并提供77枚。
        if "turtle_and_rabbit" in self.items:
            turtle_right = any(s == "turtle" and positions[i][1] == 4 for i, s in enumerate(shown))
            rabbit_left = any(s == "rabbit" and positions[i][1] == 0 for i, s in enumerate(shown))
            if turtle_right and rabbit_left:
                payout += 77
                self.items.remove("turtle_and_rabbit")

        # 锚位于四角时额外提供4枚。
        for ai, symbol in enumerate(shown):
            if symbol == "anchor" and positions[ai] in {(0, 0), (0, 4), (3, 0), (3, 4)}:
                payout += 4

        # 蜜蜂使相邻蜂系符号变为2倍；蜂巢每次出现有10%概率生成蜂蜜。
        for bi, symbol in enumerate(shown):
            if symbol == "bee":
                for ti, target in enumerate(shown):
                    if adjacent(bi, ti) and "beelikes" in groups.get(target, []):
                        payout += max(0.0, values.get(target, 1.0))
        generated = []
        spawn_multiplier = 2 ** self.items.count("conveyor_belt")
        booze_pool = [s for s in self.catalog.get("symbol_pool", [])
                      if "booze" in groups.get(s, [])] or ["beer", "wine", "martini"]
        for _ in range(shown.count("bartender")):
            if self.rng.random() < min(1.0, .10 * spawn_multiplier):
                generated.append(self.rng.choice(booze_pool))
        for _ in range(shown.count("cow")):
            if self.rng.random() < min(1.0, .15 * spawn_multiplier):
                generated.append("milk")
        generated.extend(["coin"] * shown.count("king_midas"))
        for _ in range(shown.count("beehive")):
            if self.rng.random() < min(1.0, .10 * spawn_multiplier):
                generated.append("honey")
        for _ in range(shown.count("goose")):
            if self.rng.random() < min(1.0, .01 * spawn_multiplier):
                generated.append("golden_egg")

        if "guillotine" in self.items:
            for i, symbol in enumerate(shown):
                if symbol == "billionaire":
                    destroyed.add(i)
                    payout += 39

        # 开锁器与盗墓者独立检查场上目标并按源码概率销毁。
        chest_bonuses = {"lockbox": 15, "safe": 30, "treasure_chest": 50, "mega_chest": 100}
        for i, symbol in enumerate(shown):
            if "lockpick" in self.items and "chest" in groups.get(symbol, []) and self.rng.random() < .35:
                destroyed.add(i); payout += chest_bonuses.get(symbol, 0)
            if "grave_robber" in self.items and "spiritbox" in groups.get(symbol, []) and self.rng.random() < .66:
                destroyed.add(i)

        # 灯泡让相邻宝石变为2倍；累计影响5颗宝石后销毁。
        bulb_indices = [i for i, s in enumerate(shown) if s == "light_bulb"]
        while len(self.light_bulb_uses) < self.deck.count("light_bulb"):
            self.light_bulb_uses.append(0)
        for bi, counter_index in zip(bulb_indices, range(len(bulb_indices))):
            affected = [ti for ti, target in enumerate(shown)
                        if adjacent(bi, ti) and "gem" in groups.get(target, [])]
            payout += sum(max(0.0, values.get(shown[ti], 1.0)) for ti in affected)
            self.light_bulb_uses[counter_index] += len(affected)
            if self.light_bulb_uses[counter_index] >= 5:
                destroyed.add(bi)

        # 抛光粉使所有相邻符号翻倍后自毁；多个粉末的倍率相乘。
        capsule_essences = [entry for entry in self.essence_lifetimes
                            if entry["type"] == "capsule_machine_essence"]
        capsule_factor = 2 ** self.items.count("capsule_machine") * 3 ** len(capsule_essences)
        powder_indices = [i for i, s in enumerate(shown) if s == "buffing_powder"]
        for ti, target in enumerate(shown):
            affecting = sum(adjacent(pi, ti) for pi in powder_indices)
            if affecting and target != "buffing_powder":
                payout += max(0.0, values.get(target, 0) + self.permanent_bonuses[target]) * (2 ** (affecting * capsule_factor) - 1)
        destroyed.update(powder_indices)

        # 煎锅：任一“煎蛋材料”与蛋相邻时销毁蛋，并为每个煎锅生成一个煎蛋卷。
        if "frying_pan" in self.items:
            for ei, symbol in enumerate(shown):
                if symbol != "egg":
                    continue
                if any(ti != ei and adjacent(ei, ti) and
                       "omelettestuff" in groups.get(target, [])
                       for ti, target in enumerate(shown)):
                    destroyed.add(ei)
                    generated.extend(["omelette"] * self.items.count("frying_pan"))

        # 毁灭诅咒有30%概率销毁一个随机相邻符号。
        for hi, symbol in enumerate(shown):
            if ("holy_water" in self.items or symbol != "hex_of_destruction" or
                    self.rng.random() >= .30):
                continue
            possible = [i for i in range(len(shown)) if i != hi and adjacent(hi, i) and i not in destroyed]
            if possible: destroyed.add(self.rng.choice(possible))
        # 抽水诅咒有30%概率令一个随机相邻符号本转收益归零。
        for hi,symbol in enumerate(shown):
            if "holy_water" in self.items or symbol!="hex_of_draining" or self.rng.random()>=.30: continue
            possible=[i for i in range(len(shown)) if i!=hi and adjacent(hi,i) and i not in destroyed]
            if possible: payout -= max(0.0,values.get(shown[self.rng.choice(possible)],0))
        # 空虚诅咒有30%概率使本转后的普通抓牌只能跳过（最后1转不触发）。
        if self.spins_left != 0 and "holy_water" not in self.items:
            for _ in range(shown.count("hex_of_emptiness")):
                if self.rng.random()<.30: self.force_skip_next_choice=True; break
            if not self.force_skip_next_choice:
                for _ in range(shown.count("hex_of_hoarding")):
                    if self.rng.random()<.30: self.force_add_next_choice=True; break
        if "holy_water" not in self.items:
            for _ in range(shown.count("hex_of_midas")):
                if self.rng.random()<min(1.0,.30*spawn_multiplier): generated.append("coin")
            for _ in range(shown.count("hex_of_thievery")):
                if self.rng.random()<.30: payout -= 6
        payout += self.items.count("holy_water") * sum(
            1 for s in shown if "hex" in groups.get(s, []))

        # 花色：场上至少3个时各+1；相邻同色互相+1，第五张王牌允许异色也互相+1。
        suits = {"clubs", "spades", "hearts", "diamonds"}
        suit_indices = [i for i, symbol in enumerate(shown) if symbol in suits]
        if len(suit_indices) >= 3:
            payout += len(suit_indices)
        red = {"hearts", "diamonds"}
        for si in suit_indices:
            for ti in suit_indices:
                if si == ti or not adjacent(si, ti):
                    continue
                same_color = (shown[si] in red) == (shown[ti] in red)
                if same_color or "fifth_ace" in self.items:
                    payout += 1

        # 扑克高手使相邻花色成为百搭：按本转最高基础/永久价值补齐差额。
        wildcard_value = max((max(0.0, values.get(s, 0) + self.permanent_bonuses[s])
                              for s in shown), default=0.0)
        shark_suits = set()
        for ci,symbol in enumerate(shown):
            if symbol == "card_shark":
                shark_suits.update(ti for ti,target in enumerate(shown)
                                   if ti != ci and adjacent(ci,ti)
                                   and "suit" in groups.get(target, []))
        payout += sum(max(0.0, wildcard_value - values.get(shown[i], 0)
                          - self.permanent_bonuses[shown[i]]) for i in shark_suits)

        # 小丑使相邻花色变为2倍；迈达斯使相邻硬币变为3倍。
        for ai,actor in enumerate(shown):
            if actor not in ("joker", "king_midas", "witch"):
                continue
            for ti,target in enumerate(shown):
                if ti == ai or not adjacent(ai,ti):
                    continue
                if actor == "joker" and "suit" in groups.get(target, []):
                    payout += max(0.0,values.get(target,0))
                elif actor == "king_midas" and target == "coin":
                    payout += 2 * max(0.0,values.get(target,0))
                elif actor == "witch" and "witchlikes" in groups.get(target, []):
                    payout += max(0.0,values.get(target,0))

        # 罗宾汉让相邻的 robinlikes 符号额外提供3枚。
        for ri,symbol in enumerate(shown):
            if symbol == "robin_hood":
                payout += 3 * sum(1 for ti,target in enumerate(shown)
                                  if ti != ri and adjacent(ri,ti)
                                  and "robinlikes" in groups.get(target, []))

        # 常见相邻销毁：钥匙开三类箱子；猴子吃椰子/半个椰子。
        destroy_rules = {
            "key": {"lockbox", "safe", "treasure_chest", "mega_chest"},
            "monkey": {"banana", "coconut", "coconut_half"},
            "dwarf": {"beer", "wine"},
            "bounty_hunter": {"thief"},
            "banana_peel": {"thief"},
            "goldfish": {"bubble"},
            "cat": {"milk"},
            "mouse": {"cheese"},
            "miner": {"ore", "big_ore"},
            "hooligan": {"urn", "big_urn", "tomb"},
            "bear": {"honey"},
        }
        bonuses = {"lockbox": 15, "safe": 30, "treasure_chest": 50, "mega_chest": 100,
                   "coconut": 14, "coconut_half": 7,
                   "banana": 6, "beer": 10, "wine": 20, "thief": 20,
                   "bubble": 15, "milk": 9, "cheese": 20, "honey": 40}
        for ai, actor in enumerate(shown):
            targets = destroy_rules.get(actor, set())
            for ti, target in enumerate(shown):
                toddler_target = actor == "toddler" and "toddlerlikes" in groups.get(target, [])
                dwarf_target = actor == "dwarf" and "dwarflikes" in groups.get(target, [])
                anvil_target = actor == "dwarf" and "dwarven_anvil" in self.items and "minerlikes" in groups.get(target, [])
                contract_target = (actor == "bounty_hunter" and
                                   "zaroffs_contract" in self.items and
                                   "human" in groups.get(target, []))
                fruit_target = actor == "mrs_fruit" and "fruitlikes" in groups.get(target, [])
                diver_target = actor == "diver" and "poslikes" in groups.get(target, [])
                archaeologist_target = actor == "archaeologist" and "archlikes" in groups.get(target, [])
                pirate_target = actor == "pirate" and "piratelikes" in groups.get(target, [])
                magic_key_target = actor == "magic_key" and "chest" in groups.get(target, [])
                robin_target = actor == "robin_hood" and "robinhates" in groups.get(target, [])
                dame_target = actor == "dame" and target == "martini"
                zaroff_target = actor == "general_zaroff" and target != "general_zaroff" and "human" in groups.get(target, [])
                if ti not in destroyed and ti not in removed and (target in targets or toddler_target or dwarf_target or anvil_target or contract_target or fruit_target or diver_target or archaeologist_target or pirate_target or magic_key_target or robin_target or dame_target or zaroff_target) and adjacent(ai, ti):
                    if diver_target:
                        removed.add(ti)
                        self.permanent_bonuses["diver"] += 1
                        if target == "oyster": generated.append("pearl")
                        elif target == "sand_dollar": payout += 10
                        elif target == "jellyfish": self.removals += 1
                        elif target == "pufferfish": self.rerolls += 1
                        self.last_interactions.append(f"remove:diver:{target}")
                        continue
                    destroy_bonus = (25 * self.items.count("zaroffs_contract")
                                     if contract_target else bonuses.get(target, 0))
                    if pirate_target:
                        destroy_bonus = chest_bonuses.get(target, 0)
                        self.permanent_bonuses["pirate"] += 1
                    payout += destroy_bonus
                    if magic_key_target:
                        payout += 2 * (max(0.0, values.get(target, 0)) + destroy_bonus)
                    if robin_target:
                        payout += 15
                    if dame_target:
                        payout += 40
                    if zaroff_target:
                        payout += 25
                    if "looting_glove" in self.items and "box" in groups.get(target, []):
                        payout += .5 * self.items.count("looting_glove") * (
                            max(0.0, values.get(target, 0)) + destroy_bonus)
                    if toddler_target:
                        payout += 6
                    if fruit_target:
                        self.permanent_bonuses["mrs_fruit"] += 1
                    if diver_target:
                        self.permanent_bonuses["diver"] += 1
                    if archaeologist_target:
                        self.permanent_bonuses["archaeologist"] += 1
                    destroyed.add(ti)
                    if actor in ("key", "banana_peel", "magic_key"):
                        destroyed.add(ai)
                    if target == "banana":
                        generated.append("banana_peel")
                    if target == "pinata":
                        generated.extend(["candy"] * 7)
                    if target in ("ore", "big_ore"):
                        gem_pool = [s for s in self.catalog.get("symbol_pool",[])
                                    if "gem" in groups.get(s,[])]
                        if "x_ray_machine" in self.items:
                            ranks={"common":0,"uncommon":1,"rare":2,"very_rare":3}
                            gem_pool=[s for s in gem_pool if ranks.get(self.catalog.get("symbol_rarity",{}).get(s),0)>=2]
                        gem_pool = gem_pool or ["pearl", "shiny_pebble", "sapphire", "emerald", "ruby", "diamond"]
                        for _ in range(1 if target == "ore" else 2):
                            generated.append(self.rng.choice(gem_pool))
                    if "mining_pick" in self.items and "minerlikes" in groups.get(target, []):
                        payout += 10 * self.items.count("mining_pick")
                    if actor not in ("toddler", "diver", "archaeologist", "pirate", "robin_hood", "dame", "general_zaroff"):
                        break

        # 自消除胶囊和虚空符号。功能奖励立即进入环境状态。
        supported_capsules = {"removal_capsule","reroll_capsule","essence_capsule",
                              "item_capsule","rarity_capsule","time_capsule","tedium_capsule",
                              "lucky_capsule","buffing_powder"}
        self_destroy = {
            "tedium_capsule": 5,
            "void_creature": 8, "void_fruit": 8, "void_stone": 8,
        }
        for i, symbol in enumerate(shown):
            if symbol in self_destroy:
                capsule_multi = capsule_factor
                payout += self_destroy[symbol] * (capsule_multi if symbol == "tedium_capsule" else 1)
                destroyed.add(i)
            elif symbol == "removal_capsule":
                self.removals += capsule_factor; destroyed.add(i)
            elif symbol == "reroll_capsule":
                self.rerolls += capsule_factor; destroyed.add(i)
            elif symbol in ("lucky_capsule", "buffing_powder", "time_capsule"):
                capsule_multi = capsule_factor
                if symbol == "lucky_capsule": payout += 10 * capsule_multi
                if symbol == "time_capsule":
                    history = self.destroyed_history + [shown[j] for j in sorted(destroyed)]
                    for _ in range(capsule_multi):
                        eligible = [entry for entry in history
                                    if entry != "time_capsule"
                                    and "time_capsule_effects" not in groups.get(entry, [])
                                    and self.catalog.get("symbol_rarity", {}).get(entry) != "none"
                                    and not (entry == "highlander" and
                                             (entry in self.deck or entry in generated))]
                        if eligible:
                            generated.append(self.rng.choice(eligible))
                destroyed.add(i)
            elif symbol == "chemical_seven":
                payout += 7
                self.items.append("lucky_seven")
                destroyed.add(i)
            elif symbol == "essence_capsule":
                self.essence_tokens += capsule_factor; destroyed.add(i)
            elif symbol == "item_capsule":
                commons = [x for x in self.catalog.get("item_pool", [])
                           if self.catalog.get("item_rarity", {}).get(x) == "common"]
                if commons:
                    for _ in range(capsule_factor):
                        self.items.append(self.rng.choice(commons))
                destroyed.add(i)
            elif symbol == "hustler":
                self.items.append("pool_ball"); destroyed.add(i)
            elif symbol == "rarity_capsule":
                self.rare_candidate_slots += capsule_factor
                destroyed.add(i)

        if any(shown[i] in supported_capsules for i in destroyed):
            for entry in capsule_essences:
                self.consume_essence(entry)

        # 幽灵提供4次收益后消失；送葬者会让其不会消失。
        spirit_indices = [i for i,s in enumerate(shown) if s == "spirit"]
        while len(self.spirit_ttls) < self.deck.count("spirit"):
            self.spirit_ttls.append(4)
        if "undertaker" not in self.items:
            for si,counter_index in zip(spirit_indices,range(len(spirit_indices))):
                self.spirit_ttls[counter_index] -= 1
                if self.spirit_ttls[counter_index] <= 0:
                    destroyed.add(si)

        # 鸽子让相邻符号免于本转销毁。
        destroyed.difference_update(protected)

        # 冰冻化石出场20次后变为异界生物；时间机器缩短5次。
        fossil_indices = [i for i,s in enumerate(shown)
                          if s == "frozen_fossil" and i not in destroyed]
        while len(self.fossil_ttls) < self.deck.count("frozen_fossil"):
            self.fossil_ttls.append(15 if "time_machine" in self.items else 20)
        for fi,counter_index in zip(fossil_indices,range(len(fossil_indices))):
            self.fossil_ttls[counter_index] -= 1
            if self.fossil_ttls[counter_index] <= 0:
                destroyed.add(fi)
                generated.append("eldritch_beast")

        # 瓮类无论由流氓还是盗墓者销毁，都会生成对应数量的幽灵。
        spirit_counts = {"urn": 1, "big_urn": 2, "tomb": 5}
        for i in destroyed:
            generated.extend(["spirit"] * spirit_counts.get(shown[i], 0))
            if shown[i] == "peach":
                generated.append("seed")
            if "organism" in groups.get(shown[i], []) and "shrine" in self.items:
                generated.extend(["spirit"] * self.items.count("shrine"))
            if ("void" in groups.get(shown[i], []) and "void_party" in self.items and
                    self.item_counters["void_party"] < 7 and self.rng.random() < .50):
                generated.append(shown[i])
                self.item_counters["void_party"] += 1

        # 通缉令把小偷总收益变为3.5倍；销毁奖励沿用高速环境的已结算值。
        if "wanted_poster" in self.items:
            thief_base = max(0.0, values.get("thief", 0))
            payout += 2.5 * self.items.count("wanted_poster") * shown.count("thief") * thief_base
            destroyed_thieves = sum(shown[i] == "thief" for i in destroyed)
            payout += 2.5 * self.items.count("wanted_poster") * 20 * destroyed_thieves

        # 堆肥每累计销毁3个符号生成1颗种子，余数跨转保留。
        if "compost_heap" in self.items:
            self.item_counters["compost_heap"] += len(destroyed)
            compost_seeds = self.item_counters["compost_heap"] // 3
            if compost_seeds:
                generated.extend(["seed"] * compost_seeds)
                self.item_counters["compost_heap"] %= 3

        # 礼物第12次出场时销毁并提供10枚。计数按同类实例的稳定顺序近似匹配。
        # 矿井每次出场生成矿石，第4次后销毁并加入矿镐。
        mine_indices = [i for i,s in enumerate(shown) if s == "mine"]
        while len(self.mine_ttls) < self.deck.count("mine"):
            self.mine_ttls.append(4)
        for mi,counter_index in zip(mine_indices,range(len(mine_indices))):
            generated.append("ore")
            self.mine_ttls[counter_index] -= 1
            if self.mine_ttls[counter_index] <= 0:
                destroyed.add(mi)
                self.items.append("mining_pick")

        present_indices = [i for i, s in enumerate(shown) if s == "present"]
        while len(self.present_ttls) < self.deck.count("present"):
            self.present_ttls.append(7 if "time_machine" in self.items else 12)
        for pi, counter_index in zip(present_indices, range(len(present_indices))):
            self.present_ttls[counter_index] -= 1
            if self.present_ttls[counter_index] <= 0:
                payout += 10
                destroyed.add(pi)
        if destroyed or removed:
            # 按本次抽中的实例删除，重复符号也只删除对应数量。
            removal_counts = Counter(shown[i] for i in destroyed | removed)
            kept = []
            for symbol in self.deck:
                if removal_counts[symbol]:
                    removal_counts[symbol] -= 1
                else:
                    kept.append(symbol)
            self.deck = kept
            destroyed_bubbles = sum(shown[i] == "bubble" for i in destroyed)
            for _ in range(min(destroyed_bubbles, len(self.bubble_ttls))):
                self.bubble_ttls.pop(0)
            destroyed_presents = sum(shown[i] == "present" for i in destroyed)
            for _ in range(min(destroyed_presents, len(self.present_ttls))):
                self.present_ttls.pop(0)
            destroyed_spirits = sum(shown[i] == "spirit" for i in destroyed)
            for _ in range(min(destroyed_spirits, len(self.spirit_ttls))):
                self.spirit_ttls.pop(0)
            destroyed_fossils = sum(shown[i] == "frozen_fossil" for i in destroyed)
            for _ in range(min(destroyed_fossils, len(self.fossil_ttls))):
                self.fossil_ttls.pop(0)
            destroyed_mines = sum(shown[i] == "mine" for i in destroyed)
            for _ in range(min(destroyed_mines, len(self.mine_ttls))):
                self.mine_ttls.pop(0)
            self.destroyed_history.extend(shown[i] for i in sorted(destroyed)
                                          if shown[i] != "time_capsule")
        self.destroyed_count += len(destroyed)
        # 虚空传送门按整局累计销毁数量提供收益，重复类型同样计数。
        if "void_portal" in self.items:
            portal_value = self.destroyed_count // 8
            self.item_counters["void_portal_value"] = portal_value
            payout += portal_value * self.items.count("void_portal")
        payout += len(destroyed) * self.items.count("black_pepper")
        self.deck.extend(generated)
        self.spirit_ttls.extend([4] * generated.count("spirit"))
        payout += len(generated) * self.items.count("brown_pepper")

        # 煤第20次出场后变成钻石。
        coal_indices = [i for i, s in enumerate(shown) if s == "coal" and i not in destroyed]
        while len(self.coal_ttls) < self.deck.count("coal"):
            self.coal_ttls.append(15 if "time_machine" in self.items else 20)
        for _ci, counter_index in zip(coal_indices, range(len(coal_indices))):
            self.coal_ttls[counter_index] -= 1
            if self.coal_ttls[counter_index] <= 0 and "coal" in self.deck:
                self.deck.remove("coal"); self.deck.append("diamond")
        self.coal_ttls = [ttl for ttl in self.coal_ttls if ttl > 0]

        if "cardboard_box" in self.items:
            self.item_counters["cardboard_box"] += 1
            grants=self.item_counters["cardboard_box"]//10
            self.removals += grants*self.items.count("cardboard_box")
            self.item_counters["cardboard_box"]%=10
        if "dishwasher" in self.items:
            self.item_counters["dishwasher"] += 1
            grants = self.item_counters["dishwasher"] // 12
            if grants:
                self.essence_tokens += grants * self.items.count("dishwasher")
                self.item_counters["dishwasher"] %= 12

        # 鸡分别有5%和1%概率生成蛋与金蛋，传送带倍增概率。
        coop_probability_multiplier = 3 ** self.items.count("chicken_coop")
        for _ in range(shown.count("chicken")):
            if self.rng.random() < min(1.0,.05*spawn_multiplier*coop_probability_multiplier):
                self.deck.append("egg")
            if self.rng.random() < min(1.0,.01*spawn_multiplier*coop_probability_multiplier):
                self.deck.append("golden_egg")

        # 矿石傀儡出场5次后销毁并生成5个矿石；时间机器缩短2次。
        golem_indices = [i for i, s in enumerate(shown) if s == "golem" and i not in destroyed]
        while len(self.golem_ttls) < self.deck.count("golem"):
            self.golem_ttls.append(3 if "time_machine" in self.items else 5)
        expired_golems = 0
        for _gi, counter_index in zip(golem_indices, range(len(golem_indices))):
            self.golem_ttls[counter_index] -= 1
            if self.golem_ttls[counter_index] <= 0 and "golem" in self.deck:
                self.deck.remove("golem"); expired_golems += 1
        if expired_golems:
            self.deck.extend(["ore"] * (5 * expired_golems))
        self.golem_ttls = [ttl for ttl in self.golem_ttls if ttl > 0]

        # 肥皂每次出场生成泡泡，第3次后自毁。
        soap_indices=[i for i,s in enumerate(shown) if s=="bar_of_soap" and i not in destroyed]
        while len(self.soap_ttls)<self.deck.count("bar_of_soap"): self.soap_ttls.append(3)
        expired_soap=0
        for _si,counter_index in zip(soap_indices,range(len(soap_indices))):
            self.deck.append("bubble"); self.bubble_ttls.append(3)
            self.soap_ttls[counter_index]-=1
            if self.soap_ttls[counter_index]<=0 and "bar_of_soap" in self.deck:
                self.deck.remove("bar_of_soap"); expired_soap+=1
        self.soap_ttls=[x for x in self.soap_ttls if x>0]

        # 套娃依次在3/5/7/9次出场后升级；时间机器每阶段减少2次。
        doll_steps={f"matryoshka_doll_{i}":(2*i+1,f"matryoshka_doll_{i+1}") for i in range(1,5)}
        for doll,(needed,next_doll) in doll_steps.items():
            shown_count=shown.count(doll)
            counters=self.matryoshka_ttls.setdefault(doll,[])
            while len(counters)<self.deck.count(doll): counters.append(max(1,needed-(2 if "time_machine" in self.items else 0)))
            transforms=0
            for counter_index in range(min(shown_count,len(counters))):
                counters[counter_index]-=1
                if counters[counter_index]<=0 and doll in self.deck:
                    self.deck.remove(doll); transforms+=1
            if transforms: self.deck.extend([next_doll]*transforms)
            self.matryoshka_ttls[doll]=[x for x in counters if x>0]

        # 牡蛎出场时有20%概率生成珍珠。
        for _ in range(shown.count("oyster")):
            if self.rng.random() < min(1.0, .20 * spawn_multiplier):
                self.deck.append("pearl")

        # 种子出场时有25%概率成长；产物池先使用已核对的基础植物/水果。
        adjacent_suns = max((sum(1 for ui,s in enumerate(shown)
                                 if s == "sun" and adjacent(si,ui))
                             for si,s in enumerate(shown) if s == "seed"), default=0)
        adjacent_farmers = max((sum(1 for fi,s in enumerate(shown)
                                    if s == "farmer" and adjacent(si,fi))
                                for si,s in enumerate(shown) if s == "seed"), default=0)
        seed_chance = min(1.0, .25 + .50 * self.items.count("fertilizer") +
                          .50 * adjacent_suns + .50 * adjacent_farmers)
        if "seed" in shown and self.rng.random() < seed_chance and "seed" in self.deck:
            plant_pool = [s for s in self.catalog.get("symbol_pool", [])
                          if "plant" in groups.get(s, [])]
            min_rank = 2 if "fertilizer" in self.items else (1 if "compost_heap" in self.items else 0)
            rank = {"common": 0, "uncommon": 1, "rare": 2, "very_rare": 3}
            eligible = [s for s in plant_pool if rank.get(self.catalog.get("symbol_rarity", {}).get(s), 0) >= min_rank]
            self.deck.remove("seed")
            self.deck.append(self.rng.choice(eligible or ["flower", "cherry", "banana", "orange", "peach", "apple"]))

        # 鸡蛋与小鸡各有10%成长概率（仅处理本转未被销毁的实例）。
        for old, new in (("egg", "chick"), ("chick", "chicken")):
            for i, symbol in enumerate(shown):
                growth_multiplier = coop_probability_multiplier if old == "egg" else 1
                if symbol == old and i not in destroyed and self.rng.random() < min(1.0,.10*growth_multiplier) and old in self.deck:
                    self.deck.remove(old); self.deck.append(new)
        # 兔子每10次出场永久+2；脱毛季使每次出场有15%概率生成兔毛。
        rabbit_before = self.display_counts["rabbit"] - shown.count("rabbit")
        rabbit_after = self.display_counts["rabbit"]
        rabbit_growth = 2 * (rabbit_after // 10 - rabbit_before // 10)
        self.permanent_bonuses["rabbit"] += rabbit_growth
        payout += rabbit_growth * shown.count("rabbit")
        if "shedding_season" in self.items:
            for _ in range(shown.count("rabbit")):
                if self.rng.random() < min(1.0, .15 * spawn_multiplier):
                    self.deck.append("rabbit_fluff")
        if "dwarven_anvil" in self.items:
            payout += shown.count("dwarf") * max(0.0, values.get("dwarf", 1.0))
        if "ancient_lizard_blade" in self.items:
            duplicate_types = sum(count >= 2 for symbol,count in Counter(self.deck).items()
                                  if symbol != "empty")
            payout += max(0, (9 - duplicate_types) * self.items.count("ancient_lizard_blade"))
        self.coins += payout
        self.total_spins += 1

        # 进阶20：开局3个红叉；之后每15转加入1个。每个红叉33转后消失。
        if self.floor >= 20:
            self.dud_ttls = [ttl - 1 for ttl in self.dud_ttls]
            expired = sum(ttl <= 0 for ttl in self.dud_ttls)
            self.dud_ttls = [ttl for ttl in self.dud_ttls if ttl > 0]
            for _ in range(expired):
                if "dud" in self.deck:
                    self.deck.remove("dud")
            if self.total_spins % 15 == 0:
                self.deck.append("dud")
                self.dud_ttls.append(33)
        self.spins_left -= 1
        if self.spins_left == 0:
            old_index = self.rent_index
            self.pending_rent = True
            self._resolve_due_rent()
            if self.rent_index == 3 and old_index != self.rent_index:
                self.rerolls += 2; self.removals += 2
        return payout


class HeuristicAgent:
    def score_symbol(self, env, candidate):
        values, deck = env.catalog["symbol_values"], Counter(env.deck)
        score = values.get(candidate, 0.0)
        # 一次性资源与可成长符号的实际决策价值高于面板基础值。
        score += {"removal_capsule": 2.2, "reroll_capsule": 1.5,
                  "tedium_capsule": 4.0, "lucky_capsule": 2.0,
                  "chemical_seven": 3.0, "void_creature": 2.0,
                  "item_capsule": 4.0,
                  "hustler": 10.0,
                  "void_fruit": 2.0, "void_stone": 2.0,
                  "coal": 1.2, "present": 1.0}.get(candidate, 0)
        # 已有成套联动。
        partners = {
            "crab": 1.5 * deck["crab"], "cultist": 1.2 * deck["cultist"],
            "flower": 1.5 * deck["rain"], "rain": 1.2 * deck["flower"],
            "key": 1.5 * sum(deck[x] for x in ("lockbox", "safe", "treasure_chest")),
            "lockbox": 1.2 * deck["key"], "safe": 2.0 * deck["key"],
            "treasure_chest": 3.0 * deck["key"],
            "mouse": 1.8 * deck["cheese"], "cheese": 1.5 * deck["mouse"],
            "dwarf": 1.2 * (deck["beer"] + deck["wine"]),
            "beer": 1.0 * deck["dwarf"], "wine": 2.0 * deck["dwarf"],
            "bee": .8 * (deck["flower"] + deck["honey"]),
            "honey": .8 * (deck["bee"] + deck["bear"]),
        }
        score += partners.get(candidate, 0)
        if candidate == "essence_capsule":
            # 精华胶囊本转为-12，只有现金缓冲足够时才承担短期亏损。
            rent = env.state()["rent"]
            score += 14.0 if env.coins >= rent + 12 else 0.0
        if candidate in ("clubs", "spades", "hearts", "diamonds"):
            score += .6 * sum(deck[x] for x in ("clubs", "spades", "hearts", "diamonds"))
        if candidate == "ninja":
            score -= 1.2 * deck["ninja"]
        if candidate.startswith("hex_of_"):
            score -= 2.5
        if candidate in ("magpie", "thief"):
            score -= 1.0
        if candidate == "dud":
            score = -99
        return score

    def choose_symbol(self, env, candidates):
        best = max(candidates, key=lambda x: self.score_symbol(env, x), default=None)
        threshold = .8 if len(env.deck) < 20 else 2.0
        return best if env.force_add_next_choice or (best and self.score_symbol(env, best) >= threshold) else "skip"

    def choose_item(self, env, candidates):
        deck = Counter(env.deck)
        scores = {
            "egg_carton": 3.0,
            "pizza_the_cat": 1.0 + 2.0 * deck["cat"],
            "blue_pepper": 3.0 if len(env.deck) < 20 else 0.2,
            "red_suits": 1.0 + deck["hearts"] + deck["diamonds"],
            "blue_suits": 1.0 + deck["clubs"] + deck["spades"],
            "fifth_ace": 1.0 + sum(deck[x] for x in ("clubs", "spades", "hearts", "diamonds")),
            "tax_evasion": 1.0 + deck["magpie"],
        }
        return max(candidates, key=lambda x: scores.get(x, .5), default="skip")

    def choose_essence(self, env, candidates):
        # 精华效果逐项补全前，优先选与现有物品同名的精华。
        return max(candidates, key=lambda x: int(x.removesuffix("_essence") in env.items), default="skip")

    def choose_position(self, env, actions):
        """用即时反事实收益选择交换/重转动作。"""
        if len(actions) <= 1:
            return "skip"
        scores = []
        for action in actions:
            sim = copy.deepcopy(env)
            scores.append(sim.spin(action))
        return actions[max(range(len(actions)), key=scores.__getitem__)]

    def maybe_remove(self, env):
        if not env.removals or not env.deck:
            return
        vals = env.catalog["symbol_values"]
        worst = min(env.deck, key=lambda x: vals.get(x, 0))
        if vals.get(worst, 0) < 1:
            env.remove(worst)

    def maybe_interact(self, env):
        for action in env.available_interactions():
            if action == "use:comfy_pillow" and env.coins < env.state()["rent"]:
                continue
            env.interact(action)


class RolloutAgent(HeuristicAgent):
    """用环境本身进行短视反事实模拟的CPU教师。"""
    def __init__(self, horizon=3, trials=1):
        self.horizon, self.trials = horizon, trials

    def choose_symbol(self, env, candidates):
        options = list(candidates) + ([] if env.force_add_next_choice else ["skip"])
        scores = []
        for option in options:
            totals = []
            for trial in range(self.trials):
                sim = copy.deepcopy(env)
                # 公共随机数加小幅独立扰动，兼顾公平比较与方差覆盖。
                sim.rng.seed((env.seed or 0) ^ (env.total_spins * 1009) ^ (trial * 9176))
                sim.spins_left = 10000
                sim.choose(option)
                totals.append(sum(sim.spin() for _ in range(self.horizon)))
            # 牌组超过20后，低产符号占用抽取位置，加入轻度容量成本。
            capacity_cost = max(0, len(env.deck) - 19) * .08 if option != "skip" else 0
            scores.append(sum(totals) / len(totals) - capacity_cost)
        return options[max(range(len(options)), key=scores.__getitem__)]


def run_episode(catalog, seed=0, agent=None):
    env, agent = FastLandlordEnv(catalog, seed), agent or HeuristicAgent()
    while not env.done:
        rent_before = env.rent_index
        env.preview_spin()
        env.spin(agent.choose_position(env, env.position_interactions()))
        if env.done:
            break
        agent.maybe_interact(env)
        if env.pending_rent:
            env.decline_rent_rescue()
            break
        while env.pending_essence_choices:
            choices = env.candidates("essence")
            if not choices: env.pending_essence_choices -= 1; continue
            env.choose(agent.choose_essence(env, choices), "essence")
        while env.pending_symbol_groups or env.pending_symbol_rarities:
            forced = env.candidates("symbol")
            if not forced:
                if env.pending_symbol_groups: env.pending_symbol_groups.pop(0)
                elif env.pending_symbol_rarities: env.pending_symbol_rarities.pop(0)
                continue
            env.choose(max(forced, key=lambda x: env.catalog["symbol_values"].get(x, 0)))
        choices = env.candidates("symbol")
        env.choose(agent.choose_symbol(env, choices))
        agent.maybe_remove(env)
        while env.pending_item_choices:
            items = env.candidates("item")
            env.choose(agent.choose_item(env, items), "item")
    return {"won": env.won, "rents_paid": env.rent_index,
            "coins": round(env.coins, 2), "deck_size": len(env.deck)}
