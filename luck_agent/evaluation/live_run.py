"""Run diagnostics independent of advice protocol and game input."""
import ctypes
import json
import os
import time
from datetime import datetime, timezone


class ProcessProbe:
    """Hold the original Windows process handle, avoiding PID reuse."""
    def __init__(self, pid):
        if os.name != 'nt':
            raise RuntimeError('Process monitoring requires Windows')
        from ctypes import wintypes
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.OpenProcess(0x100000 | 0x1000, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def poll(self):
        status = self.api.WaitForSingleObject(self.handle, 0)
        if status == 258:
            return None
        if status != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = ctypes.c_ulong()
        if not self.api.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class RunLog:
    def __init__(self, path):
        # Exclusive creation prevents mixing evidence from separate runs.
        self.file = open(path, 'x', encoding='utf-8') if path else None
        self.started = time.monotonic()

    def emit(self, event, **fields):
        if self.file:
            self.file.write(json.dumps({
                'event': event, 'utc': datetime.now(timezone.utc).isoformat(),
                'elapsed_seconds': round(time.monotonic()-self.started, 3),
                **fields}, ensure_ascii=False)+'\n')
            self.file.flush()

    def close(self):
        if self.file:
            self.file.close()
