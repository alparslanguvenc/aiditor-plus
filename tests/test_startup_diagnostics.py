"""Packaged builds must explain start-up failures instead of closing silently."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import startup_diagnostics


class StartupDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.saved = (sys.stdout, sys.stderr, sys.excepthook, threading.excepthook, startup_diagnostics._stream)
        self.home = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {'HOME': self.home.name, 'LOCALAPPDATA': self.home.name,
                                                'XDG_STATE_HOME': self.home.name})
        self.env.start()

    def tearDown(self):
        if startup_diagnostics._stream and startup_diagnostics._stream is not self.saved[4]:
            startup_diagnostics._stream.close()
        sys.stdout, sys.stderr, sys.excepthook, threading.excepthook, startup_diagnostics._stream = self.saved
        self.env.stop()
        self.home.cleanup()

    def test_source_runs_keep_console_output(self):
        self.assertIsNone(startup_diagnostics.install())
        self.assertIs(sys.excepthook, self.saved[2])

    def test_packaged_start_logs_and_alerts_on_errors(self):
        with mock.patch.object(sys, 'frozen', True, create=True), \
                mock.patch.object(startup_diagnostics, 'log_path', return_value=Path(self.home.name) / 'logs' / 'app.log'):
            path = startup_diagnostics.install()
            print('hazır')
            with mock.patch.object(startup_diagnostics, 'show_alert') as alert:
                try:
                    raise PermissionError('veri klasörüne yazılamıyor')
                except PermissionError:
                    sys.excepthook(*sys.exc_info())
            sys.stdout.flush()
            text = path.read_text(encoding='utf-8')
            self.assertIn('hazır', text)
            self.assertIn('PermissionError: veri klasörüne yazılamıyor', text)
            self.assertIn('Traceback', text)
            title, message = alert.call_args.args
            self.assertIn('açılamadı', title)
            self.assertIn(str(path), message)

    def test_large_log_is_restarted(self):
        path = Path(self.home.name) / 'big.log'
        path.write_text('x' * (startup_diagnostics.MAX_LOG_BYTES + 10))
        with mock.patch.object(sys, 'frozen', True, create=True), \
                mock.patch.object(startup_diagnostics, 'log_path', return_value=path):
            startup_diagnostics.install()
            sys.stdout.flush()
        self.assertLess(path.stat().st_size, 1000)

    def test_macos_alert_passes_text_as_arguments(self):
        with mock.patch.object(sys, 'platform', 'darwin'), \
                mock.patch.object(startup_diagnostics.subprocess, 'run') as run:
            startup_diagnostics.show_alert('Başlık "x"', 'İleti')
        command = run.call_args.args[0]
        self.assertEqual(command[0], 'osascript')
        self.assertEqual(command[-2:], ['Başlık "x"', 'İleti'])

    def test_log_location_per_platform(self):
        with mock.patch.object(sys, 'platform', 'darwin'):
            self.assertEqual(startup_diagnostics.log_path().parts[-4:],
                             ('Library', 'Logs', 'AI-ditor Plus', 'aiditor-plus.log'))


if __name__ == '__main__':
    unittest.main()
