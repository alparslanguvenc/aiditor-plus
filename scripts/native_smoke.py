"""macOS native-window smoke test with disposable storage."""
import os
from pathlib import Path
import sys
import tempfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix='aiditor-native-') as directory:
        os.environ['AIDITOR_DATA_DIR']=directory
        from app import create_local_server
        from account_store import AccountStore
        from desktop import run_desktop
        result=[]
        def check(window):
            try:
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    if window.evaluate_js('Boolean(window.journalWorkspace)'):break
                    time.sleep(.1)
                window.evaluate_js('''(async()=>{await fetch('/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json','X-Aiditor-Request':'1'},body:JSON.stringify({username:'native_test',password:'local-test-password',display_name:'Masaüstü Denemesi'})});location.reload();return true;})()''')
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    if window.evaluate_js('Boolean(window.journalWorkspace?.ready && window.articleLibrary?.ready)'):break
                    time.sleep(.1)
                else:raise AssertionError('Native workspace failed to initialize')
                window.evaluate_js('''(()=>{
                  const note=document.getElementById('js-footer-text');note.value='Pencere kapanırken korunan dergi notu';note.dispatchEvent(new Event('input',{bubbles:true}));
                  const title=document.getElementById('c-en-title');title.value='Native close recovery';title.dispatchEvent(new Event('input',{bubbles:true}));
                  return true;
                })()''')
                # Exercise the actual WebKit fetch -> JS/Python bridge -> disk flow.
                # Only the OS file picker is replaced with a disposable destination.
                zip_path = Path(directory) / 'native-article.zip'
                window.create_file_dialog = lambda *args, **kwargs: [str(zip_path)]
                window.evaluate_js('''(async()=>{
                  await doGenerate();
                  document.getElementById('dl-link').click();
                })()''')
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    if window.evaluate_js("document.getElementById('zip-download-status').textContent") == 'ZIP dosyası kaydedildi.':break
                    time.sleep(.1)
                else:
                    raise AssertionError(window.evaluate_js("document.getElementById('zip-download-status').textContent + document.getElementById('err-panel').textContent"))
                with zipfile.ZipFile(zip_path) as archive:
                    assert archive.testzip() is None
                    assert 'Native close recovery' in archive.read('main.tex').decode()
                from docx import Document
                word_path = Path(directory) / 'native-article.docx'
                window.create_file_dialog = lambda *args, **kwargs: [str(word_path)]
                window.evaluate_js("(async()=>{await doGenerate('docx');document.getElementById('dl-docx').click();})()")
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    if window.evaluate_js("document.getElementById('docx-download-status').textContent") == 'Word dosyası kaydedildi.':break
                    time.sleep(.1)
                else:raise AssertionError(window.evaluate_js("document.getElementById('docx-download-status').textContent + document.getElementById('err-panel').textContent"))
                assert Document(word_path).core_properties.title=='Native close recovery'
                from webview.platforms.cocoa import BrowserView
                from PyObjCTools import AppHelper
                AppHelper.callAfter(BrowserView.instances[window.uid].window.performClose_, None)
            except Exception as error:
                result.append(error)
                window.evaluate_js('window.journalWorkspace={prepareToClose:async()=>true}')
                window.destroy()
        run_desktop(create_local_server(0),on_started=check)
        if result:raise result[0]
        store=AccountStore(directory)
        user=store.authenticate('native_test','local-test-password')
        assert user
        assert store.journal(user['id'])['settings']['footer_text']=='Pencere kapanırken korunan dergi notu'
        assert store.articles(user['id'])[0]['title']=='Native close recovery'
        print('PASS: native WebKit login, authenticated ZIP and DOCX buttons/bridge/disk/CRC, autosave and close')


if __name__=='__main__':main()
