"""Leave a readable trace when the packaged desktop app cannot start.

Packaged builds have no console, so an exception during start-up would close
the app silently. This module keeps a small log file and shows a native alert
that tells the user what happened and where the log is.
"""
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import traceback

APP_NAME = 'AI-ditor Plus'
MAX_LOG_BYTES = 1024 * 1024
_stream = None


def log_path() -> Path:
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Logs' / APP_NAME / 'aiditor-plus.log'
    if os.name == 'nt':
        root = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        return Path(root) / APP_NAME / 'aiditor-plus.log'
    root = os.environ.get('XDG_STATE_HOME') or str(Path.home() / '.local' / 'state')
    return Path(root) / 'aiditor-plus' / 'aiditor-plus.log'


def show_alert(title: str, message: str) -> None:
    """Native, dependency-free alert; failures here must never hide the original error."""
    try:
        if sys.platform == 'darwin':
            script = ['-e', 'on run argv', '-e',
                      'display alert (item 1 of argv) message (item 2 of argv) as critical',
                      '-e', 'end run', title, message]
            subprocess.run(['osascript', *script], check=False, timeout=600)
        elif os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        pass


def log_exception(summary: str, exc_info=None) -> None:
    exc_type, exc, tb = exc_info or sys.exc_info()
    stream = _stream or sys.stderr
    try:
        stream.write(f'\n{summary}\n')
        stream.write(''.join(traceback.format_exception(exc_type, exc, tb)))
        stream.flush()
    except Exception:
        pass


def report_fatal(exc_type, exc, tb) -> None:
    log_exception('Başlatma hatası / Start-up error:', (exc_type, exc, tb))
    if issubclass(exc_type, KeyboardInterrupt):
        return
    show_alert(f'{APP_NAME} açılamadı',
               f'{exc_type.__name__}: {exc}\n\nAyrıntılar şu dosyaya kaydedildi:\n{log_path()}\n\n'
               'Sorun sürerse bu dosyayı geliştiriciyle paylaşın.')


def install() -> Path | None:
    """Route packaged output to the log file and report uncaught errors."""
    global _stream
    if not getattr(sys, 'frozen', False):
        return None
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = 'w' if path.exists() and path.stat().st_size > MAX_LOG_BYTES else 'a'
        _stream = open(path, mode, encoding='utf-8', buffering=1)
    except OSError:
        _stream = None
    if _stream is not None:
        sys.stdout = sys.stderr = _stream
        print(f'\n=== {APP_NAME} · {platform.platform()} · {platform.machine()} · Python {platform.python_version()} ===',
              flush=True)
    # Request lines would grow the log without helping diagnosis.
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    sys.excepthook = report_fatal
    threading.excepthook = lambda args: log_exception(f'Arka plan hatası ({args.thread.name if args.thread else "?"}):',
                                                      (args.exc_type, args.exc_value, args.exc_traceback))
    return path
