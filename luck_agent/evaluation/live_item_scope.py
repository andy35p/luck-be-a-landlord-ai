"""Items whose effects are neutral to the currently supported pick preferences.

This is a compatibility gate, not an item simulator. Egg choices and negative
symbol payouts must be independently implemented before widening symbol scope.
"""

NEUTRAL_SYMBOLS = frozenset({
    'coin', 'pearl', 'cherry', 'flower', 'cat', 'mouse', 'cheese', 'milk',
    'goldfish', 'sapphire', 'sand_dollar',
})


def item_scope_blockers(items, symbols):
    if items == []:
        return []
    if not isinstance(items, list) or not items:
        return ['items_or_missing_items_unsupported']
    if not set(symbols).issubset(NEUTRAL_SYMBOLS):
        return ['item_symbol_combination_unsupported']
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            return ['unsupported_item_state']
        kind = item.get('type')
        expected = {'egg_carton': [1, 6], 'tax_evasion': [1]}.get(kind)
        uid = item.get('instance_id')
        if (expected is None or not isinstance(uid, str) or not uid or uid in seen
                or item.get('values') != expected
                or any(type(v) is not int for v in item.get('values', []))
                or type(item.get('item_count')) is not int or item['item_count'] != 1
                or type(item.get('saved_value')) is not int
                or not 0 <= item['saved_value'] <= (6 if kind == 'egg_carton' else 0)
                or item.get('saved_values') != {}
                or type(item.get('value')) is not int or item['value'] != 0
                or type(item.get('destroy_counters')) is not int or item['destroy_counters'] != 0
                or any(item.get(field) is not False for field in
                       ('active', 'destroyed', 'destroyable', 'symbol_trigger'))):
            return ['unsupported_item_state']
        seen.add(uid)
    # Multiple copies need their own stacking evidence.
    if len({item['type'] for item in items}) != len(items):
        return ['unsupported_item_stacking']
    return []
