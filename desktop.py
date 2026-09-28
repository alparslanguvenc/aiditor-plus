"""Native desktop window for the local-only AI-ditor Plus service."""
import base64
import binascii
import io
import os
from pathlib import Path
import tempfile
import threading
import zipfile
import zlib
from lxml.etree import XMLSyntaxError


class ArticleDownloads:
    """Save authenticated ZIP bytes without the WebKit downloader's new request."""

    def __init__(self):
        self._window = None
        self._lock = threading.Lock()

    def save_article_zip(self, encoded):
        return self._save_package(encoded, 'zip')

    def save_article_docx(self, encoded):
        return self._save_package(encoded, 'docx')

    def _save_package(self, encoded, kind):
        if not self._lock.acquire(blocking=False):
            return {'ok': False, 'error': 'Açık olan kaydetme penceresini tamamlayın.'}
        temporary = None
        try:
            if not isinstance(encoded, str) or len(encoded) > 180 * 1024 * 1024:
                raise ValueError('ZIP verisi geçersiz veya çok büyük.')
            try:
                blob = base64.b64decode(encoded, validate=True)
                with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                    entries = archive.infolist()
                    if (len(entries) > 5000 or sum(item.file_size for item in entries) > 128 * 1024 * 1024
                            or archive.testzip() is not None):
                        raise ValueError
                    names = set(archive.namelist())
                    required = {'main.tex'} if kind == 'zip' else {'[Content_Types].xml', '_rels/.rels', 'word/document.xml'}
                    if not required.issubset(names):
                        raise ValueError
                    if kind == 'docx':
                        from docx import Document
                        Document(io.BytesIO(blob))
            except (ValueError, binascii.Error, zipfile.BadZipFile, RuntimeError, NotImplementedError, KeyError, zlib.error, XMLSyntaxError) as exc:
                raise ValueError('Geçerli bir çıktı dosyası alınamadı. Çıktıyı yeniden oluşturun.') from exc
            import webview
            selected = self._window.create_file_dialog(
                webview.FileDialog.SAVE, save_filename='aiditor_article.' + kind,
                file_types=(('Word belgesi (*.docx)' if kind == 'docx' else 'ZIP arşivi (*.zip)'),),
            )
            if not selected:
                return {'ok': True, 'cancelled': True}
            target = Path(selected if isinstance(selected, str) else selected[0])
            # The OS dialog owns the filename and overwrite confirmation.
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.aiditor-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            temporary = None
            return {'ok': True, 'cancelled': False}
        except ValueError as error:
            return {'ok': False, 'error': str(error)}
        except OSError:
            return {'ok': False, 'error': 'Dosya kaydedilemedi. Klasör izinlerini ve boş disk alanını kontrol edin.'}
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            self._lock.release()


def protect_unsaved_close(window):
    """Cancel synchronous OS close, flush asynchronously, then close on success."""
    state = {'allowed': False, 'pending': False}

    def on_closing():
        if state['allowed']:
            return True
        if state['pending']:
            return False
        state['pending'] = True

        def completed(saved):
            state['pending'] = False
            if saved is True:
                state['allowed'] = True
                window.destroy()

        def flush():
            try:
                window.evaluate_js('(async () => window.journalWorkspace ? await journalWorkspace.prepareToClose() : (window.articleLibrary ? await articleLibrary.prepareToClose() : true))()',
                                   callback=completed)
            except Exception:
                state['pending'] = False

        threading.Thread(target=flush, daemon=True, name='aiditor-save-before-close').start()
        return False

    window.events.closing += on_closing
    return on_closing


def run_desktop(server, on_started=None):
    """Own the server lifecycle; closing the window also stops the service."""
    import webview

    webview.settings['ALLOW_DOWNLOADS'] = True
    webview.settings['ALLOW_FILE_URLS'] = False
    webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True
    downloads = ArticleDownloads()
    window = webview.create_window(
        'AI-ditor Plus', f'http://127.0.0.1:{server.server_port}',
        width=1320, height=900, min_size=(760, 600),
        text_select=True, zoomable=True, confirm_close=False,
        background_color='#f5f3ee', js_api=downloads,
    )
    downloads._window = window
    protect_unsaved_close(window)
    worker = threading.Thread(target=server.serve_forever, daemon=True, name='aiditor-local-server')
    worker.start()
    try:
        webview.start(
            on_started, window if on_started else None,
            localization={
                'global.quitConfirmation': 'Uygulamadan çıkılsın mı?',
                'global.ok': 'Tamam', 'global.cancel': 'İptal',
                'global.quit': 'Çıkış',
                'global.saveFile': 'Dosyayı kaydet',
                'cocoa.menu.about': 'Hakkında', 'cocoa.menu.edit': 'Düzen',
                'cocoa.menu.view': 'Görünüm', 'cocoa.menu.quit': 'Çıkış',
                'cocoa.menu.cut': 'Kes', 'cocoa.menu.copy': 'Kopyala',
                'cocoa.menu.paste': 'Yapıştır', 'cocoa.menu.selectAll': 'Tümünü Seç',
                'cocoa.menu.fullscreen': 'Tam Ekran',
            },
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    return window
