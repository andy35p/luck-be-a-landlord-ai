"""Read-only audit of the recovered real-game collector; never submits actions."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from luck_agent.env.instance_goldfish_engine import goldfish_catalog
from luck_agent.env.rule_engine import load_catalog


def inspect_record(record, supported_symbols, supported_items):
    state = record['state']
    cards = state.get('cards', [])
    symbols = [s for s in state.get('symbols', []) if s.get('type') != 'empty']
    ui = state.get('ui', {})
    # Observational filter, NOT a validated action mask or stable-decision guarantee.
    ready = (record.get('kind') == 'observation'
             and state.get('prompt', {}).get('type') == 'add_tile'
             and bool(cards) and all(c.get('active') is True for c in cards)
             and ui.get('closed') is False
             and ui.get('delay_timer') == 0 and ui.get('prompt_delay') == 0
             and state.get('board_status', {}).get('effects_playing') is False)
    blockers = []
    if state.get('progress', {}).get('current_floor') != 1:
        blockers.append('floor_not_supported')
    unknown = sorted({s.get('type', '<missing>') for s in symbols}
                     | {c.get('data', {}).get('type', '<missing>') for c in cards})
    unknown = [s for s in unknown if s not in supported_symbols]
    unknown_items = sorted({s.get('type', '<missing>') for s in state.get('items', [])}
                           - set(supported_items))
    if unknown:
        blockers.append('symbols_not_supported')
    if unknown_items:
        blockers.append('items_not_supported')
    return {'readiness_hint': ready, 'raw_symbol_slots': len(state.get('symbols', [])),
            'nonempty_symbol_slots': len(symbols), 'scope_blockers': blockers,
            'unsupported_symbols': unknown, 'unsupported_items': unknown_items}


def audit(directory):
    catalog = goldfish_catalog(load_catalog())
    files = []
    total = Counter()
    floors = Counter()
    for path in sorted(Path(directory).glob('*.jsonl')):
        raw = path.read_bytes()
        counts = Counter()
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                result = inspect_record(record, catalog['symbol_pool'], catalog['item_pool'])
            except (ValueError, KeyError, TypeError, AttributeError):
                counts['invalid_records'] += 1
                continue
            counts['records'] += 1
            counts['action_attempts'] += record.get('kind') == 'action_attempt'
            counts['readiness_hints'] += result['readiness_hint']
            counts['hints_with_scope_blockers'] += result['readiness_hint'] and bool(result['scope_blockers'])
            counts['records_with_empty_slots'] += result['raw_symbol_slots'] > result['nonempty_symbol_slots']
            floors[str(record['state'].get('progress', {}).get('current_floor'))] += 1
        total.update(counts)
        files.append({'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), **counts})
    return {'files': files, 'totals': dict(total), 'floor_record_counts': dict(floors),
            'limits': 'Readiness hints are not verified legal decision points. No GameState adapter, recommendation, or live UI tested.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.directory)
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'files': len(result['files']), 'totals': result['totals'],
                      'floors': result['floor_record_counts']}))


if __name__ == '__main__':
    main()
