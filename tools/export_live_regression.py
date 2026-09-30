"""Project recorded local integration evidence into minimal offline fixtures.

Never reads installed game files; never executes input or creates training data.
Run from the repository root. Source logs stay excluded from version control.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def select_fields(value, keys):
    return {k: copy.deepcopy(value[k]) for k in keys if k in value}


def project(record, session):
    result = select_fields(record, ('schema_version', 'sequence', 'ticks_ms', 'kind',
        'state_revision', 'test_fixture'))
    result['session_id'] = session
    # Preserve provenance timestamps as historical, never current/fresh data.
    result['captured_unix_seconds'] = record['captured_unix_seconds']
    state = record['state']
    result['state'] = {
        'economy': select_fields(state['economy'], ('coins',)),
        'progress': select_fields(state['progress'], ('current_floor', 'spins',
            'times_rent_paid', 'rent_values', 'reroll_tokens', 'removal_tokens',
            'hex_of_emptiness_trigger', 'hex_of_hoarding_trigger')),
        'ui': select_fields(state['ui'], ('closed', 'locked_in_position', 'delay_timer', 'prompt_delay')),
        'input_context': copy.deepcopy(state['input_context']),
        'board_status': select_fields(state['board_status'], ('effects_playing',)),
        'prompt': select_fields(state['prompt'], ('type', 'prompt')),
        'cards': [{'active': c['active'], 'data': select_fields(c['data'], ('type',))} for c in state['cards']],
        'buttons': [select_fields(b, ('active', 'disabled', 'call', 'args')) for b in state['buttons']],
        'items': [select_fields(i, ('type', 'item_count', 'active')) for i in state['items']],
        'symbols': [],
    }
    # A consistent bijection keeps duplicate identity defects visible.
    aliases = {}
    for symbol in state['symbols']:
        s = select_fields(symbol, ('type', 'destroyed', 'being_destroyed',
            'permanent_bonus', 'permanent_multiplier'))
        if 'instance_id' in symbol:
            uid = symbol['instance_id']
            s['instance_id'] = aliases.setdefault(uid, 'symbol-'+str(len(aliases)+1))
        result['state']['symbols'].append(s)
    return result


def main():
    cases = []
    specifications = {
        'v085': [('title', 1), ('natural_choice', 35), ('after_symbol_pick', 46), ('game_over', 170)],
        'v086': [('rent_due', 205), ('rent_increase', 228), ('item_choice', 264), ('item_owned', -1)],
        'v080': [('controlled_cheese', 39), ('controlled_mouse', 222)],
    }
    for version, selections in specifications.items():
        source = ROOT/'logs'/('collector-'+version)/'session.jsonl'
        data = source.read_bytes()
        records = [json.loads(line) for line in data.decode('utf-8-sig').splitlines()]
        for label, sequence in selections:
            record = records[-1] if sequence == -1 else next(r for r in records if r['sequence'] == sequence)
            cases.append({'id': label, 'provenance': {
                'source': version, 'source_sha256': hashlib.sha256(data).hexdigest(),
                'source_sequence': record['sequence'], 'controlled': version == 'v080'},
                'record': project(record, 'offline-'+version)})
    output = ROOT/'tests/fixtures/live_records.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'purpose': 'Offline regression only; not training or a live feed',
                                 'cases': cases}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Exported {len(cases)} projected cases to {output}')


if __name__ == '__main__':
    main()
