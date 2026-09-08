"""Exercise recoverable saves and asynchronous preset/logo races in a real browser."""
import json
from pathlib import Path
import tempfile
import time

from PIL import Image
from playwright.sync_api import sync_playwright, expect
from browser_workflow import Server, QA, PASSWORD, ready, login, preset_saved, api


def run():
    with tempfile.TemporaryDirectory(prefix='aiditor-races-') as data, sync_playwright() as p:
        server=Server(data)
        try:
            url=server.start();browser=p.chromium.launch(headless=True)
            context=browser.new_context();page=context.new_page()
            page.on('dialog',lambda dialog:dialog.accept())
            login(page,url,'race_journal',True,'Kayıt Güvenliği Dergisi')
            # Commit succeeds but the browser loses the response, then more typing arrives.
            bodies=[]
            def lose_response(route):
                if route.request.method!='PUT':return route.continue_()
                bodies.append(route.request.post_data)
                response=route.fetch()
                assert response.status==200
                route.abort('failed')
            page.route('**/api/journal',lose_response)
            page.locator('#js-footer-text').fill('İlk kaydedilen sürüm')
            expect(page.locator('#journal-save-status')).to_have_attribute('data-state','error')
            page.unroute('**/api/journal',lose_response)
            def record_retry(route):
                if route.request.method=='PUT':bodies.append(route.request.post_data)
                route.continue_()
            page.route('**/api/journal',record_retry)
            page.locator('#js-footer-text').fill('Yanıt kaybolduktan sonraki değişiklik')
            preset_saved(page)
            assert len(bodies)>=3 and bodies[0]==bodies[1],bodies
            assert api(page,'/api/journal')['settings']['footer_text']=='Yanıt kaybolduktan sonraki değişiklik'
            page.unroute('**/api/journal',record_retry)
            # An import in progress cannot bypass native close protection.
            preset=Path(data)/'replacement.json'
            incoming={'format':'aiditor-journal-preset','version':1,'settings':{**api(page,'/api/journal')['settings'],'journal_name_tr':'Aktarılan Dergi'},'assets':{}}
            preset.write_text(json.dumps(incoming))
            held=[]
            def hold_put(route):
                if route.request.method=='PUT':held.append(route)
                else:route.continue_()
            page.route('**/api/journal',hold_put)
            page.locator('#import-preset').set_input_files(preset)
            for _ in range(100):
                page.wait_for_timeout(25)
                if held:break
            assert held,'Import PUT was never sent'
            assert page.evaluate('journalWorkspace.prepareToClose()') is False
            held.pop().continue_()
            expect(page.locator('#js-name-tr')).to_have_value('Aktarılan Dergi');preset_saved(page)
            page.unroute('**/api/journal',hold_put)
            # Lost acknowledgment of a committed preset import stays recoverable.
            incoming['settings']['journal_name_tr']='Yanıtı Kaybolan Aktarım'
            preset.write_text(json.dumps(incoming))
            import_bodies=[]
            def lose_import(route):
                if route.request.method!='PUT':return route.continue_()
                import_bodies.append(route.request.post_data)
                response=route.fetch();assert response.status==200;route.abort('failed')
            page.route('**/api/journal',lose_import)
            page.locator('#import-preset').set_input_files(preset)
            expect(page.locator('#journal-save-status')).to_have_attribute('data-state','error')
            assert page.evaluate('journalWorkspace.prepareToClose()') is False
            page.unroute('**/api/journal',lose_import)
            # Save retries the identical import body before unlocking the new preset.
            def retry_import(route):
                if route.request.method=='PUT':import_bodies.append(route.request.post_data)
                route.continue_()
            page.route('**/api/journal',retry_import)
            page.locator('#journal-import-retry').click()
            expect(page.locator('#js-name-tr')).to_have_value('Yanıtı Kaybolan Aktarım');preset_saved(page)
            assert import_bodies[0]==import_bodies[1]
            assert api(page,'/api/journal')['settings']['journal_name_tr']=='Yanıtı Kaybolan Aktarım'
            page.unroute('**/api/journal',retry_import)
            # Delay old image reads to make removal/newer-choice races deterministic.
            images={}
            for name,color in [('existing.png','green'),('slow.png','red'),('fast.png','blue')]:
                path=Path(data)/name;Image.new('RGB',(48,48),color).save(path);images[name]=path
            page.locator('#logo-inp').set_input_files(images['existing.png']);expect(page.locator('#logo-label')).to_have_text('existing.png');preset_saved(page)
            page.evaluate('''() => {
              const Native=window.FileReader;
              window.FileReader=class {
                readAsDataURL(file){const reader=new Native();reader.onload=()=>{this.result=reader.result;setTimeout(()=>this.onload?.({target:this}),file.name==='slow.png'?1800:0)};reader.onerror=()=>this.onerror?.(reader.error);reader.readAsDataURL(file);}
              };
            }''')
            page.locator('#logo-inp').set_input_files(images['slow.png'])
            page.locator('#remove-logo').click()
            page.wait_for_timeout(2000);preset_saved(page)
            expect(page.locator('#logo-label')).to_have_text('Logo eklenmedi')
            assert not api(page,'/api/journal')['assets'].get('logo')
            page.locator('#logo-inp').set_input_files(images['slow.png'])
            page.locator('#logo-inp').set_input_files(images['fast.png'])
            expect(page.locator('#logo-label')).to_have_text('fast.png')
            page.wait_for_timeout(2000);preset_saved(page)
            expect(page.locator('#logo-label')).to_have_text('fast.png')
            assert api(page,'/api/journal')['assets']['logo']['name']=='fast.png'
            # A clean old window can close after another window changes the account.
            assert page.evaluate('journalWorkspace.prepareToClose()') is True
            other=context.new_page();other.goto(url,wait_until='networkidle');ready(other)
            other.locator('#logout-button').click();expect(other.locator('#auth-screen')).to_be_visible()
            result=page.evaluate('aiditorFetch("/api/journal").then(r=>r.status)')
            assert result==401
            assert page.evaluate('journalWorkspace.prepareToClose()') is True
            browser.close()
            print('PASS: lost save/import response retry, import close guard, logo remove/reselection races, clean stale window close')
        finally:server.stop()


if __name__=='__main__':run()
