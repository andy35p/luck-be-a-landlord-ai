"""Inspect installed native candidate/reminder paths without exporting game code."""
import argparse
import hashlib
import json
from pathlib import Path

from tools.audit_local_mod_surface import read_resource


def audit(pck):
    resources = {}
    sources = {}
    for name in ('Main', 'Card', 'Slot Icon', 'Pico Label'):
        raw = read_resource(pck, f'res://{name}.tscn')
        resources[name] = hashlib.sha256(raw).hexdigest()
        sources[name] = raw.decode('utf-8').replace('\\"', '"')
    card, slot, label = (sources[n] for n in ('Card', 'Slot Icon', 'Pico Label'))
    return {
        'scope': 'Static source-path evidence; not a runtime or Workshop subscription test',
        'resource_sha256': resources,
        'facts': {
            'slot_reminder_evaluates_var_math': 'parse_var_math(m.value_text.value, self, null)' in slot,
            'slot_math_has_inventory_type_lookup': 'a.symbols_in_inventory.type' in slot,
            'card_mentions_value_text': 'value_text' in card,
            'card_mentions_parse_var_math': 'parse_var_math' in card,
            'card_passes_database_values_to_description': 'description.values = data.values' in card,
            'card_uses_database_description': 'description.raw_string = data.description' in card,
            'label_mentions_parse_var_math': 'parse_var_math' in label,
        },
        'interpretation': 'Dynamic owned-symbol reminder exists, but inspected candidate card path does not expose it. No complete native adviser integration established.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pck', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.pck)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(result['facts']))
