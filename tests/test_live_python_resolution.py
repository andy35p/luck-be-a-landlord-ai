"""Exercise the actual PowerShell runtime probe without starting the game."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which('pwsh') or shutil.which('powershell')


@unittest.skipUnless(SHELL, 'PowerShell is required')
class LivePythonResolutionTests(unittest.TestCase):
    def probe(self, expression, **overrides):
        env = dict(os.environ, **overrides)
        env['LIVE_RUNTIME_HELPER'] = str(ROOT / 'resolve_live_python.ps1')
        return subprocess.run(
            [SHELL, '-NoProfile', '-NonInteractive', '-Command',
             "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); . $env:LIVE_RUNTIME_HELPER; " + expression],
            env=env, capture_output=True, text=True, encoding='utf-8', timeout=20)

    def test_explicit_runtime_with_spaces_is_probed(self):
        result = self.probe('Resolve-LivePython -PythonPath $env:LIVE_TEST_PYTHON',
                            LIVE_TEST_PYTHON=sys.executable)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(result.stdout.strip()).samefile(sys.executable))

    def test_missing_explicit_path_has_actionable_error(self):
        result = self.probe('Resolve-LivePython -PythonPath $env:LIVE_TEST_PYTHON',
                            LIVE_TEST_PYTHON=str(ROOT / 'missing-python.exe'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python executable not found', result.stderr)

    def test_empty_path_does_not_fall_back_to_codex_cache(self):
        result = self.probe('Resolve-LivePython', PATH='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python 3.11+ required', result.stderr)
