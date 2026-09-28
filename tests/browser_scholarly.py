"""Select the fifth preset, persist its settings and export both document formats."""
import io,zipfile,tempfile
from pathlib import Path
from docx import Document
from playwright.sync_api import sync_playwright,expect
from browser_workflow import Server,login,ready,saved,preset_saved,QA,api


def run():
    with tempfile.TemporaryDirectory(prefix='aiditor-scholarly-browser-') as data, sync_playwright() as p:
        server=Server(data);browser=None
        try:
            url=server.start();browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            login(page,url,'scholarly_test',True,'Örnek Sosyal Bilimler');ready(page)
            page.locator('#journal-tab').click();page.locator('[data-template-id="scholarly"]').click()
            preset_saved(page)
            expect(page.locator('#js-font')).to_have_value('Times New Roman')
            expect(page.locator('#js-body-size')).to_have_value('11')
            expect(page.locator('#js-header_mode')).to_have_value('odd_even')
            expect(page.locator('#js-header_even_left')).to_have_value('{dergi} {yil} {cilt}({sayi}) {sayfa_araligi}')
            expect(page.locator('#js-english-abstract-heading')).to_have_value('Extended Summary')
            assert page.locator('[data-template-id="scholarly"] img').evaluate('(img)=>img.complete && img.naturalWidth>0')
            page.locator('#template-gallery').screenshot(path=str(QA/'scholarly-gallery.png'))
            page.locator('#js-english-abstract-heading').fill('Extended Abstract')
            page.locator('#js-header_left').fill('ÖZEL {yazarlar}')
            preset_saved(page);page.reload();ready(page);page.locator('#journal-tab').click()
            expect(page.locator('#js-english-abstract-heading')).to_have_value('Extended Abstract')
            expect(page.locator('#js-header_left')).to_have_value('ÖZEL {yazarlar}')
            expect(page.locator('#scholarly-layout-note')).to_be_visible()
            page.locator('#articles-tab').click()
            fields={'c-tr-title':'Düzen ve Yayın Süreçleri','c-en-title':'Layout and Publishing Processes','a-tr-abs':'Türkçe özet içeriği korunur.','a-en-abs':'The English summary is editable and starts on its own page.','refs':'Örnek, A. (2026). Yayın.'}
            page.evaluate('''fields=>{for(const [id,value] of Object.entries(fields)){const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));}}''',fields)
            saved(page);page.locator('#btn-docx').click()
            expect(page.locator('#result-title')).to_have_text('Tamamlandı — Word belgesi hazır')
            with page.expect_download() as download:page.locator('#dl-docx').click()
            path=Path(data)/'article.docx';download.value.save_as(path);doc=Document(path)
            assert len(doc.sections)==2
            text=[p.text for p in doc.paragraphs];assert 'Extended Abstract' in text
            assert text.index(fields['a-tr-abs'])<text.index(fields['c-en-title'])<text.index(fields['a-en-abs'])
            page.locator('#btn-gen').click()
            expect(page.locator('#dl-link')).to_be_visible()
            with page.expect_download() as download:page.locator('#dl-link').click()
            path=Path(data)/'article.zip';download.value.save_as(path)
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None
                text=archive.read('main.tex').decode();assert '% Template: scholarly;' in text and 'Extended Abstract' in text
            page.set_viewport_size({'width':390,'height':844});page.locator('#journal-tab').click()
            page.locator('#template-gallery').screenshot(path=str(QA/'scholarly-gallery-mobile.png'))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
            assert not errors,errors
            print('PASS: fifth preset, real thumbnail, preset persistence, custom summary title, separate editable summary, ZIP, mobile')
        finally:
            if browser:browser.close()
            server.stop()

if __name__=='__main__':run()
