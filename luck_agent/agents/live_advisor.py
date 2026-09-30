"""Conservative, read-only heuristic advice; never executes game actions."""
import copy
import math
import time
from types import SimpleNamespace
from luck_agent.evaluation.live_observation import observe_symbol_choice
from luck_agent.agents.heuristic_agent import HeuristicAgent
from luck_agent.evaluation.live_item_scope import item_scope_blockers
from luck_agent.evaluation.live_collector_contract import collector_blockers


class LiveAdvisor:
    # Item combinations are separately gated; no hidden effect reconstruction.
    supported = frozenset({'coin', 'pearl', 'cherry', 'flower', 'cat', 'mouse', 'cheese', 'milk', 'goldfish',
                           'sapphire', 'sand_dollar'})

    def __init__(self, ttl=2.0, clock=time.monotonic, *, allow_test_fixtures=False):
        if not math.isfinite(ttl) or ttl <= 0:
            raise ValueError('Positive finite TTL required')
        self.ttl, self.clock = ttl, clock
        if type(allow_test_fixtures) is not bool:
            raise ValueError('allow_test_fixtures must be an explicit boolean')
        self.allow_test_fixtures = allow_test_fixtures
        self.teacher = HeuristicAgent()
        self.session, self.sequence, self.last_ticks = None, -1, -1
        self.retired = set()
        self.cached = None
        self.deadline = 0

    def _reject(self, reasons):
        self.cached = {'status': 'unavailable', 'reasons': reasons, 'action': None}
        return copy.deepcopy(self.cached)

    def update(self, record, *, fresh=False):
        """Caller must confirm a live feed; historical input is rejected by default.

        TTL is time since receipt, not proof of game freshness. New records invalidate
        previous advice. A future file watcher must not mark backlog records fresh.
        """
        if not fresh:
            return self._reject(['live_freshness_unconfirmed'])
        try:
            controlled = 'test_fixture' in record or 'fixture_applied' in record
            if controlled and not self.allow_test_fixtures:
                return self._reject(['controlled_test_record'])
            session, seq, ticks = record['session_id'], record['sequence'], record['ticks_ms']
            if (record['schema_version'] != '0.2' or not isinstance(session, str) or not session
                    or type(seq) is not int or seq < 1 or type(ticks) is not int or ticks < 0):
                return self._reject(['invalid_envelope'])
            if session in self.retired:
                return self._reject(['retired_session'])
            if session == self.session and (seq <= self.sequence or ticks < self.last_ticks):
                return self._reject(['out_of_order_or_duplicate'])
            if self.session is not None and session != self.session:
                self.retired.add(self.session)
            self.session, self.sequence, self.last_ticks = session, seq, ticks
            self._reject(['pending_validation'])
            observed = observe_symbol_choice(record)
            state = record['state']
            reasons = list(observed['blockers'])
            reasons.extend(collector_blockers(record))
            progress = state.get('progress', {})
            if type(progress.get('current_floor')) is not int or progress['current_floor'] != 1:
                reasons.append('unsupported_floor')
            for field in ('hex_of_emptiness_trigger', 'hex_of_hoarding_trigger'):
                if progress.get(field) is not False: reasons.append('special_effect_or_unknown')
            symbols = state.get('symbols')
            if not isinstance(symbols, list) or not symbols:
                reasons.append('missing_deck')
                symbols = []
            deck = []
            ids = set()
            for symbol in symbols:
                if symbol.get('type') == 'empty': continue
                kind, uid = symbol.get('type'), symbol.get('instance_id')
                if not isinstance(uid, str) or not uid or uid in ids:
                    reasons.append('invalid_instance_identity')
                ids.add(uid)
                if kind not in self.supported: reasons.append('unsupported_symbol')
                if (symbol.get('destroyed') is not False or symbol.get('being_destroyed') is not False
                        or symbol.get('permanent_bonus') != 0 or symbol.get('permanent_multiplier') != 1):
                    reasons.append('modified_or_transient_symbol')
                deck.append(kind)
            if not deck: reasons.append('empty_effective_deck')
            if any(c not in self.supported for c in observed['candidates']):
                reasons.append('unsupported_candidate')
            reasons.extend(item_scope_blockers(state.get('items'), deck + observed['candidates']))
            if not observed['skip_button_observed']:
                reasons.append('ordinary_skip_not_confirmed')
            if reasons: return self._reject(sorted(set(reasons)))
            # This restricted scoring only uses catalog base values and deck counts.
            # No GameState fabrication, model inference or timer reconstruction.
            view = SimpleNamespace(catalog=self.teacher.catalog, deck=deck, force_add_next_choice=False)
            scores = {c: self.teacher.prior.score_symbol(view, c) for c in observed['candidates']}
            best = max(observed['candidates'], key=scores.__getitem__, default=None)
            threshold = .8 if len(deck) < 20 else 2.0
            choice = best if best is not None and scores[best] >= threshold else 'skip'
            self.deadline = self.clock() + self.ttl
            self.cached = {'status': 'ready', 'policy': 'restricted_heuristic_v3',
                'state_revision': record.get('state_revision'),
                'observation_id': observed['observation_id'], 'session_id': session, 'sequence': seq,
                'action': {'action_type': 1 if choice == 'skip' else 0,
                           'target_id': None if choice == 'skip' else choice, 'secondary_target_id': None},
                'scores': scores, 'threshold': threshold,
                'reasons': [], 'scope': 'Heuristic preference, not expected return or a model recommendation'}
            if controlled:
                self.cached['test_fixture'] = record.get('test_fixture')
                self.cached['scope'] = 'Controlled test only; excluded from natural evaluation and training'
            return copy.deepcopy(self.cached)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            return self._reject(['malformed_observation'])

    def current(self):
        if self.cached is None: return self._reject(['no_observation'])
        if self.cached['status'] == 'ready' and self.clock() >= self.deadline:
            return self._reject(['expired'])
        return copy.deepcopy(self.cached)
