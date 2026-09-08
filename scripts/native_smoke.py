"""macOS native-window smoke test with disposable storage."""
import os
from pathlib import Path
import sys
import tempfile
import time

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
        print('PASS: native WebKit window, registration, workspace, close waits for settings and article disk saves')


if __name__=='__main__':main()
