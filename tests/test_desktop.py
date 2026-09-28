import base64
import io
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import create_local_server
from desktop import ArticleDownloads, run_desktop, protect_unsaved_close


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


class ArticleDownloadTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='aiditor-save-test-')
        self.addCleanup(directory.cleanup)
        self.target = Path(directory.name) / 'Türkçe makale.zip'
        self.api = ArticleDownloads()
        self.api._window = SimpleNamespace(create_file_dialog=Mock(return_value=[str(self.target)]))
        self.webview = SimpleNamespace(FileDialog=SimpleNamespace(SAVE=30))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('main.tex', 'Türkçe makale')
            archive.writestr('journal_logo.png', b'example image bytes')
        self.blob = buffer.getvalue()

    def save(self, blob):
        with patch.dict(sys.modules, {'webview': self.webview}):
            return self.api.save_article_zip(base64.b64encode(blob).decode())

    def test_native_save_preserves_zip_bytes(self):
        self.assertEqual(self.save(self.blob), {'ok': True, 'cancelled': False})
        self.assertEqual(self.target.read_bytes(), self.blob)
        with zipfile.ZipFile(self.target) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('main.tex').decode(), 'Türkçe makale')

    def test_login_error_and_truncated_archive_are_never_saved(self):
        for blob in (b'{"code":"login_required","ok":false}', self.blob[:30], b''):
            self.assertFalse(self.save(blob)['ok'])
        self.api._window.create_file_dialog.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_cancel_does_not_replace_existing_file(self):
        self.target.write_bytes(b'previous file')
        self.api._window.create_file_dialog.return_value = None
        self.assertEqual(self.save(self.blob), {'ok': True, 'cancelled': True})
        self.assertEqual(self.target.read_bytes(), b'previous file')

    def test_disk_failure_keeps_existing_file_and_cleans_temporary(self):
        self.target.write_bytes(b'previous file')
        with patch('desktop.os.replace', side_effect=OSError('disk full')):
            self.assertFalse(self.save(self.blob)['ok'])
        self.assertEqual(self.target.read_bytes(), b'previous file')
        self.assertEqual(list(self.target.parent.iterdir()), [self.target])

    def test_repeated_click_does_not_open_another_dialog(self):
        self.api._lock.acquire()
        try:
            self.assertFalse(self.save(self.blob)['ok'])
            self.api._window.create_file_dialog.assert_not_called()
        finally:
            self.api._lock.release()
