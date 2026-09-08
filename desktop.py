"""Native desktop window for the local-only AI-ditor Plus service."""
import threading


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
    window = webview.create_window(
        'AI-ditor Plus', f'http://127.0.0.1:{server.server_port}',
        width=1320, height=900, min_size=(760, 600),
        text_select=True, zoomable=True, confirm_close=False,
        background_color='#f5f3ee',
    )
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
