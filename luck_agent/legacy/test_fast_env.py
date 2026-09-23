import unittest
from fast_env import FastLandlordEnv


CATALOG = {
    "symbol_values": {"flower": 1, "rain": 2, "crab": 1, "key": 1,
                      "lockbox": 1, "coin": 1, "d3": 2, "d5": 3,
                      "cat": 1, "milk": 1, "mouse": 1, "cheese": 1,
                      "cultist": 0, "turtle": 0, "ninja": 2, "oyster": 1,
                      "toddler": 1, "candy": 1, "pinata": 1,
                      "bee": 1, "flower": 1, "beehive": 3, "honey": 3,
                      "clubs": 1, "spades": 1, "hearts": 1, "diamonds": 1,
                      "chemical_seven": 0, "present": 0, "egg": 1,
                      "omelette": 3, "miner": 1, "ore": 1, "anchor": 1,
                      "coal": 0, "diamond": 5, "light_bulb": 1, "pearl": 1,
                      "dwarf": 1, "beer": 1, "crow": 2, "goose": 1,
                      "golden_egg": 4, "billionaire": 0, "goldfish": 1,
                      "bear": 2, "rabbit": 1, "rabbit_fluff": 2,
                      "urn": 1, "spirit": 4, "toddler": 1, "monkey": 1,
                      "banana": 1, "banana_peel": 1, "dog": 1, "wolf": 2,
                      "beastmaster": 2, "diver": 2, "archaeologist": 2,
                      "magic_key": 2, "mine": 4, "bartender": 3,
                      "cow": 3, "card_shark": 3,
                      "robin_hood": -4, "apple": 3,
                      "farmer": 2, "dame": 2, "martini": 3,
                      "strawberry": 3, "ruby": 3, "emerald": 3,
                      "general_zaroff": 1, "joker": 3, "king_midas": 1,
                      "chef": 2,
                      "witch": 2,
                      "target": 2, "buffing_powder": 0, "time_capsule": 0,
                      "seed": 1, "rare_plant": 4, "lucky_capsule": 0,
                      "pufferfish": 2, "hex_of_destruction": 3, "hex_of_tedium": 3,
                      "hex_of_draining": 3, "hex_of_emptiness": 3, "sloth": 0,
                      "hex_of_hoarding": 3, "hex_of_midas": 3, "hex_of_thievery": 3},
    "symbol_groups": {"candy": ["toddlerlikes"], "pinata": ["toddlerlikes"],
                      "bubble": ["toddlerlikes"], "flower": ["beelikes"],
                      "honey": ["beelikes"], "egg": ["omelettestuff"],
                      "ore": ["minerlikes"], "pearl": ["gem"],
                      "beer": ["dwarflikes"], "crow": ["bird", "animal"],
                      "egg": ["omelettestuff", "food"], "urn": ["spiritbox"],
                      "lockbox": ["chest"], "beer": ["dwarflikes", "booze"],
                      "toddler": ["halloween"], "pearl": ["gem", "kyle"],
                      "dog": ["animal"], "anchor": ["poslikes"],
                      "pearl": ["gem", "kyle", "archlikes"],
                      "lockbox": ["chest"], "clubs": ["suit"],
                      "coin": ["robinlikes"], "apple": ["robinhates"],
                      "seed": ["farmerlikes"], "martini": ["booze"],
                      "chef": ["human"], "witch": ["human"],
                      "hex_of_tedium": ["witchlikes"],
                      "egg": ["omelettestuff", "food", "chickenstuff"]},
    "symbol_pool": ["flower", "rain", "crab", "key", "lockbox", "coin"],
    "item_pool": ["egg_carton"],
    "symbol_candidate_counts": {}, "item_candidate_counts": {},
    "essence_pool": ["test_essence"], "essence_candidate_counts": {},
    "essence_rarity": {"test_essence": "essence"},
}


class RuleTests(unittest.TestCase):
    def env(self, deck, seed=0):
        env = FastLandlordEnv(CATALOG, seed=seed, floor=1)
        env.deck = list(deck)
        env.spins_left = 99
        return env

    def test_rain_increases_flower_payout(self):
        base = self.env(["flower", "rain"], seed=1)
        self.assertEqual(base.spin(), 4)  # 1+2，且相邻花额外+1

    def test_crabs_in_same_row_buff_each_other(self):
        env = self.env(["crab", "crab"], seed=1)
        self.assertEqual(env.spin(), 8)  # 基础2 + 双向各3

    def test_key_destroys_lockbox_and_awards_bonus(self):
        env = self.env(["key", "lockbox"], seed=1)
        self.assertEqual(env.spin(), 17)
        self.assertEqual(env.deck, [])

    def test_removal_consumes_one_token(self):
        env = self.env(["coin"])
        env.removals = 1
        self.assertTrue(env.remove("coin"))
        self.assertEqual(env.removals, 0)

    def test_egg_carton_absorbs_egg(self):
        env = self.env(["coin"])
        env.items.append("egg_carton")
        env.choose("egg")
        self.assertNotIn("egg", env.deck)
        self.assertEqual(env.spin(), 2)

    def test_pizza_cat_adds_one_per_cat(self):
        env = self.env(["cat"])
        env.items.append("pizza_the_cat")
        self.assertEqual(env.spin(), 2)

    def test_dwarf_consumes_beer(self):
        env = self.env(["dwarf", "beer"], seed=1)
        self.assertEqual(env.spin(), 12)
        self.assertEqual(env.deck, ["dwarf"])

    def test_removal_capsule_self_destructs_and_grants_token(self):
        env = self.env(["removal_capsule"])
        env.spin()
        self.assertEqual(env.removals, 1)
        self.assertEqual(env.deck, [])

    def test_dice_payout_is_in_valid_range(self):
        env = self.env(["d3"], seed=3)
        self.assertIn(env.spin(), (1, 2, 3))

    def test_miner_opens_ore_and_generates_gem(self):
        env = self.env(["miner", "ore"], seed=1)
        env.spin()
        self.assertEqual(len(env.deck), 2)
        self.assertIn("miner", env.deck)
        self.assertNotIn("ore", env.deck)

    def test_floor20_starts_with_three_duds(self):
        env = FastLandlordEnv(CATALOG, seed=1, floor=20)
        self.assertEqual(env.deck.count("dud"), 3)
        self.assertEqual(env.dud_ttls, [33, 33, 33])

    def test_floor20_duds_expire_and_periodic_dud_is_added(self):
        env = FastLandlordEnv(CATALOG, seed=1, floor=20)
        env.spins_left = 99
        for _ in range(33):
            env.spin()
        # 初始3个已消失；第15、30转加入的2个仍存在。
        self.assertEqual(env.deck.count("dud"), 2)

    def test_candidates_are_unique(self):
        env = self.env(["coin"])
        choices = env.candidates("symbol", 3)
        self.assertEqual(len(choices), len(set(choices)))

    def test_bubble_disappears_after_three_appearances(self):
        env = self.env(["bubble"])
        env.bubble_ttls = [3]
        env.spin(); env.spin(); env.spin()
        self.assertNotIn("bubble", env.deck)

    def test_dog_optional_interaction_is_recorded(self):
        env = self.env(["dog"])
        self.assertEqual(env.spin(), 3)
        self.assertEqual(env.last_interactions, ["pet_dog"])

    def test_banana_peel_destroys_thief_and_itself(self):
        env = self.env(["banana_peel", "thief"], seed=1)
        env.spin()
        self.assertEqual(env.deck, [])

    def test_gambler_is_cashed_when_die_rolls_one(self):
        found = False
        for seed in range(30):
            env = self.env(["gambler", "d3"], seed=seed)
            payout = env.spin()
            if "gambler" not in env.deck:
                self.assertGreaterEqual(payout, 4)
                found = True
                break
        self.assertTrue(found)

    def test_cat_consumes_milk(self):
        env = self.env(["cat", "milk"], seed=1)
        self.assertEqual(env.spin(), 11)
        self.assertEqual(env.deck, ["cat"])

    def test_mouse_consumes_cheese(self):
        env = self.env(["mouse", "cheese"], seed=1)
        self.assertEqual(env.spin(), 22)
        self.assertEqual(env.deck, ["mouse"])

    def test_three_cultists_pay_group_bonus(self):
        env = self.env(["cultist"] * 3)
        self.assertEqual(env.spin(), 9)

    def test_pool_ball_pays_each_spin(self):
        env = self.env(["coin"]); env.items.append("pool_ball")
        self.assertEqual(env.spin(), 2)

    def test_checkered_flag_shortens_turtle_cycle(self):
        env = self.env(["turtle"]); env.items.append("checkered_flag")
        self.assertEqual(env.spin(), 0)
        self.assertEqual(env.spin(), 4)

    def test_multiple_ninjas_reduce_each_other(self):
        env = self.env(["ninja", "ninja"])
        self.assertEqual(env.spin(), 2)

    def test_ninja_and_mouse_multiplies_adjacent_pair(self):
        env = self.env(["ninja", "mouse"], seed=1)
        env.items.append("ninja_and_mouse")
        self.assertEqual(env.spin(), 18)

    def test_oyster_eventually_generates_pearl(self):
        generated = False
        for seed in range(30):
            env = self.env(["oyster"], seed=seed)
            env.spin()
            if "pearl" in env.deck:
                generated = True; break
        self.assertTrue(generated)

    def test_rain_cloud_moves_rain_into_common_choices(self):
        catalog = dict(CATALOG)
        catalog["symbol_pool"] = ["rain", "ninja"]
        catalog["symbol_rarity"] = {"rain": "uncommon", "ninja": "uncommon"}
        env = FastLandlordEnv(catalog, seed=1, floor=1); env.items.append("rain_cloud")
        self.assertEqual(env.candidates("symbol", 1), ["rain"])

    def test_toddler_eats_candy(self):
        env = self.env(["toddler", "candy"], seed=1)
        self.assertEqual(env.spin(), 8)
        self.assertEqual(env.deck, ["toddler"])

    def test_toddler_breaks_pinata_into_seven_candy(self):
        env = self.env(["toddler", "pinata"], seed=1)
        env.spin()
        self.assertEqual(env.deck.count("candy"), 7)
        self.assertNotIn("pinata", env.deck)

    def test_bee_doubles_adjacent_flower(self):
        env = self.env(["bee", "flower"], seed=1)
        self.assertEqual(env.spin(), 3)

    def test_beehive_eventually_generates_honey(self):
        self.assertTrue(any(
            (lambda e: (e.spin(), "honey" in e.deck)[1])(self.env(["beehive"], seed=seed))
            for seed in range(100)
        ))

    def test_three_suits_get_threshold_and_same_color_bonus(self):
        env = self.env(["clubs", "hearts", "diamonds"], seed=1)
        self.assertEqual(env.spin(), 8)

    def test_fifth_ace_connects_opposite_color_suits(self):
        env = self.env(["clubs", "hearts"], seed=1)
        env.items.append("fifth_ace")
        self.assertEqual(env.spin(), 4)

    def test_red_suits_charges_then_generates_symbols_on_use(self):
        env = self.env(["coin"])
        env.items.append("red_suits")
        for _ in range(7):
            env.spin()
        self.assertEqual(env.available_interactions(), ["use:red_suits"])
        self.assertTrue(env.interact("use:red_suits"))
        self.assertNotIn("red_suits", env.items)
        self.assertIn("diamonds", env.deck)
        self.assertIn("hearts", env.deck)

    def test_treasure_map_charges_then_generates_key_and_chest(self):
        env = self.env(["coin"]); env.items.append("treasure_map")
        for _ in range(20): env.spin()
        self.assertTrue(env.interact("use:treasure_map"))
        self.assertIn("key", env.deck)
        self.assertIn("treasure_chest", env.deck)

    def test_three_lucky_sevens_pay_and_are_consumed(self):
        env = self.env(["coin"]); env.items.extend(["lucky_seven"] * 3)
        self.assertEqual(env.spin(), 78)
        self.assertNotIn("lucky_seven", env.items)

    def test_chemical_seven_creates_one_lucky_seven(self):
        env = self.env(["chemical_seven"])
        self.assertEqual(env.spin(), 7)
        self.assertEqual(env.items.count("lucky_seven"), 1)
        self.assertNotIn("chemical_seven", env.deck)

    def test_present_breaks_on_twelfth_appearance(self):
        env = self.env(["present"]); env.present_ttls = [12]
        for _ in range(11): self.assertEqual(env.spin(), 0)
        self.assertEqual(env.spin(), 10)
        self.assertNotIn("present", env.deck)

    def test_frying_pan_turns_adjacent_eggs_into_omelettes(self):
        env = self.env(["egg", "egg"], seed=1); env.items.append("frying_pan")
        env.spin()
        self.assertEqual(env.deck.count("egg"), 0)
        self.assertEqual(env.deck.count("omelette"), 2)

    def test_mining_pick_adds_ten_when_ore_is_destroyed(self):
        env = self.env(["miner", "ore"], seed=1); env.items.append("mining_pick")
        self.assertEqual(env.spin(), 12)

    def test_anchor_pays_four_extra_in_corner(self):
        env = self.env(["anchor"])
        self.assertEqual(env.spin(), 5)

    def test_coal_becomes_diamond_on_twentieth_appearance(self):
        env = self.env(["coal"]); env.coal_ttls = [20]
        for _ in range(20): env.spin()
        self.assertNotIn("coal", env.deck)
        self.assertIn("diamond", env.deck)

    def test_light_bulb_doubles_gem_then_expires(self):
        env = self.env(["light_bulb", "pearl"], seed=1); env.light_bulb_uses = [0]
        for _ in range(4): self.assertEqual(env.spin(), 3)
        self.assertEqual(env.spin(), 3)
        self.assertNotIn("light_bulb", env.deck)

    def test_white_pepper_pays_three_each_spin(self):
        env = self.env(["coin"]); env.items.append("white_pepper")
        self.assertEqual(env.spin(), 4)

    def test_brown_pepper_pays_for_generated_symbols(self):
        env = self.env(["egg", "egg"], seed=1)
        env.items.extend(["frying_pan", "brown_pepper"])
        self.assertEqual(env.spin(), 4)

    def test_dwarven_anvil_doubles_dwarf(self):
        env = self.env(["dwarf", "beer"], seed=1); env.items.append("dwarven_anvil")
        self.assertEqual(env.spin(), 13)

    def test_adoption_papers_queues_three_animal_choices(self):
        catalog = dict(CATALOG)
        catalog["symbol_pool"] = ["cat", "dog", "coin"]
        catalog["symbol_groups"] = dict(CATALOG["symbol_groups"], cat=["animal"], dog=["animal"])
        env = FastLandlordEnv(catalog, seed=1, floor=1)
        env.items.append("adoption_papers")
        self.assertTrue(env.interact("use:adoption_papers"))
        self.assertEqual(env.candidates("symbol", 3), ["cat", "dog"])
        env.choose("cat")
        self.assertEqual(len(env.pending_symbol_groups), 2)

    def test_crow_loses_three_every_fourth_appearance(self):
        env = self.env(["crow"])
        self.assertEqual([env.spin() for _ in range(4)], [2, 2, 2, -1])

    def test_goose_eventually_generates_golden_egg(self):
        self.assertTrue(any(
            (lambda e: (e.spin(), "golden_egg" in e.deck)[1])(self.env(["goose"], seed=s))
            for s in range(1000)
        ))

    def test_green_pepper_pays_for_three_matching_symbols(self):
        env = self.env(["coin"] * 3); env.items.append("green_pepper")
        self.assertEqual(env.spin(), 6)

    def test_cyan_pepper_pays_when_no_symbol_appears_three_times(self):
        env = self.env(["coin", "flower"]); env.items.append("cyan_pepper")
        self.assertEqual(env.spin(), 5)

    def test_gray_pepper_pays_when_removal_token_is_spent(self):
        env = self.env(["coin"]); env.items.append("gray_pepper"); env.removals = 1
        env.remove("coin")
        self.assertEqual(env.coins, 6)

    def test_lime_pepper_pays_when_reroll_token_is_spent(self):
        env = self.env(["coin"]); env.items.append("lime_pepper"); env.rerolls = 1
        env.reroll()
        self.assertEqual(env.coins, 6)

    def test_guillotine_destroys_billionaire_for_39(self):
        env = self.env(["billionaire"]); env.items.append("guillotine")
        self.assertEqual(env.spin(), 39)
        self.assertNotIn("billionaire", env.deck)

    def test_reroll_item_rethrows_low_d3_once(self):
        env = self.env(["d3"], seed=1); env.items.append("reroll")
        self.assertEqual(env.spin(), 3)

    def test_pink_pepper_pays_when_choice_is_skipped(self):
        env = self.env(["coin"]); env.items.append("pink_pepper")
        env.choose("skip")
        self.assertEqual(env.coins, 2)

    def test_lunchbox_queues_three_food_choices(self):
        catalog = dict(CATALOG); catalog["symbol_pool"] = ["egg", "coin"]
        env = FastLandlordEnv(catalog, seed=1, floor=1); env.items.append("lunchbox")
        self.assertTrue(env.interact("use:lunchbox"))
        self.assertEqual(env.pending_symbol_groups, ["food"] * 3)

    def test_small_symbol_bomb_queues_two_unrestricted_choices(self):
        env = self.env(["coin"]); env.items.append("symbol_bomb_small")
        self.assertTrue(env.interact("use:symbol_bomb_small"))
        self.assertEqual(env.pending_symbol_groups, ["__any__"] * 2)

    def test_red_pepper_pays_when_all_displayed_symbols_are_unique(self):
        env = self.env(["coin", "flower"]); env.items.append("red_pepper")
        self.assertEqual(env.spin(), 7)

    def test_yellow_pepper_pays_when_board_is_full(self):
        env = self.env(["coin"] * 20); env.items.append("yellow_pepper")
        self.assertEqual(env.spin(), 22)

    def test_purple_pepper_pays_for_connected_triple(self):
        env = self.env(["coin"] * 3); env.items.append("purple_pepper")
        self.assertEqual(env.spin(), 8)

    def test_birdhouse_adds_one_per_bird(self):
        env = self.env(["crow"]); env.items.append("birdhouse")
        self.assertEqual(env.spin(), 3)

    def test_black_pepper_pays_per_destroyed_symbol(self):
        env = self.env(["removal_capsule"]); env.items.append("black_pepper")
        self.assertEqual(env.spin(), 2)

    def test_turtle_and_rabbit_can_trigger_for_77(self):
        triggered = False
        for seed in range(100):
            env = self.env(["rabbit"] + ["coin"] * 18 + ["turtle"], seed=seed)
            env.items.append("turtle_and_rabbit")
            if env.spin() >= 96:
                self.assertNotIn("turtle_and_rabbit", env.items)
                triggered = True; break
        self.assertTrue(triggered)

    def test_fish_bowl_absorbs_goldfish_and_pays_each_spin(self):
        env = self.env(["coin"]); env.items.append("fish_bowl")
        env.choose("goldfish")
        self.assertNotIn("goldfish", env.deck)
        self.assertEqual(env.spin(), 2)

    def test_happy_hour_adds_one_to_booze(self):
        env = self.env(["beer"]); env.items.append("happy_hour")
        self.assertEqual(env.spin(), 2)

    def test_jackolantern_doubles_halloween_symbol(self):
        env = self.env(["toddler"]); env.items.append("jackolantern")
        self.assertEqual(env.spin(), 2)

    def test_kyle_adds_one_to_kyle_group(self):
        env = self.env(["pearl"]); env.items.append("kyle_the_kernite")
        self.assertEqual(env.spin(), 2)

    def test_maxwell_multiplies_bear_by_one_point_five(self):
        env = self.env(["bear"]); env.items.append("maxwell_the_bear")
        self.assertEqual(env.spin(), 3)

    def test_nori_adds_one_to_rabbit(self):
        env = self.env(["rabbit"]); env.items.append("nori_the_rabbit")
        self.assertEqual(env.spin(), 2)

    def test_lockpick_eventually_opens_lockbox(self):
        self.assertTrue(any(
            (lambda e: (e.spin(), "lockbox" not in e.deck)[1])(
                (lambda e: (e.items.append("lockpick"), e)[1])(self.env(["lockbox"], seed=s)))
            for s in range(30)))

    def test_grave_robber_eventually_breaks_urn_into_spirit(self):
        found = False
        for seed in range(30):
            env = self.env(["urn"], seed=seed); env.items.append("grave_robber")
            env.spin()
            if "urn" not in env.deck:
                self.assertIn("spirit", env.deck); found = True; break
        self.assertTrue(found)

    def test_oswald_doubles_monkey(self):
        env = self.env(["monkey"]); env.items.append("oswald_the_monkey")
        self.assertEqual(env.spin(), 2)

    def test_ricky_adds_two_to_banana(self):
        env = self.env(["banana"]); env.items.append("ricky_the_banana")
        self.assertEqual(env.spin(), 3)

    def test_quigley_turns_displayed_dog_into_wolf(self):
        env = self.env(["dog"]); env.items.append("quigley_the_wolf")
        env.spin()
        self.assertNotIn("dog", env.deck)
        self.assertIn("wolf", env.deck)

    def test_rabbit_gains_two_permanently_every_ten_appearances(self):
        env = self.env(["rabbit"])
        self.assertEqual([env.spin() for _ in range(10)][-1], 3)
        self.assertEqual(env.spin(), 3)

    def test_shedding_season_eventually_generates_fluff(self):
        found = False
        for seed in range(50):
            env = self.env(["rabbit"], seed=seed); env.items.append("shedding_season")
            env.spin()
            if "rabbit_fluff" in env.deck: found = True; break
        self.assertTrue(found)

    def test_arrow_eventually_destroys_target_for_ten(self):
        found = False
        for seed in range(100):
            env = self.env(["bronze_arrow", "target"], seed=seed)
            if env.spin() >= 15:
                self.assertNotIn("target", env.deck); found = True; break
        self.assertTrue(found)

    def test_watering_can_adds_twelve_to_seed(self):
        env = self.env(["seed"]); env.items.append("watering_can")
        self.assertEqual(env.spin(), 13)

    def test_shattered_mirror_pays_twenty_four_every_seven_spins(self):
        env = self.env(["coin"]); env.items.append("shattered_mirror"); env.spins_left = 100
        payouts = [env.spin() for _ in range(7)]
        self.assertEqual(payouts[:6], [1] * 6)
        self.assertEqual(payouts[6], 25)

    def test_time_machine_shortens_coal_by_five_appearances(self):
        env = self.env(["coal"]); env.items.append("time_machine"); env.spins_left = 100
        for _ in range(15): env.spin()
        self.assertNotIn("coal", env.deck)
        self.assertIn("diamond", env.deck)

    def test_piggy_bank_can_be_cashed_out_to_rescue_rent(self):
        env = self.env(["coin"]); env.items.append("piggy_bank")
        env.coins = 20; env.spins_left = 1; env.item_counters["piggy_bank"] = 2
        env.spin()
        self.assertTrue(env.pending_rent)
        self.assertIn("cashout:piggy_bank", env.available_interactions())
        env.interact("cashout:piggy_bank")
        self.assertFalse(env.done)
        self.assertEqual(env.rent_index, 1)

    def test_swear_jar_saves_one_per_spin_and_cashout_triples_it(self):
        env = self.env(["coin"]); env.items.append("swear_jar"); env.spins_left = 100
        self.assertEqual(env.spin(), 0)
        self.assertEqual(env.item_counters["swear_jar"], 1)
        env.pending_rent = True; env.coins = 22
        env.interact("cashout:swear_jar")
        self.assertEqual(env.rent_index, 1)

    def test_comfy_pillow_skips_last_spin_and_forces_rare_item(self):
        catalog = dict(CATALOG) | {"item_pool": ["rare_item", "common_item"],
                                  "item_rarity": {"rare_item": "rare", "common_item": "common"}}
        env = FastLandlordEnv(catalog, seed=0, floor=1); env.deck = ["coin"]
        env.items.append("comfy_pillow")
        env.coins = 25; env.spins_left = 1
        self.assertIn("use:comfy_pillow", env.available_interactions())
        env.interact("use:comfy_pillow")
        self.assertEqual(env.rent_index, 1)
        choices = env.candidates("item")
        self.assertTrue(choices)
        self.assertTrue(all(env.catalog["item_rarity"].get(x) == "rare" for x in choices))

    def test_bear_destroys_adjacent_honey_for_forty(self):
        env = self.env(["bear", "honey"])
        self.assertEqual(env.spin(), 45)
        self.assertNotIn("honey", env.deck)

    def test_dark_humor_moves_comedian_to_uncommon_choices(self):
        catalog = dict(CATALOG) | {"symbol_pool": ["comedian"],
          "symbol_rarity": {"comedian": "rare"}, "symbol_candidate_counts": {}}
        env = FastLandlordEnv(catalog, seed=0, floor=1); env.items.append("dark_humor")
        env.rent_index = 1
        self.assertEqual(env.candidates("symbol"), ["comedian"])

    def test_buffing_powder_doubles_adjacent_symbol_and_destroys_itself(self):
        env = self.env(["buffing_powder", "coin"])
        self.assertEqual(env.spin(), 2)
        self.assertNotIn("buffing_powder", env.deck)

    def test_time_capsule_restores_last_destroyed_symbol(self):
        env = self.env(["time_capsule"]); env.destroyed_history.append("honey")
        env.spin()
        self.assertNotIn("time_capsule", env.deck)
        self.assertIn("honey", env.deck)

    def test_compost_heap_generates_seed_each_three_destructions(self):
        env = self.env(["removal_capsule"] * 3); env.items.append("compost_heap")
        env.spin()
        self.assertIn("seed", env.deck)
        self.assertEqual(env.item_counters["compost_heap"], 0)

    def test_fertilizer_forces_seed_to_grow_into_rare_plant(self):
        catalog = dict(CATALOG)
        catalog["symbol_pool"] = ["flower", "rare_plant"]
        catalog["symbol_groups"] = dict(CATALOG["symbol_groups"]) | {"flower": ["plant"], "rare_plant": ["plant"]}
        catalog["symbol_rarity"] = {"flower": "common", "rare_plant": "rare"}
        env = FastLandlordEnv(catalog, seed=0, floor=1); env.deck=["seed"]
        env.items.extend(["fertilizer", "fertilizer"]); env.spins_left=99
        env.spin()
        self.assertEqual(env.deck, ["rare_plant"])

    def test_dark_humor_lets_comedian_triple_adjacent_dark_group(self):
        catalog = dict(CATALOG)
        catalog["symbol_values"] = dict(CATALOG["symbol_values"]) | {"comedian": 3}
        catalog["symbol_groups"] = dict(CATALOG["symbol_groups"]) | {"beer": ["darkhumor"]}
        env = FastLandlordEnv(catalog, seed=0, floor=1); env.deck=["comedian", "beer"]
        env.items.append("dark_humor"); env.spins_left=99
        self.assertEqual(env.spin(), 6)

    def test_essence_capsule_grants_choice_after_next_rent(self):
        env = self.env(["essence_capsule"]); env.coins=40; env.spins_left=1
        env.spin()
        self.assertEqual(env.pending_essence_choices, 1)
        self.assertEqual(env.candidates("essence"), ["test_essence"])
        env.choose("test_essence", "essence")
        self.assertIn("test_essence", env.essences)

    def test_item_capsule_adds_common_item_and_destroys_itself(self):
        catalog = dict(CATALOG) | {"item_pool":["common_item"], "item_rarity":{"common_item":"common"}}
        env = FastLandlordEnv(catalog, seed=0, floor=1); env.deck=["item_capsule"]; env.spins_left=99
        env.spin()
        self.assertNotIn("item_capsule", env.deck)
        self.assertIn("common_item", env.items)

    def test_hustler_becomes_pool_ball_item(self):
        env = self.env(["hustler"]); env.spin()
        self.assertNotIn("hustler", env.deck)
        self.assertIn("pool_ball", env.items)

    def test_golem_breaks_into_five_ore_after_five_appearances(self):
        env = self.env(["golem"])
        for _ in range(5): env.spin()
        self.assertNotIn("golem", env.deck)
        self.assertEqual(env.deck.count("ore"), 5)

    def test_lucky_capsule_self_destructs_for_ten(self):
        env = self.env(["lucky_capsule"])
        self.assertEqual(env.spin(), 10)
        self.assertNotIn("lucky_capsule", env.deck)

    def test_removing_pufferfish_grants_reroll(self):
        env = self.env(["pufferfish"]); env.removals=1
        self.assertTrue(env.remove("pufferfish"))
        self.assertEqual(env.rerolls, 1)

    def test_hex_of_destruction_eventually_destroys_neighbor(self):
        self.assertTrue(any(
            (lambda e:(e.spin(),len(e.deck)<2)[1])(self.env(["hex_of_destruction","coin"],seed=s))
            for s in range(30)))

    def test_hex_of_tedium_reduces_high_rarity_weight(self):
        catalog=dict(CATALOG) | {"symbol_pool":["coin","rare_symbol"],
          "symbol_rarity":{"coin":"common","rare_symbol":"rare"}}
        plain_rare=cursed_rare=0
        for seed in range(300):
            plain=FastLandlordEnv(catalog,seed=seed,floor=1); plain.rent_index=6
            cursed=FastLandlordEnv(catalog,seed=seed,floor=1); cursed.rent_index=6
            cursed.last_shown=["hex_of_tedium"]*5
            plain_rare += plain.candidates("symbol",n=1)==["rare_symbol"]
            cursed_rare += cursed.candidates("symbol",n=1)==["rare_symbol"]
        self.assertLess(cursed_rare, plain_rare)

    def test_xray_machine_makes_ore_generate_rare_gem(self):
        catalog=dict(CATALOG)
        catalog["symbol_pool"]=["pearl","ruby"]
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"pearl":["gem"],"ruby":["gem"]}
        catalog["symbol_rarity"]={"pearl":"common","ruby":"rare"}
        env=FastLandlordEnv(catalog,seed=0,floor=1); env.deck=["miner","ore"]
        env.items.append("x_ray_machine"); env.spins_left=99; env.spin()
        self.assertIn("ruby",env.deck)

    def test_first_matryoshka_upgrades_after_three_appearances(self):
        env=self.env(["matryoshka_doll_1"])
        for _ in range(3): env.spin()
        self.assertEqual(env.deck,["matryoshka_doll_2"])

    def test_rarity_capsule_queues_rare_or_better_choice(self):
        catalog=dict(CATALOG)|{"symbol_pool":["coin","rare_symbol"],
          "symbol_rarity":{"coin":"common","rare_symbol":"rare"}}
        env=FastLandlordEnv(catalog,seed=0,floor=1); env.deck=["rarity_capsule"]; env.spins_left=99
        env.spin()
        self.assertEqual(env.candidates("symbol"),["rare_symbol","coin"])
        self.assertEqual(env.pending_symbol_rarities,[])
        env.choose("coin")
        self.assertEqual(env.rare_candidate_slots,0)

    def test_bar_of_soap_generates_three_bubbles_then_destroys(self):
        env=self.env(["bar_of_soap"])
        for _ in range(3): env.spin()
        self.assertNotIn("bar_of_soap",env.deck)
        self.assertEqual(env.deck.count("bubble"),3)

    def test_black_cat_pays_nine_and_doubles_cat(self):
        env=self.env(["cat"]); env.items.append("black_cat")
        self.assertEqual(env.spin(),11)

    def test_cursed_katana_reverses_duplicate_ninja_penalty(self):
        env=self.env(["ninja","ninja"]); env.items.append("cursed_katana")
        self.assertEqual(env.spin(),6)

    def test_hex_of_draining_eventually_zeroes_neighbor(self):
        self.assertTrue(any(self.env(["hex_of_draining","coin"],seed=s).spin()==3 for s in range(30)))

    def test_sloth_pays_four_every_second_appearance(self):
        env=self.env(["sloth"])
        self.assertEqual([env.spin(),env.spin()],[0,4])

    def test_rusty_gear_doubles_connected_triple(self):
        env=self.env(["coin","coin","coin"]); env.items.append("rusty_gear")
        self.assertEqual(env.spin(),6)

    def test_cardboard_box_grants_removal_every_ten_spins(self):
        env=self.env(["coin"]); env.items.append("cardboard_box")
        for _ in range(10): env.spin()
        self.assertEqual(env.removals,1)

    def test_barrel_of_dwarves_active_interaction_adds_seven(self):
        env=self.env(["coin"]); env.items.append("barrel_o_dwarves")
        env.interact("use:barrel_o_dwarves")
        self.assertEqual(env.deck.count("dwarf"),7)

    def test_goldilocks_active_interaction_adds_three_bears(self):
        env=self.env(["coin"]); env.items.append("goldilocks")
        env.interact("use:goldilocks")
        self.assertEqual(env.deck.count("bear"),3)

    def test_quantum_bomb_queues_nine_symbol_choices(self):
        env=self.env(["coin"]); env.items.append("symbol_bomb_quantum")
        env.interact("use:symbol_bomb_quantum")
        self.assertEqual(env.pending_symbol_groups,["__any__"]*9)

    def test_hex_of_emptiness_eventually_forces_skip(self):
        found=False
        for seed in range(30):
            env=self.env(["hex_of_emptiness"],seed=seed); env.spin()
            if env.force_skip_next_choice:
                self.assertEqual(env.candidates("symbol"),[]); found=True; break
        self.assertTrue(found)

    def test_hex_of_hoarding_eventually_forces_add(self):
        self.assertTrue(any((lambda e:(e.spin(),e.force_add_next_choice)[1])(
            self.env(["hex_of_hoarding"],seed=s)) for s in range(30)))

    def test_hex_of_midas_eventually_adds_coin(self):
        self.assertTrue(any((lambda e:(e.spin(),e.deck.count("coin")>0)[1])(
            self.env(["hex_of_midas"],seed=s)) for s in range(30)))

    def test_hex_of_thievery_eventually_subtracts_six(self):
        self.assertTrue(any(self.env(["hex_of_thievery"],seed=s).spin()==-3 for s in range(30)))

    def test_removing_jellyfish_refunds_removal(self):
        env=self.env(["jellyfish"]);env.removals=1;env.remove("jellyfish")
        self.assertEqual(env.removals,1)

    def test_removing_sand_dollar_grants_ten(self):
        env=self.env(["sand_dollar"]);env.removals=1;env.remove("sand_dollar")
        self.assertEqual(env.coins,10)

    def test_lefty_doubles_left_column_rabbit_and_sheds_fluff(self):
        env=self.env(["rabbit"]);env.items.append("lefty_the_rabbit")
        self.assertEqual(env.spin(),2)
        for _ in range(9):env.spin()
        self.assertIn("rabbit_fluff",env.deck)

    def test_flush_moves_suits_into_common_pool(self):
        catalog=dict(CATALOG)|{"symbol_pool":["coin","clubs"],
          "symbol_rarity":{"coin":"common","clubs":"uncommon"}}
        seen=False
        for seed in range(30):
            env=FastLandlordEnv(catalog,seed=seed,floor=1);env.items.append("flush")
            if env.candidates("symbol",n=1)==["clubs"]:seen=True;break
        self.assertTrue(seen)

    def test_big_symbol_bomb_queues_four_choices(self):
        env=self.env(["coin"]);env.items.append("symbol_bomb_big")
        self.assertTrue(env.interact("use:symbol_bomb_big"))
        self.assertEqual(env.pending_symbol_groups,["__any__"]*4)

    def test_cleaning_rag_and_fruit_basket_add_one_per_matching_symbol(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"cherry":1}
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{
            "pearl":["gem"],"cherry":["fruit"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["pearl","cherry"]
        env.items.extend(["cleaning_rag","fruit_basket"]);env.spins_left=99
        self.assertEqual(env.spin(),4)

    def test_coin_on_a_string_provides_one_each_spin(self):
        env=self.env(["coin"]);env.items.append("coin_on_a_string")
        self.assertEqual(env.spin(),2)

    def test_zaroffs_contract_lets_bounty_hunter_destroy_human_for_25(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"bounty_hunter":1,"chef":3}
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"chef":["human","organism"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["bounty_hunter","chef"]
        env.items.append("zaroffs_contract");env.spins_left=99
        self.assertEqual(env.spin(),29)
        self.assertEqual(env.deck,["bounty_hunter"])

    def test_shrine_adds_spirit_when_organism_is_destroyed(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"bounty_hunter":1,"chef":3}
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"chef":["human","organism"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["bounty_hunter","chef"]
        env.items.extend(["zaroffs_contract","shrine"]);env.spins_left=99
        env.spin()
        self.assertEqual(env.deck,["bounty_hunter","spirit"])

    def test_conveyor_belt_increases_beehive_spawn_probability(self):
        plain=belt=0
        for seed in range(400):
            a=self.env(["beehive"],seed);a.spin();plain += "honey" in a.deck
            b=self.env(["beehive"],seed);b.items.append("conveyor_belt");b.spin();belt += "honey" in b.deck
        self.assertGreater(belt,plain)

    def test_horseshoe_provides_two_each_spin(self):
        env=self.env(["coin"]);env.items.append("horseshoe")
        self.assertEqual(env.spin(),3)

    def test_lemon_provides_one_per_empty_position(self):
        env=self.env(["coin"]);env.items.append("lemon")
        self.assertEqual(env.spin(),20)

    def test_ritual_candle_adds_one_to_fossil_likes(self):
        catalog=dict(CATALOG)
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"cultist":["fossillikes"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["cultist"]
        env.items.append("ritual_candle");env.spins_left=99
        self.assertEqual(env.spin(),1)

    def test_triple_coins_makes_coin_worth_three(self):
        env=self.env(["coin"]);env.items.append("triple_coins")
        self.assertEqual(env.spin(),3)

    def test_looting_glove_multiplies_destroyed_box_by_one_point_five(self):
        catalog=dict(CATALOG)
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"lockbox":["chest","box"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["key","lockbox"]
        env.items.append("looting_glove");env.spins_left=99
        self.assertEqual(env.spin(),25)

    def test_wanted_poster_multiplies_destroyed_thief_payout(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"bounty_hunter":1,"thief":1}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["bounty_hunter","thief"]
        env.items.append("wanted_poster");env.spins_left=99
        self.assertEqual(env.spin(),74.5)

    def test_spirit_disappears_after_four_payouts(self):
        env=self.env(["spirit"])
        for _ in range(4): env.spin()
        self.assertNotIn("spirit",env.deck)

    def test_moon_triples_adjacent_night_symbol(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"moon":3,"wolf":2}
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"wolf":["night"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["moon","wolf"];env.spins_left=99
        self.assertEqual(env.spin(),9)

    def test_sun_quintuples_adjacent_flower(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"sun":3}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["sun","flower"];env.spins_left=99
        self.assertEqual(env.spin(),8)

    def test_pear_gains_permanent_value_when_multiplied_by_chef(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"chef":2,"pear":1}
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"pear":["food","scaler"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["chef","pear"];env.spins_left=99
        env.spin()
        self.assertEqual(env.permanent_bonuses["pear"],1)

    def test_amethyst_gains_permanent_value_when_multiplied_by_dame(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"dame":2,"amethyst":1}
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"amethyst":["gem","scaler"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["dame","amethyst"];env.spins_left=99
        env.spin()
        self.assertEqual(env.permanent_bonuses["amethyst"],1)

    def test_dove_prevents_adjacent_symbol_destruction(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"dove":2}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["dove","key","lockbox"];env.spins_left=99
        env.spin()
        self.assertIn("lockbox",env.deck)

    def test_capsule_machine_doubles_capsule_reward(self):
        env=self.env(["removal_capsule"]);env.items.append("capsule_machine")
        env.spin()
        self.assertEqual(env.removals,2)

    def test_void_party_moves_void_symbols_to_common_pool(self):
        catalog=dict(CATALOG)|{"symbol_pool":["coin","void_creature"],
          "symbol_rarity":{"coin":"common","void_creature":"uncommon"}}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.items.append("void_party")
        seen=any((lambda e:e.candidates("symbol",1)==["void_creature"])(
            FastLandlordEnv(catalog,seed=s,floor=1)) for s in range(30))
        # 为每个试验环境加上物品，避免依赖当前env的随机状态。
        seen=False
        for seed in range(30):
            trial=FastLandlordEnv(catalog,seed=seed,floor=1);trial.items.append("void_party")
            if trial.candidates("symbol",1)==["void_creature"]: seen=True;break
        self.assertTrue(seen)

    def test_protractor_triggers_every_third_spin(self):
        env=self.env(["coin"]);env.items.append("protractor")
        env.spin();env.spin();env.spin()
        self.assertEqual(env.item_counters["protractor"],0)

    def test_lint_roller_removes_all_fluff_before_spin_for_twelve_each(self):
        env=self.env(["rabbit_fluff","rabbit_fluff","coin"]);env.items.append("lint_roller")
        self.assertEqual(env.spin(),25)
        self.assertNotIn("rabbit_fluff",env.deck)

    def test_holy_water_adds_one_and_disables_hex_effect(self):
        catalog=dict(CATALOG)
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"hex_of_thievery":["hex"]}
        env=FastLandlordEnv(catalog,seed=1,floor=1);env.deck=["hex_of_thievery"]
        env.items.append("holy_water");env.spins_left=99
        self.assertEqual(env.spin(),4)

    def test_dishwasher_grants_essence_token_every_twelve_spins(self):
        env=self.env(["coin"]);env.items.append("dishwasher")
        for _ in range(12): env.spin()
        self.assertEqual(env.essence_tokens,1)

    def test_chicken_eventually_generates_an_egg(self):
        self.assertTrue(any((lambda e:(e.spin(),len(e.deck)>1)[1])(
            self.env(["chicken"],seed=s)) for s in range(200)))

    def test_frozen_fossil_becomes_eldritch_beast_after_twenty(self):
        env=self.env(["frozen_fossil"])
        for _ in range(20): env.spin()
        self.assertEqual(env.deck,["eldritch_beast"])

    def test_mrs_fruit_destroys_fruit_and_grows_permanently(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"mrs_fruit":2,"peach":2}
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"peach":["fruitlikes"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1);env.deck=["mrs_fruit","peach"]
        env.spins_left=99;env.spin()
        self.assertNotIn("peach",env.deck)
        self.assertEqual(env.permanent_bonuses["mrs_fruit"],1)
        self.assertIn("seed",env.deck)

    def test_coffee_allows_one_extra_spin_when_rent_is_unaffordable(self):
        env=self.env(["coin"]);env.items.append("coffee");env.coins=0;env.spins_left=1
        env.spin()
        self.assertTrue(env.pending_rent)
        self.assertTrue(env.interact("use:coffee"))
        self.assertEqual(env.spins_left,1)
        self.assertFalse(env.done)

    def test_devils_deal_skips_rent_and_adds_six_duds(self):
        env=self.env(["coin"]);env.items.append("devils_deal");env.coins=0;env.spins_left=1
        env.spin()
        self.assertTrue(env.interact("use:devils_deal"))
        self.assertEqual(env.rent_index,1)
        self.assertEqual(env.deck.count("dud"),6)

    def test_swapping_device_exposes_pair_actions_and_changes_adjacency(self):
        env=self.env(["key","coin","coin","coin","lockbox"])
        env.items.append("swapping_device")
        env.pending_shown=["key","coin","coin","coin","lockbox"]
        self.assertIn("swap:1:4",env.position_interactions())
        env.spin("swap:1:4")
        self.assertNotIn("lockbox",env.deck)

    def test_oil_can_exposes_columns_on_fifth_spin_and_resets_charge(self):
        env=self.env(["coin"]);env.items.append("oil_can")
        env.item_counters["oil_can"]=4
        env.preview_spin()
        self.assertIn("respin:0",env.position_interactions())
        env.spin("respin:0")
        self.assertEqual(env.item_counters["oil_can"],0)

    def test_oil_can_respin_preserves_deck_multiplicity(self):
        env=self.env(["light_bulb"]+["coin"]*19);env.items.append("oil_can")
        env.item_counters["oil_can"]=5
        env.pending_shown=["light_bulb"]+["coin"]*19
        env.spin("respin:1")
        self.assertLessEqual(env.last_shown.count("light_bulb"),1)

    def test_beastmaster_doubles_adjacent_animal(self):
        env=self.env(["beastmaster","dog"])
        env.pending_shown=["beastmaster","dog"]
        self.assertEqual(env.spin(),6)  # 基础3、抚摸狗+2、驯兽师使狗额外+1

    def test_clear_sky_connects_sun_to_distant_flower(self):
        plain=self.env(["sun"]+["coin"]*18+["flower"])
        plain.pending_shown=["sun"]+["coin"]*18+["flower"]
        clear=self.env(["sun"]+["coin"]*18+["flower"]);clear.items.append("clear_sky")
        clear.pending_shown=["sun"]+["coin"]*18+["flower"]
        self.assertEqual(clear.spin()-plain.spin(),4*clear.catalog["symbol_values"]["flower"])

    def test_diver_consumes_all_adjacent_targets_and_grows(self):
        env=self.env(["anchor","diver","anchor"])
        env.pending_shown=["anchor","diver","anchor"]
        env.spin()
        self.assertEqual(env.deck,["diver"])
        self.assertEqual(env.permanent_bonuses["diver"],2)

    def test_archaeologist_consumes_adjacent_target_and_grows(self):
        env=self.env(["archaeologist","pearl"])
        env.pending_shown=["archaeologist","pearl"]
        env.spin()
        self.assertEqual(env.deck,["archaeologist"])
        self.assertEqual(env.permanent_bonuses["archaeologist"],1)

    def test_magic_key_triples_chest_and_destroys_both(self):
        env=self.env(["magic_key","lockbox"])
        env.pending_shown=["magic_key","lockbox"]
        self.assertEqual(env.spin(),50)  # 魔法钥匙2 + 宝箱(1+15)×3
        self.assertEqual(env.deck,[])

    def test_mine_generates_four_ore_then_becomes_mining_pick(self):
        env=self.env(["mine"])
        for _ in range(4):
            env.pending_shown=["mine"]
            env.spin()
        self.assertNotIn("mine",env.deck)
        self.assertEqual(env.deck.count("ore"),4)
        self.assertIn("mining_pick",env.items)

    def test_void_portal_counts_all_destroyed_instances_in_eights(self):
        env=self.env(["coin"])
        env.destroyed_history=["old"]*16
        env.destroyed_count=16
        env.choose("void_portal","item")
        env.pending_shown=["coin"]
        self.assertEqual(env.spin(),3)
        self.assertEqual(env.item_counters["void_portal_value"],2)

    def test_bartender_and_cow_generate_at_guaranteed_roll(self):
        env=self.env(["bartender","cow"])
        env.pending_shown=["bartender","cow"]
        env.rng.random=lambda: 0.0
        env.rng.choice=lambda choices: choices[0]
        env.spin()
        self.assertIn("milk",env.deck)
        self.assertTrue(any(s in ("beer","wine","martini") for s in env.deck))

    def test_card_shark_turns_adjacent_suit_into_wildcard_value(self):
        env=self.env(["card_shark","clubs","diamond"])
        env.pending_shown=["card_shark","clubs","diamond"]
        self.assertEqual(env.spin(),13)

    def test_robin_hood_pays_every_four_displays(self):
        env=self.env(["robin_hood"])
        payouts=[]
        for _ in range(4):
            env.pending_shown=["robin_hood"]
            payouts.append(env.spin())
        self.assertEqual(payouts,[-4,-4,-4,21])

    def test_robin_hood_buffs_friend_and_destroys_apple(self):
        env=self.env(["coin","robin_hood","apple"])
        env.pending_shown=["coin","robin_hood","apple"]
        self.assertEqual(env.spin(),18)
        self.assertNotIn("apple",env.deck)

    def test_counted_rare_symbols_gain_one_when_deck_has_two(self):
        env=self.env(["strawberry","strawberry"])
        env.pending_shown=["strawberry","strawberry"]
        self.assertEqual(env.spin(),8)

    def test_dame_destroys_martini_for_forty(self):
        env=self.env(["dame","martini"])
        env.pending_shown=["dame","martini"]
        self.assertEqual(env.spin(),45)
        self.assertEqual(env.deck,["dame"])

    def test_farmer_doubles_seed_and_adds_growth_chance(self):
        env=self.env(["farmer","seed"])
        env.pending_shown=["farmer","seed"]
        env.rng.random=lambda: .30
        self.assertEqual(env.spin(),4)
        self.assertNotIn("seed",env.deck)

    def test_general_zaroff_destroys_adjacent_human_for_twenty_five(self):
        env=self.env(["general_zaroff","chef"])
        env.pending_shown=["general_zaroff","chef"]
        self.assertEqual(env.spin(),28)
        self.assertEqual(env.deck,["general_zaroff"])

    def test_joker_doubles_adjacent_suit(self):
        env=self.env(["joker","clubs"])
        env.pending_shown=["joker","clubs"]
        self.assertEqual(env.spin(),5)

    def test_king_midas_generates_coin_and_triples_adjacent_coin(self):
        env=self.env(["king_midas","coin"])
        env.pending_shown=["king_midas","coin"]
        self.assertEqual(env.spin(),4)
        self.assertEqual(env.deck.count("coin"),2)

    def test_witch_doubles_adjacent_witchlike_symbol(self):
        env=self.env(["witch","hex_of_tedium"])
        env.pending_shown=["witch","hex_of_tedium"]
        self.assertEqual(env.spin(),8)

    def test_anthropology_degree_adds_one_per_human(self):
        env=self.env(["chef","witch"]);env.items.append("anthropology_degree")
        env.pending_shown=["chef","witch"]
        self.assertEqual(env.spin(),6)

    def test_bowling_ball_provides_three_each_spin(self):
        env=self.env(["coin"]);env.items.append("bowling_ball")
        env.pending_shown=["coin"]
        self.assertEqual(env.spin(),4)

    def test_chicken_coop_buffs_egg_and_triples_growth_chance(self):
        env=self.env(["egg"]);env.items.append("chicken_coop")
        env.pending_shown=["egg"]
        env.rng.random=lambda: .20
        self.assertEqual(env.spin(),3)
        self.assertIn("chick",env.deck)

    def test_very_big_symbol_bomb_queues_eight_choices(self):
        env=self.env(["coin"]);env.items.append("symbol_bomb_very_big")
        self.assertTrue(env.interact("use:symbol_bomb_very_big"))
        self.assertEqual(env.pending_symbol_groups,["__any__"]*8)

    def test_booster_pack_queues_exact_rarity_sequence(self):
        env=self.env(["coin"]);env.items.append("booster_pack")
        self.assertTrue(env.interact("use:booster_pack"))
        self.assertEqual(env.pending_symbol_rarities,
                         ["=common"]*4+["=uncommon"]*3+["=rare"])

    def test_bag_of_holding_queues_extra_item_choices_after_rent(self):
        env=self.env(["coin"])
        env.items.extend(["bag_of_holding"]*2)
        env.coins=25; env.pending_rent=True
        env._resolve_due_rent()
        self.assertEqual(env.pending_item_choices,3)
        env.choose("egg_carton","item")
        env.choose("skip","item")
        env.choose(None,"item")
        self.assertEqual(env.pending_item_choices,0)

    def test_diver_removal_does_not_trigger_destruction_items(self):
        env=self.env(["diver","anchor"])
        env.items.extend(["black_pepper","compost_heap","void_portal"])
        env.pending_shown=["diver","anchor"]
        env.spin()
        self.assertEqual(env.destroyed_count,0)
        self.assertEqual(env.destroyed_history,[])
        self.assertEqual(env.item_counters["compost_heap"],0)
        self.assertIn("remove:diver:anchor",env.last_interactions)

    def test_diver_removing_oyster_generates_pearl(self):
        catalog=dict(CATALOG)
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"oyster":["poslikes"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1)
        env.deck=["diver","oyster"];env.spins_left=99
        env.pending_shown=["diver","oyster"];env.rng.random=lambda: .99
        env.spin()
        self.assertNotIn("oyster",env.deck)
        self.assertEqual(env.deck.count("pearl"),1)
        self.assertEqual(env.destroyed_count,0)

    def test_diver_removing_sand_dollar_grants_ten(self):
        catalog=dict(CATALOG)
        catalog["symbol_values"]=dict(CATALOG["symbol_values"])|{"sand_dollar":2}
        catalog["symbol_groups"]=dict(CATALOG["symbol_groups"])|{"sand_dollar":["poslikes"]}
        env=FastLandlordEnv(catalog,seed=0,floor=1)
        env.deck=["diver","sand_dollar"];env.spins_left=99
        env.pending_shown=["diver","sand_dollar"]
        self.assertEqual(env.spin(),14)
        self.assertEqual(env.deck,["diver"])

    def test_lucky_dice_always_rolls_maximum(self):
        env=self.env(["d3","d5"]);env.items.append("lucky_dice")
        env.pending_shown=["d3","d5"]
        self.assertEqual(env.spin(),8)

    def test_lucky_carrot_triples_rabbit_value(self):
        env=self.env(["rabbit"]);env.items.append("lucky_carrot")
        env.pending_shown=["rabbit"]
        self.assertEqual(env.spin(),3)

    def test_quiver_excludes_first_direction_from_second_draw(self):
        env=self.env(["bronze_arrow","coin"]);env.items.append("quiver")
        env.pending_shown=["bronze_arrow","coin"]
        draws=[]
        def choose_direction(options):
            draws.append(list(options))
            return options[0]
        env.rng.choice=choose_direction
        env.spin()
        self.assertEqual(len(draws),2)
        self.assertEqual(len(draws[0]),8)
        self.assertEqual(len(draws[1]),7)
        self.assertNotIn(draws[0][0],draws[1])

    def test_counted_bonus_excludes_symbols_not_displayed(self):
        env=self.env(["strawberry","strawberry"])
        env.pending_shown=["strawberry"]
        self.assertEqual(env.spin(),3)

    def test_diamonds_reward_other_displayed_diamonds(self):
        env=self.env(["diamond","diamond"])
        env.pending_shown=["diamond","diamond"]
        self.assertEqual(env.spin(),12)

    def test_sunglasses_grants_removal_at_three_token_threshold(self):
        env=self.env(["coin"]);env.items.append("sunglasses");env.removals=3
        env.pending_shown=["coin"];env.spin()
        self.assertEqual(env.removals,4)

    def test_chili_powder_pays_two_per_pepper(self):
        env=self.env(["coin"]);env.items.extend(["chili_powder","gray_pepper","lime_pepper"])
        env.pending_shown=["coin"]
        self.assertEqual(env.spin(),5)


    def test_watermelon_counts_only_other_displayed_watermelons(self):
        env=self.env(["watermelon"]*3)
        env.catalog={**env.catalog,"symbol_values":{**env.catalog["symbol_values"],"watermelon":4}}
        env.pending_shown=["watermelon"]*2
        self.assertEqual(env.spin(),10)

    def test_telescope_links_distant_rain_every_third_spin(self):
        env=self.env(["flower"]+["coin"]*18+["rain"])
        env.items.append("telescope")
        payouts=[]
        for _ in range(4):
            env.pending_shown=list(env.deck)
            payouts.append(env.spin())
        self.assertEqual(payouts,[21,21,22,21])

    def test_credit_card_seventh_spin_expands_and_rerolls_twenty_choices(self):
        env=self.env(["coin"])
        env.catalog={**env.catalog,"symbol_pool":[f"test_{i}" for i in range(30)]}
        env.choose("credit_card","item")
        self.assertEqual(len(env.candidates()),3)
        for _ in range(6):
            env.pending_shown=["coin"];env.spin()
        self.assertEqual(len(env.candidates()),3)
        env.pending_shown=["coin"];env.spin()
        choices=env.candidates()
        self.assertEqual(len(choices),20)
        self.assertEqual(len(set(choices)),20)
        env.rerolls=1
        self.assertEqual(len(env.reroll()),20)
        self.assertEqual(len(env.candidates("item")),1)
        env.pending_shown=["coin"];env.spin()
        self.assertEqual(len(env.candidates()),3)

    def test_frozen_pizza_extra_choice_every_second_spin_can_skip(self):
        env=self.env(["coin"]);env.items.extend(["frozen_pizza"]*2)
        env.pending_shown=["coin"];env.spin()
        self.assertEqual(env.pending_symbol_groups,[])
        env.pending_shown=["coin"];env.spin()
        self.assertEqual(env.pending_symbol_groups,["__any__"]*2)
        env.choose("skip")
        self.assertEqual(env.pending_symbol_groups,["__any__"])
        env.choose(env.candidates()[0])
        self.assertEqual(env.pending_symbol_groups,[])
        env.pending_shown=["coin"];env.spin()
        self.assertEqual(env.pending_symbol_groups,[])

    def test_key_opens_mega_chest_with_hundred_coin_bonus(self):
        env=self.env(["key","mega_chest"])
        env.catalog={**env.catalog,"symbol_values":{**env.catalog["symbol_values"],"mega_chest":3},
                     "symbol_groups":{**env.catalog["symbol_groups"],"mega_chest":["chest"]}}
        env.pending_shown=list(env.deck)
        self.assertEqual(env.spin(),104)
        self.assertNotIn("mega_chest",env.deck)
        self.assertNotIn("key",env.deck)

    def test_magic_key_triples_mega_chest_payout(self):
        env=self.env(["magic_key","mega_chest"])
        env.catalog={**env.catalog,"symbol_values":{**env.catalog["symbol_values"],"mega_chest":3},
                     "symbol_groups":{**env.catalog["symbol_groups"],"mega_chest":["chest"]}}
        env.pending_shown=list(env.deck)
        self.assertEqual(env.spin(),311)

    def test_timed_essences_pay_on_final_spin_then_expire(self):
        for name,duration,income in [("pool_ball_essence",60,1),("horseshoe_essence",30,2),
                                     ("bowling_ball_essence",20,3),("four_leaf_clover_essence",15,4)]:
            env=self.env(["coin"]);env.choose(name,"essence")
            for _ in range(duration):
                env.pending_shown=["coin"]
                self.assertEqual(env.spin(),1+income)
            self.assertNotIn(name,env.essences)
            env.pending_shown=["coin"]
            self.assertEqual(env.spin(),1)

    def test_popsicle_extends_existing_essence_for_second_lifetime(self):
        env=self.env(["coin"]);env.choose("four_leaf_clover_essence","essence")
        env.choose("popsicle","item")
        for _ in range(30):
            env.pending_shown=["coin"]
            self.assertEqual(env.spin(),5)
        self.assertEqual(env.essences,[])

    def test_highlander_ownership_filters_offers_until_removed(self):
        env=self.env(["highlander"])
        env.catalog={**env.catalog,"symbol_pool":["highlander","coin"]}
        self.assertEqual(env.candidates(),["coin"])
        self.assertFalse(env.choose("highlander"))
        self.assertEqual(env.deck.count("highlander"),1)
        env.removals=1;env.remove("highlander")
        self.assertIn("highlander",env.candidates())

    def test_empty_forced_rarity_does_not_offer_wrong_rarity(self):
        env=self.env(["coin"])
        env.catalog={**env.catalog,"symbol_pool":["coin"],"symbol_rarity":{"coin":"common"}}
        for request in ("=rare","rare"):
            env.pending_symbol_rarities=[request]
            self.assertEqual(env.candidates(),[])

    def test_time_capsule_samples_legal_history_instead_of_last_entry(self):
        env=self.env(["time_capsule","highlander"])
        env.catalog={**env.catalog,"symbol_rarity":{"dud":"none"},
                     "symbol_groups":{**env.catalog["symbol_groups"],"blocked":["time_capsule_effects"]}}
        env.destroyed_history=["honey","honey","coin","time_capsule","blocked","dud","highlander"]
        observed=[]
        def select(pool):
            observed.append(list(pool))
            return pool[0]
        env.rng.choice=select
        env.pending_shown=["time_capsule"]
        env.spin()
        self.assertIn(["honey","honey","coin"],observed)
        self.assertIn("honey",env.deck)
        self.assertEqual(env.deck.count("highlander"),1)

    def test_pirate_consumes_adjacent_targets_without_dwarf_beer_reward(self):
        env=self.env(["pirate","beer","coin"])
        env.catalog={**env.catalog,"symbol_values":{**env.catalog["symbol_values"],"pirate":2},
                     "symbol_groups":{**env.catalog["symbol_groups"],"beer":["piratelikes"],"coin":["piratelikes"]}}
        env.pending_shown=["beer","pirate","coin"]
        self.assertEqual(env.spin(),4)
        self.assertEqual(env.permanent_bonuses["pirate"],2)
        self.assertEqual(env.deck,["pirate"])
        self.assertEqual(env.spin(),4)

    def test_four_leaf_clover_pays_per_copy(self):
        env=self.env(["coin"])
        env.items.extend(["four_leaf_clover"]*2)
        self.assertEqual(env.spin(),9)
        self.assertEqual(env.spin(),9)

    def test_golden_and_lucky_carrots_stack_on_rabbit_growth(self):
        env=self.env(["rabbit"])
        env.items.extend(["golden_carrot","lucky_carrot"])
        env.permanent_bonuses["rabbit"]=2
        self.assertEqual(env.spin(),45)

    def test_golden_carrot_increases_noncommon_candidate_weights(self):
        env=self.env(["coin"])
        env.rent_index=6
        env.catalog={**env.catalog,"symbol_pool":["coin","rare_test"],
                     "symbol_rarity":{"coin":"common","rare_test":"rare"}}
        env.items.append("golden_carrot")
        observed=[]
        def choose(population,weights,k):
            observed.append(dict(zip(population,weights)))
            return [population[0]]
        env.rng.choices=choose
        env.candidates(n=1)
        self.assertAlmostEqual(observed[0]["rare"],.4)
        self.assertAlmostEqual(observed[0]["common"],.65)

    def test_recycling_replenishes_rerolls_once_per_spin(self):
        env=self.env(["coin"])
        env.rerolls=0;env.items.extend(["recycling"]*2)
        env.preview_spin();env.preview_spin()
        self.assertEqual(env.rerolls,0)
        env.spin()
        self.assertEqual(env.rerolls,2)
        env.reroll()
        self.assertEqual(env.rerolls,1)
        env.spin()
        self.assertEqual(env.rerolls,3)

    def test_lizard_blade_counts_duplicate_types_in_entire_deck(self):
        env=self.env(["coin"]*4+["pearl"]*3)
        env.items.extend(["ancient_lizard_blade"]*2)
        env.pending_shown=["coin"]
        self.assertEqual(env.spin(),15)

    def test_lizard_blade_counts_after_targets_are_destroyed(self):
        env=self.env(["cat","milk","milk"])
        env.items.append("ancient_lizard_blade")
        env.pending_shown=["cat","milk"]
        self.assertEqual(env.spin(),20)

    def test_lizard_blade_never_produces_negative_income(self):
        env=self.env([f"test_{i}" for i in range(10) for _ in range(2)])
        env.items.append("ancient_lizard_blade")
        env.pending_shown=["test_0"]
        self.assertEqual(env.spin(),1)

    def test_essence_consumption_resets_only_triggered_instance(self):
        env=self.env(["coin"]);env.choose("popsicle","item")
        env.choose("capsule_machine_essence","essence")
        env.choose("four_leaf_clover_essence","essence")
        entry=env.essence_lifetimes[0]
        entry["age"]=7
        self.assertTrue(env.consume_essence(entry))
        self.assertEqual(entry["lives"],1)
        self.assertEqual(entry["age"],0)
        self.assertEqual(env.essence_lifetimes[1]["lives"],2)
        self.assertTrue(env.consume_essence(entry))
        self.assertFalse(env.consume_essence(entry))
        self.assertEqual(env.essences,["four_leaf_clover_essence"])

    def test_consuming_identical_essences_preserves_instance_identity(self):
        env=self.env(["coin"])
        for _ in range(2): env.choose("four_leaf_clover_essence","essence")
        first,second=env.essence_lifetimes
        self.assertFalse(env.consume_essence(dict(second)))
        self.assertTrue(env.consume_essence(second))
        self.assertIs(env.essence_lifetimes[0],first)
        self.assertFalse(env.consume_essence(second))
        self.assertEqual(len(env.essences),1)

    def test_two_identical_timed_essences_both_expire(self):
        env=self.env(["coin"])
        for _ in range(2): env.choose("four_leaf_clover_essence","essence")
        for _ in range(15): self.assertEqual(env.spin(),9)
        self.assertEqual(env.essences,[])
        self.assertEqual(env.essence_lifetimes,[])
        self.assertEqual(env.spin(),1)

    def test_capsule_machine_essence_multiplies_tokens_and_is_consumed(self):
        env=self.env(["removal_capsule"])
        env.removals=0;env.items.append("capsule_machine")
        env.choose("capsule_machine_essence","essence")
        env.spin()
        self.assertEqual(env.removals,6)
        self.assertNotIn("capsule_machine_essence",env.essences)

    def test_capsule_essence_waits_then_popsicle_preserves_one_more_trigger(self):
        env=self.env(["coin"]);env.choose("popsicle","item")
        env.choose("capsule_machine_essence","essence")
        env.spin()
        self.assertEqual(env.essence_lifetimes[0]["lives"],2)
        env.rerolls=0
        for _ in range(2):
            env.choose("reroll_capsule");env.pending_shown=["reroll_capsule"];env.spin()
        self.assertEqual(env.rerolls,6)
        self.assertEqual(env.essences,[])

    def test_powder_capsule_effect_repetitions_are_exponential(self):
        env=self.env(["buffing_powder","coin"])
        env.choose("capsule_machine_essence","essence")
        env.items.append("capsule_machine")
        env.permanent_bonuses["coin"]=1
        self.assertEqual(env.spin(),128)
        self.assertEqual(env.essences,[])

    def test_wealth_capsule_uses_essence_multiplier(self):
        env=self.env(["lucky_capsule"])
        env.choose("capsule_machine_essence","essence")
        self.assertEqual(env.spin(),30)
        self.assertEqual(env.essences,[])

    def test_rare_candidate_slot_survives_reroll_and_is_spent_on_skip(self):
        env=self.env(["coin"])
        env.catalog={**env.catalog,"symbol_pool":["coin","rare_a","rare_b"],
                     "symbol_rarity":{"coin":"common","rare_a":"rare","rare_b":"rare"}}
        env.rare_candidate_slots=1
        self.assertIn(env.candidates()[0],["rare_a","rare_b"])
        env.rerolls=1
        self.assertIn(env.reroll()[0],["rare_a","rare_b"])
        self.assertEqual(env.rare_candidate_slots,1)
        env.choose("skip")
        self.assertEqual(env.rare_candidate_slots,0)
        self.assertEqual(env.deck,["coin"])

    def test_rare_slot_overflow_carries_to_next_offer_without_extra_pick(self):
        env=self.env(["coin"])
        env.catalog={**env.catalog,"symbol_pool":["coin","a","b","c"],
                     "symbol_rarity":{"coin":"common","a":"rare","b":"rare","c":"rare"}}
        env.rare_candidate_slots=4
        first=env.candidates()
        self.assertEqual(set(first),{"a","b","c"})
        env.choose(first[0])
        self.assertEqual(len(env.deck),2)
        self.assertEqual(env.rare_candidate_slots,1)
        second=env.candidates()
        self.assertIn(second[0],{"a","b","c"})
        env.choose("skip")
        self.assertEqual(env.rare_candidate_slots,0)
        self.assertEqual(len(env.deck),2)

    def test_empty_offer_does_not_spend_stale_rare_slot_count(self):
        env=self.env(["coin"])
        env.rare_candidate_slots=2;env.offered_rare_slots=1
        env.force_skip_next_choice=True
        self.assertEqual(env.candidates(),[])
        env.choose("skip")
        self.assertEqual(env.rare_candidate_slots,2)

if __name__ == "__main__":
    unittest.main()
