"""Manage one approved, long-running development server without blocking chat."""
import collections
import os
import re
import socket
import subprocess
import threading
import time
from urllib.parse import urlparse


def local_http_address(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('localhost', '127.0.0.1', '::1') or parsed.username or parsed.password:
            return None
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        return parsed, port
    except (ValueError, TypeError):
        return None


class DevServer:
    def __init__(self):
        self.process = None
        self.job = None
        self.kernel = None
        self.lines = collections.deque(maxlen=250)
        self.reader = None
        self.url = None

    def start(self, command, root, url='', stop_event=None, wait_seconds=35):
        if self.process and self.process.poll() is None:
            return 'A development server is already running. Stop it before starting another.\n' + self.status()
        if url and not local_http_address(url):
            return 'Error: the server URL must be an http(s) localhost address.'
        self.lines.clear()
        self.url = None
        self.process = subprocess.Popen(command, cwd=str(root), shell=True, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                        errors='replace', bufsize=1,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
            self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
            self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
            self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            self.kernel.TerminateJobObject.restype = wintypes.BOOL
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.job = self.kernel.CreateJobObjectW(None, None)
            if self.job and not self.kernel.AssignProcessToJobObject(self.job, int(self.process._handle)):
                self.kernel.CloseHandle(self.job)
                self.job = None
        process = self.process
        def read_output():
            for line in process.stdout:
                self.lines.append(line.rstrip())
        self.reader = threading.Thread(target=read_output, daemon=True)
        self.reader.start()
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if stop_event and stop_event.is_set():
                return 'Server startup stopped by user. ' + self.stop()
            if self.process.poll() is not None:
                return 'Development server exited with code ' + str(self.process.returncode) + '.\n' + self.output()
            candidates = re.findall(r'https?://(?:localhost|127\.0\.0\.1|\[::1\]):\d+[^\s]*', self.output())
            for candidate in ([url] if url else []) + candidates[::-1]:
                candidate = candidate.rstrip('.,/)')
                address = local_http_address(candidate)
                if not address:
                    continue
                try:
                    with socket.create_connection((address[0].hostname, address[1]), timeout=.4):
                        self.url = candidate
                        return 'Development server command is running in the background. A local port is listening at ' + candidate + '. Open the page to confirm that it belongs to this server and works.\n' + self.output()
                except OSError:
                    pass
            time.sleep(.2)
        return 'Development server is still running, but its listening address could not be confirmed. Use server status or stop it if needed.\n' + self.output()

    def output(self):
        return '\n'.join(list(self.lines)[-80:])[-10000:]

    def status(self):
        if not self.process:
            return 'No development server has been started by this agent.'
        state = 'running' if self.process.poll() is None else 'exited with code ' + str(self.process.returncode)
        return 'Development server: ' + state + (('\nAddress: ' + self.url) if self.url else '') + '\n' + self.output()

    def stop(self):
        if not self.process or self.process.poll() is not None:
            if self.job and self.kernel:
                self.kernel.CloseHandle(self.job)
                self.job = None
            return 'No development server is running.'
        stopped = False
        if self.job and self.kernel:
            stopped = bool(self.kernel.TerminateJobObject(self.job, 1))
        if not stopped and os.name == 'nt':
            outcome = subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            stopped = outcome.returncode == 0
        if not stopped:
            self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            return 'Stop was requested, but the server did not exit.'
        if self.job and self.kernel:
            self.kernel.CloseHandle(self.job)
            self.job = None
        return 'Development server stopped.' if stopped or os.name != 'nt' else 'The main process stopped; stopping its children could not be confirmed.'
