"""Bounded, conservative JSONL tail: ignores startup backlog and rejects stale writes."""
import json
import time
from pathlib import Path
from luck_agent.agents.live_advisor import LiveAdvisor


class LiveFeed:
    def __init__(self, directory, clock=time.monotonic, wall_clock=time.time):
        self.directory = Path(directory)
        self.clock, self.wall_clock = clock, wall_clock
        self.advisor = LiveAdvisor(clock=clock)
        self.positions = {}
        self.active = None
        self.last_received = None
        self.last_identity = None
        self.pending = {}
        self.discard_prefix = set()
        self.status = {'status': 'unavailable', 'action': None, 'reasons': ['waiting_for_new_record']}
        for p in self.directory.glob('*.jsonl'):
            size = p.stat().st_size
            self.positions[p] = size
            if size:
                with p.open('rb') as f:
                    f.seek(size-1)
                    if f.read(1) != b'\n': self.discard_prefix.add(p)

    def reject(self, reason):
        # Public API invalidates any previous advice without fabricating an observation.
        self.advisor.update({}, fresh=False)
        self.status = {'status': 'unavailable', 'action': None, 'reasons': [reason]}
        return self.status.copy()

    def poll(self):
        try:
            paths = list(self.directory.glob('*.jsonl'))
            changed = [p for p in paths if p not in self.positions or p.stat().st_size != self.positions[p]]
            if len(changed) > 1:
                for p in changed: self.positions[p] = p.stat().st_size
                self.pending.clear()
                self.discard_prefix.update(changed)
                return self.reject('ambiguous_concurrent_logs')
            if not changed:
                if self.active is not None and not self.active.exists(): return self.reject('source_removed')
                if self.last_received is not None and self.clock()-self.last_received >= 2:
                    return self.reject('feed_stalled')
                if self.active in self.pending or self.active in self.discard_prefix:
                    return self.reject('incomplete_record')
                if self.status['status'] == 'ready': self.status = self.advisor.current()
                return self.status.copy()
            path = changed[0]
            size = path.stat().st_size
            position = self.positions.get(path, 0)
            if size < position:
                self.positions[path] = size
                self.pending.pop(path, None)
                self.discard_prefix.add(path)
                return self.reject('source_truncated')
            if size-position > 1024*1024:
                self.positions[path] = size
                self.pending.pop(path, None)
                self.discard_prefix.add(path)
                return self.reject('backlog_too_large')
            with path.open('rb') as f:
                f.seek(position); chunk = f.read(size-position)
            self.positions[path] = position+len(chunk)
            if self.active != path:
                self.reject('source_changed')
                self.pending.clear()
                self.active = path
            data = self.pending.pop(path, b'')+chunk
            if path in self.discard_prefix:
                if b'\n' not in data: return self.reject('incomplete_startup_record')
                data = data.split(b'\n', 1)[1]; self.discard_prefix.remove(path)
            lines = data.split(b'\n')
            if lines[-1]:
                self.pending[path] = lines[-1]
                if len(lines[-1]) > 1024*1024: self.pending.pop(path); self.discard_prefix.add(path)
                return self.reject('incomplete_record')
            lines = [line for line in lines[:-1] if line.strip()]
            if not lines: return self.reject('waiting_for_complete_record')
            record = json.loads(lines[-1])
            captured = record.get('captured_unix_seconds')
            now = self.wall_clock()
            # One-second producer precision; future clocks are refused.
            if type(captured) not in (int, float) or not 0 <= now-captured <= 1.5:
                return self.reject('missing_or_stale_capture_time')
            self.last_received = self.clock()
            self.last_identity = {key: record.get(key) for key in ('session_id', 'sequence', 'state_revision')}
            self.status = self.advisor.update(record, fresh=True)
            return self.status.copy()
        except (OSError, ValueError, TypeError, AttributeError):
            return self.reject('unreadable_or_malformed_feed')
