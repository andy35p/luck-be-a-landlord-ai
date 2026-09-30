"""Verify the recorded, manually driven V073 real-game experiment."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from luck_agent.evaluation.live_observation import observe_symbol_choice


def main():
    path = Path('logs/collector-v073/session-snapshot.jsonl')
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    by_seq = {r['sequence']: r for r in rows}
    if len(by_seq) != len(rows) or any(r['schema_version'] != '0.2' for r in rows):
        raise ValueError('Unexpected schema or duplicate sequence')
    observations = {n: observe_symbol_choice(r) for n, r in by_seq.items()}
    checks = {
        'title_blocks': 'input_context_title_visible' in observations[1]['blockers'],
        'candidate_ids_match_screen': observations[4]['candidates'] == ['d3', 'oyster', 'magpie'],
        'ordinary_choice_ready': observations[4]['readiness_hint'],
        'options_blocks': observations[5]['blockers'] == ['input_context_options_visible'],
        'options_closed_recovers': observations[6]['readiness_hint'],
        'focus_lost_blocks': observations[7]['blockers'] == ['input_context_window_focused'],
        'focus_restored_recovers': observations[8]['readiness_hint'],
        'skip_button_observed': observations[8]['skip_button_observed'],
        'skip_request_recorded': by_seq[9]['kind'] == 'action_attempt' and by_seq[9]['requested_action'] == 'skip',
        'attempt_not_marked_accepted': by_seq[9]['action_accepted'] is None,
        'choice_closed_after_skip': not observations[10]['readiness_hint'] and not observations[10]['candidates'],
    }
    before, after = by_seq[8]['state'], by_seq[10]['state']
    def deck(state):
        return Counter(s['type'] for s in state['symbols'] if s['type'] != 'empty')
    checks['skip_keeps_deck'] = deck(before) == deck(after)
    checks['skip_same_spin_and_coins'] = (before['progress']['spins'] == after['progress']['spins']
                                        and before['economy']['coins'] == after['economy']['coins'])
    if not all(checks.values()):
        raise ValueError(checks)
    result = {'session_id': rows[0]['session_id'], 'snapshot_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'checks': checks, 'records': len(rows), 'game_build': '16940935',
              'installed_dll_sha256': hashlib.sha256(Path('logs/collector-v072/build/LandlordResearch.dll').read_bytes()).hexdigest(),
              'scope': 'One live session, manually driven UI; readiness is not model support or a general legal-action mask.'}
    Path('reports/v073_live_validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
