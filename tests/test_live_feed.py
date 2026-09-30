import json
import tempfile
import unittest
from pathlib import Path
from test_live_advisor import observation
from luck_agent.evaluation.live_feed import LiveFeed


class LiveFeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'session.jsonl'; self.now = [100.2]
        self.feed = LiveFeed(self.tmp.name, clock=lambda:self.now[0], wall_clock=lambda:self.now[0])

    def append(self, seq, capture=100):
        record = observation(seq); record['captured_unix_seconds'] = capture
        with self.path.open('ab') as f: f.write((json.dumps(record)+'\n').encode())

    def test_fresh_then_expired_and_heartbeat_recovers(self):
        self.append(1); self.assertEqual(self.feed.poll()['status'], 'ready')
        self.now[0] = 103; self.assertEqual(self.feed.poll()['reasons'], ['feed_stalled'])
        self.append(2,103); self.assertEqual(self.feed.poll()['status'], 'ready')

    def test_startup_backlog_and_stale_new_record_rejected(self):
        self.append(1)
        feed = LiveFeed(self.tmp.name, wall_clock=lambda:100.2)
        self.assertNotEqual(feed.poll()['status'], 'ready')
        self.append(2,90); self.assertEqual(feed.poll()['reasons'], ['missing_or_stale_capture_time'])

    def test_partial_input_invalidates_and_completes(self):
        self.append(1); self.feed.poll()
        record = observation(2); record['captured_unix_seconds'] = 100
        data = (json.dumps(record)+'\n').encode()
        with self.path.open('ab') as f: f.write(data[:60])
        self.assertEqual(self.feed.poll()['reasons'], ['incomplete_record'])
        with self.path.open('ab') as f: f.write(data[60:])
        self.assertEqual(self.feed.poll()['status'], 'ready')

    def test_malformed_and_concurrent_logs_invalidate(self):
        self.append(1); self.feed.poll()
        with self.path.open('ab') as f: f.write(b'bad\n')
        self.assertEqual(self.feed.poll()['status'], 'unavailable')
        self.append(2)
        (Path(self.tmp.name)/'other.jsonl').write_text('{}\n')
        self.assertEqual(self.feed.poll()['reasons'], ['ambiguous_concurrent_logs'])
