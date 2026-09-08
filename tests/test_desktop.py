import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import create_local_server
from desktop import run_desktop, protect_unsaved_close


class ClosingEvent:
    def __iadd__(self, callback):
        self.callback = callback
        return self


def mock_window():
    return SimpleNamespace(events=SimpleNamespace(closing=ClosingEvent()), destroy=Mock(), evaluate_js=Mock())


class DesktopLifecycleTests(unittest.TestCase):
    def test_native_window_owns_and_stops_server(self):
        stop = threading.Event()
        server = SimpleNamespace(server_port=43210, serve_forever=lambda: stop.wait(5),
                                 shutdown=Mock(side_effect=stop.set), server_close=Mock())
        window = mock_window()
        webview = SimpleNamespace(settings={}, create_window=Mock(return_value=window), start=Mock())
        with patch.dict(sys.modules, {'webview': webview}):
            self.assertIs(run_desktop(server), window)
        self.assertEqual(webview.create_window.call_args.args[1], 'http://127.0.0.1:43210')
        self.assertTrue(webview.settings['ALLOW_DOWNLOADS'])
        self.assertFalse(webview.settings['ALLOW_FILE_URLS'])
        server.shutdown.assert_called_once()
        server.server_close.assert_called_once()

    def test_native_failure_also_stops_server(self):
        stop = threading.Event()
        server = SimpleNamespace(server_port=43210, serve_forever=lambda: stop.wait(5),
                                 shutdown=Mock(side_effect=stop.set), server_close=Mock())
        webview = SimpleNamespace(settings={}, create_window=Mock(return_value=mock_window()), start=Mock(side_effect=RuntimeError('test')))
        with patch.dict(sys.modules, {'webview': webview}), self.assertRaises(RuntimeError):
            run_desktop(server)
        server.server_close.assert_called_once()

    def test_invalid_ports_are_rejected(self):
        for port in (-1, 65536):
            with self.assertRaises(ValueError):
                create_local_server(port)

    def test_close_waits_for_successful_autosave(self):
        window = mock_window()
        called = threading.Event()
        callbacks = []
        window.evaluate_js.side_effect = lambda script, callback: (callbacks.append(callback), called.set())
        close = protect_unsaved_close(window)
        self.assertFalse(close())
        self.assertTrue(called.wait(2))
        window.destroy.assert_not_called()
        self.assertFalse(close())  # Duplicate close cannot start a second save.
        callbacks.pop()(False)
        window.destroy.assert_not_called()
        called.clear()
        self.assertFalse(close())
        self.assertTrue(called.wait(2))
        callbacks.pop()(True)
        window.destroy.assert_called_once()
        self.assertTrue(close())
