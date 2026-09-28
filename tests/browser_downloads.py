"""Downloads must save the authenticated ZIP, never a login/error response."""
import base64
import io
from pathlib import Path
import tempfile
import zipfile

from playwright.sync_api import sync_playwright, expect
from browser_workflow import Server, login, ready, saved


def run():
    with tempfile.TemporaryDirectory(prefix='aiditor-downloads-') as data, sync_playwright() as playwright:
        server = Server(data)
        browser = None
        try:
            url = server.start()
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            login(page, url, 'download_test', True, 'İndirme Test Dergisi')
            ready(page)
            page.locator('#articles-tab').click()
            page.locator('#c-tr-title').fill('Türkçe ZIP indirme testi')
            saved(page)
            page.locator('#btn-gen').click()
            expect(page.locator('#result-panel')).to_be_visible()
            with page.expect_download() as download:
                page.locator('#dl-link').click()
            target = Path(data) / 'browser.zip'
            download.value.save_as(target)
            with zipfile.ZipFile(target) as archive:
                assert archive.testzip() is None
                assert 'Türkçe ZIP indirme testi' in archive.read('main.tex').decode()

            # Simulate only the native bridge: browser fetch must still carry the cookie.
            page.evaluate('''window.pywebview = {api: {save_article_zip: async encoded => {
              window.savedZip = encoded; return {ok:true,cancelled:false};
            }}}''')
            page.locator('#dl-link').click()
            expect(page.locator('#zip-download-status')).to_have_text('ZIP dosyası kaydedildi.')
            assert base64.b64decode(page.evaluate('window.savedZip')) == target.read_bytes()

            failures = [
                (404, 'application/json', '{"error":"Dosya bulunamadı"}', 'Dosya bulunamadı'),
                (200, 'text/html', '<html>Error</html>', 'ZIP yerine farklı'),
                (200, 'application/zip', '{"ok":false}', 'eksik veya geçersiz'),
                (401, 'application/json', '{"code":"login_required","error":"Yeniden giriş yapın"}', 'Yeniden giriş yapın'),
            ]
            downloads = []
            page.on('download', lambda item: downloads.append(item))
            for code, content_type, body, expected in failures:
                page.evaluate('window.savedZip = null')
                def fail_download(route):
                    route.fulfill(status=code, content_type=content_type, body=body)
                page.route('**/download/*', fail_download)
                page.locator('#dl-link').click()
                expect(page.locator('#zip-download-status')).to_contain_text(expected)
                expect(page.locator('#dl-link')).to_be_enabled()
                assert page.evaluate('window.savedZip') is None
                assert downloads == []
                page.unroute('**/download/*')
            expect(page.locator('#session-warning')).to_be_visible()
            print('PASS: actual ZIP click, native payload bytes, 404/HTML/invalid ZIP/401 saved as no file')
        finally:
            if browser:
                browser.close()
            server.stop()


if __name__ == '__main__':
    run()
