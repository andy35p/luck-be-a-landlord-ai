"""Read-only real-game observations, deliberately distinct from simulator GameState."""
import hashlib
import json


def observe_symbol_choice(record):
    state = record.get('state', {})
    ui = state.get('ui', {})
    prompt = state.get('prompt', {})
    cards = state.get('cards', [])
    reasons = []
    if record.get('kind') != 'observation': reasons.append('not_observation')
    if not record.get('session_id') or type(record.get('sequence')) is not int:
        reasons.append('missing_identity')
    if prompt.get('type') != 'add_tile' or prompt.get('prompt') is not False:
        reasons.append('not_ordinary_symbol_choice')
    if not cards or any(c.get('active') is not True or not c.get('data', {}).get('type') for c in cards):
        reasons.append('inactive_or_missing_cards')
    if ui.get('closed') is not False or ui.get('locked_in_position') is not True:
        reasons.append('popup_not_settled')
    if state.get('board_status', {}).get('effects_playing') is not False:
        reasons.append('effects_or_unknown')
    context = state.get('input_context', {})
    for field, expected in [('options_visible', False), ('title_visible', False), ('window_focused', True)]:
        if context.get(field) is not expected: reasons.append('input_context_' + field)
    candidates = [c.get('data', {}).get('type') for c in cards]
    if len(set(candidates)) != len(candidates): reasons.append('duplicate_candidates')
    skip_visible = any(b.get('active') is True and b.get('disabled') is False
        and b.get('call') == 'resolve_event' and b.get('args') == ['skip']
        for b in state.get('buttons', []))
    identity = json.dumps({'session': record.get('session_id'), 'sequence': record.get('sequence'),
                           'state': state}, sort_keys=True, separators=(',', ':'))
    return {'session_id': record.get('session_id'), 'sequence': record.get('sequence'),
            'observation_id': hashlib.sha256(identity.encode()).hexdigest(),
            'candidates': candidates, 'skip_button_observed': skip_visible,
            'readiness_hint': not reasons, 'blockers': reasons,
            'nonempty_symbols': [s for s in state.get('symbols', []) if s.get('type') != 'empty'],
            'recommendation': None,
            'scope': 'Observation only; no validated legal action mask or model compatibility claim'}
