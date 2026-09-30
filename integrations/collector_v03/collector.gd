# LANDLORD_RESEARCH_V1
var _lr_elapsed = 0.0
var _lr_sequence = 0
var _lr_session = ""
var _lr_last = ""
var _lr_last_capture_ms = -1000
var _lr_directory = "user://landlordResearch"

func _lr_safe(value, depth = 0):
	if depth > 6:
		return null
	var kind = typeof(value)
	if kind == TYPE_NIL or kind == TYPE_BOOL or kind == TYPE_INT or kind == TYPE_STRING:
		return value
	if kind == TYPE_REAL:
		return value if not is_nan(value) and not is_inf(value) else null
	if kind == TYPE_VECTOR2:
		return [value.x, value.y]
	if kind == TYPE_ARRAY:
		var result = []
		for entry in value:
			result.append(_lr_safe(entry, depth + 1))
		return result
	if kind == TYPE_DICTIONARY:
		var result = {}
		for key in value:
			result[str(key)] = _lr_safe(value[key], depth + 1)
		return result
	return null

func _lr_fields(object, names):
	var result = {}
	if typeof(object) == TYPE_DICTIONARY:
		for name in names:
			if object.has(name):
				result[name] = _lr_safe(object[name])
		return result
	if object == null or not is_instance_valid(object):
		return result
	var available = {}
	for property in object.get_property_list():
		available[property.name] = true
	for name in names:
		if available.has(name):
			result[name] = _lr_safe(object.get(name))
	result["instance_id"] = str(object.get_instance_id())
	return result

func _lr_tick(delta):
	_lr_elapsed += delta
	if _lr_elapsed < 0.25:
		return
	_lr_elapsed = 0.0
	_lr_capture("observation", null)

func _lr_capture(kind, requested):
	var popup = get_node_or_null("Pop-up Sprite/Pop-up")
	var board = get_node_or_null("Reels")
	var inventory = get_node_or_null("Items")
	if popup == null or board == null or inventory == null:
		return
	var state = {}
	state["economy"] = _lr_fields(get_node_or_null("Coins"), ["coins"])
	state["progress"] = _lr_fields(popup, ["current_floor", "spins", "total_runs", "times_rent_paid", "times_to_pay_rent", "rent_values", "reroll_tokens", "removal_tokens", "essence_tokens", "reroll_cost", "removal_cost", "hex_of_emptiness_trigger", "hex_of_hoarding_trigger"])
	state["rarity"] = _lr_fields(self, ["rarity_chances"])
	state["ui"] = _lr_fields(popup, ["closed", "delay_timer", "prompt_delay", "locked_in_position"])
	var options_node = get_node_or_null("Options Sprite/Options")
	var title_node = get_node_or_null("Title")
	state["input_context"] = {"window_focused": OS.is_window_focused()}
	if options_node != null:
		state.input_context["options_visible"] = options_node.visible
	if title_node != null:
		state.input_context["title_visible"] = title_node.visible
	state["board_status"] = _lr_fields(board, ["effects_playing"])
	state["symbols"] = []
	for reel in board.reels:
		for icon in reel.icons:
			state.symbols.append(_lr_fields(icon, ["type", "value", "saved_value", "saved_values", "item_count", "permanent_bonus", "permanent_multiplier", "displayed_text_value", "displayed_bonus_value", "displayed_multiplier_value", "grid_position", "destroyed", "being_destroyed", "groups"]))
	state["items"] = []
	for item in inventory.items:
		state.items.append(_lr_fields(item, ["type", "rarity", "value", "values", "saved_value", "saved_values", "item_count", "destroy_counters", "active", "destroyed", "destroyable", "symbol_trigger"]))
	state["prompt"] = {}
	if popup.emails.size() > 0:
		state.prompt = _lr_fields(popup.emails[0], ["type", "replies", "prompt"])
	state["cards"] = []
	for card in popup.cards:
		var card_state = _lr_fields(card, ["active"])
		card_state["data"] = _lr_fields(card.data, ["type", "rarity", "value", "values", "groups"])
		state.cards.append(card_state)
	state["buttons"] = []
	for button in popup.buttons:
		state.buttons.append(_lr_fields(button, ["active", "disabled", "button_text", "call", "args", "shortcuts"]))
	state["visible_grid"] = []
	for row in board.displayed_icons:
		var grid_row = []
		for icon in row:
			grid_row.append(str(icon.get_instance_id()) if icon != null and is_instance_valid(icon) else null)
		state.visible_grid.append(grid_row)
	var signature = JSON.print(state)
	if kind == "observation" and signature == _lr_last and OS.get_ticks_msec() - _lr_last_capture_ms < 1000:
		return
	_lr_last_capture_ms = OS.get_ticks_msec()
	_lr_last = signature
	if _lr_session == "":
		_lr_session = str(OS.get_unix_time()) + "_" + str(OS.get_ticks_msec())
		var directory = Directory.new()
		directory.make_dir_recursive(_lr_directory)
	_lr_sequence += 1
	var record = {"schema_version": "0.2", "session_id": _lr_session, "sequence": _lr_sequence, "kind": kind, "ticks_ms": OS.get_ticks_msec(), "requested_action": _lr_safe(requested), "action_accepted": null, "state": state}
	record["captured_unix_seconds"] = OS.get_unix_time()
	var file = File.new()
	var path = _lr_directory + "/" + _lr_session + ".jsonl"
	var mode = File.READ_WRITE if file.file_exists(path) else File.WRITE
	var error = file.open(path, mode)
	if error != OK:
		push_error("LandlordResearch write failed: " + str(error))
		return
	file.seek_end()
	file.store_line(JSON.print(record))
	file.close()
