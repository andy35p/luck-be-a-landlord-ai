extends "res://Mod Data.gd"

func _init():
	mod_type = "existing_symbol"
	type = "mouse"
	inherit_effects = true
	inherit_art = true
	inherit_groups = true
	inherit_description = true
	description = "\nIntegration probe: reminder number is a heuristic score, not coin income."
	value_text = {"color": "symbol_reminder_up_text", "value": {"starting_value": {"symbols_in_inventory": {"type": "cheese"}}, "var_math": [{"*": 1.8}, {"+": 1}]}}
