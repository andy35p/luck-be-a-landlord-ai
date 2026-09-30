import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from luck_agent.evaluation.live_run import ProcessProbe, RunLog


class LiveRunTests(unittest.TestCase):
    def test_log_cannot_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'events.jsonl'
            log = RunLog(path)
            log.emit('started')
            log.close()
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                RunLog(path)
            self.assertEqual(before, path.read_bytes())

    def test_duration_and_offline_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder)/'events.jsonl'
            display = Path(folder)/'advice.json'
            result = subprocess.run([sys.executable, 'watch_live_advice.py',
                '--directory', folder, '--seconds', '0.2', '--event-log', str(log),
                '--display-file', str(display)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            events = [json.loads(x) for x in log.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(events[-1]['outcome'], 'duration_completed')
            self.assertTrue(all('utc' in x and 'elapsed_seconds' in x for x in events))
            self.assertEqual(json.loads(display.read_text())['status'], 'unavailable')

    @unittest.skipUnless(os.name == 'nt', 'Windows process handles')
    def test_early_exit_is_not_reported_as_duration_completed(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder)/'events.jsonl'
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1); raise SystemExit(7)'])
            try:
                result = subprocess.run([sys.executable, 'watch_live_advice.py',
                    '--directory', folder, '--seconds', '10', '--event-log', str(log),
                    '--game-pid', str(child.pid)], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                events = [json.loads(x) for x in log.read_text().splitlines()]
                self.assertEqual(events[-1]['outcome'], 'game_exited')
                self.assertEqual(next(x for x in events if x['event'] == 'game_exited')['exit_code'], 7)
            finally:
                child.wait(timeout=5)

    @unittest.skipUnless(os.name == 'nt', 'Windows process handles')
    def test_original_process_exit_code(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(.5); raise SystemExit(7)'])
        probe = ProcessProbe(child.pid)
        try:
            self.assertIsNone(probe.poll())
            child.wait(timeout=5)
            self.assertEqual(probe.poll(), 7)
        finally:
            probe.close()
            child.wait(timeout=5)
