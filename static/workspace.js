/* Account identity is captured per page: an old tab can never write into a new account. */
let aiditorAccount = null;
let accountBlocked = false;
let resolveAccountReady;
window.aiditorAccountReady = new Promise(resolve => { resolveAccountReady = resolve; });
window.aiditorFetch = async function(url, options = {}) {
  if (accountBlocked) throw new Error('Bu sekmenin hesabı değişti. JSON yedeği aldıktan sonra sayfayı yenileyin.');
  const headers = new Headers(options.headers || {});
  if (aiditorAccount) headers.set('X-Aiditor-Account', aiditorAccount.id);
  if (options.method && !['GET','HEAD'].includes(options.method.toUpperCase())) headers.set('X-Aiditor-Request','1');
  const response = await fetch(url, {...options, headers});
  if (response.status === 401 || response.status === 409) {
    const result = await response.clone().json().catch(() => ({}));
    if (response.status === 401 || result.code === 'account_changed') {
      accountBlocked = true;
      document.getElementById('article-editor').inert = true;
      document.getElementById('journal-form').inert = true;
      if (!document.getElementById('session-warning')) {
        const banner = document.createElement('div'); banner.id = 'session-warning'; banner.className = 'session-warning';
        banner.setAttribute('role','alert');
        const message = document.createElement('p'); message.textContent = 'Oturumunuz kapandı veya başka bir sekmede hesap değiştirildi. Bu sekmedeki içerik diğer hesaba kaydedilmez. Önce gerekliyse yedek alın, ardından sayfayı yenileyin.';
        banner.append(message);
        for (const [label, callback] of [['Makale JSON yedeği al', () => saveProject()],['Dergi ayarlarını yedekle', () => journalWorkspace.exportPreset()],['Sayfayı yenile', () => location.reload()]]) {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-sm btn-outline-secondary me-2'; button.textContent = label; button.addEventListener('click',callback); banner.append(button);
        }
        document.getElementById('main-workspace').prepend(banner);
      }
    }
  }
  return response;
};
window.journalWorkspace = (() => {
  const byId = id => document.getElementById(id);
  const fields = {
    journal_name_tr:'js-name-tr', journal_name_en:'js-name-en', issn_print:'js-issn-print', issn_online:'js-issn-online',
    journal_url:'js-url', font_family:'js-font', body_size:'js-body-size', accent_color:'js-accent-color',
    corresponding_marker:'js-corr-marker', logo_height_cm:'js-logo-height', doi_position:'js-doi-position',
    header_layout:'js-header-layout', footer_layout:'js-footer-layout', footer_text:'js-footer-text', first_page_fit:'js-first-page-fit',
  };
  let settings = {}, assets = {logo:null,license:null}, templates = [], revision = 0;
  let ready = false, dirty = false, sequence = 0, inFlight = null, timer = null, conflict = false, authMode = 'login';
  let attempt = null, replacementAttempt = null, replacing = false, loading = false;
  const assetJobs = new Set(), assetGenerations = {logo:0,license:0}, assetSlotJobs = {};
  const localTemplates = [
    {id:'classic', name:'Klasik', description:'Çift dilli kimlik, çizgili üst bilgi ve geleneksel akademik düzen.'},
    {id:'contemporary', name:'Çağdaş', description:'Belirgin renk bandı ve güçlü bir başlık hiyerarşisi.'},
    {id:'centered', name:'Ortalanmış', description:'Simetrik logo, merkezde dergi kimliği ve dengeli başlık.'},
    {id:'minimal', name:'Sade', description:'İnce çizgiler, yalın kimlik ve ferah bir sayfa.'},
  ];
  function status(message, state='saved') {
    for (const id of ['journal-save-status','preset-mini-status']) { byId(id).textContent=message; byId(id).dataset.state=state; }
    byId('journal-reload').hidden = !conflict && state !== 'error';
  }
  function collect() {
    const next = {...settings};
    for (const [key,id] of Object.entries(fields)) next[key] = byId(id).value;
    next.english_only = byId('js-english-only').checked;
    next.logo_height_cm = Number(byId('js-logo-height').value) || 2.3;
    next.body_size = Number(byId('js-body-size').value) || 10;
    next.font = next.font_family;
    next.template_id = next.header_layout;
    return next;
  }
  window.collectJournalSettings = collect;
  function apply(next) {
    settings = {...next};
    const values = {font_family:next.font_family || next.font || 'Palatino Linotype',body_size:10,accent_color:'#176B6A',
      logo_height_cm:2.3,corresponding_marker:'*',doi_position:'bottom',header_layout:next.template_id || 'classic',
      footer_layout:'full',first_page_fit:'auto',...next};
    const fontAliases = {texgyrepagella:'Palatino Linotype',texgyretermes:'Times New Roman',tgschola:'Century',texgyrebonum:'Century',latinmodern:'Latin Modern',carlito:'Calibri',texgyreheros:'Sans Serif'};
    values.font_family = fontAliases[values.font_family] || values.font_family;
    for (const [key,id] of Object.entries(fields)) byId(id).value = values[key] ?? '';
    byId('js-english-only').checked = !!next.english_only;
    updateAssets(); renderTemplates(); updatePreview();
  }
  function updateAssets() {
    for (const [key,id] of [['logo','logo'],['license','ccby']]) {
      byId(id+'-label').textContent = assets[key]?.name || (key==='logo' ? 'Logo eklenmedi' : 'Lisans görseli eklenmedi');
      byId('remove-'+key).hidden = !assets[key];
    }
  }
  function pageSketch(id, values = {}, imageAsset = null) {
    const safeId = ['classic','contemporary','centered','minimal'].includes(id) ? id : 'classic';
    const page=document.createElement('div'); page.className='mini-paper '+safeId; page.setAttribute('aria-hidden','true');
    if (/^#[0-9a-f]{6}$/i.test(values.accent_color || '')) page.style.setProperty('--page-accent',values.accent_color);
    if (values.font_family === 'Calibri' || values.font_family === 'Sans Serif') page.style.fontFamily='Arial,sans-serif';
    const mast=document.createElement('div');mast.className='mini-mast';
    if (imageAsset && /^data:image\/(png|jpeg);base64,/i.test(imageAsset.data)) { const img=document.createElement('img'); img.src=imageAsset.data; img.alt='';mast.append(img); }
    else if(imageAsset?.name){const icon=document.createElement('span');icon.className='asset-pdf';icon.textContent=imageAsset.name;mast.append(icon);}
    else {const icon=document.createElement('i');icon.textContent='J';mast.append(icon);}
    const name=document.createElement('b');name.textContent=(values.english_only ? values.journal_name_en : values.journal_name_tr) || values.journal_name_en || 'AKADEMİK ARAŞTIRMALAR DERGİSİ';mast.append(name);page.append(mast);
    const band=document.createElement('div');band.className='mini-band';band.textContent=(values.issn_online ? 'e-ISSN '+values.issn_online+' · ' : '')+'2026 · CİLT 1 · SAYI 1';page.append(band);
    const title=document.createElement('h4');title.textContent=values.english_only ? 'Research, knowledge and new perspectives' : 'Araştırma, bilgi ve yeni bakış açıları';page.append(title);
    const author=document.createElement('div');author.className='mini-authors';author.textContent='Yazar Adı · Yazar Adı';page.append(author);
    const rule=document.createElement('div');rule.className='mini-rule';page.append(rule);
    const abstracts=document.createElement('div');abstracts.className='mini-abstracts';
    for (const heading of (values.english_only ? ['ABSTRACT','1. INTRODUCTION'] : ['ÖZET','ABSTRACT'])) {const group=document.createElement('div');const h=document.createElement('h5');h.textContent=heading;const lines=document.createElement('div');lines.className='mini-lines';group.append(h,lines);abstracts.append(group);}page.append(abstracts);
    const foot=document.createElement('div');foot.className='mini-foot';foot.textContent=values.footer_text || values.journal_url || 'Dergi bilgileri · Lisans ve yayın notları';page.append(foot);
    if (values.footer_layout === 'minimal') foot.style.borderTop='0';
    return page;
  }
  function renderTemplates() {
    const gallery=byId('template-gallery');gallery.replaceChildren();
    for (const item of templates.length ? templates : localTemplates) {
      const selected=(settings.template_id || 'classic')===item.id;
      const button=document.createElement('button');button.type='button';button.className='template-option';button.dataset.templateId=item.id;button.setAttribute('aria-pressed',String(selected));
      const thumbnail=document.createElement('img');thumbnail.className='template-thumbnail';thumbnail.src='/static/previews/'+encodeURIComponent(item.id)+'.png';thumbnail.alt=item.name+' ilk sayfa örneği';thumbnail.loading='lazy';
      thumbnail.addEventListener('error',()=>thumbnail.replaceWith(pageSketch(item.id,item.settings || {})),{once:true});button.append(thumbnail);
      const name=document.createElement('strong');name.textContent=item.name;
      if(selected){const mark=document.createElement('span');mark.className='template-selected';mark.textContent='✓ SEÇİLİ';name.append(mark);}
      const description=document.createElement('small');description.textContent=item.description;button.append(name,description);
      button.addEventListener('click',()=>{
        if(!ready || accountBlocked || replacing || loading || replacementAttempt) return;
        const current=collect();const identity={};
        for(const key of ['journal_name_tr','journal_name_en','issn_print','issn_online','journal_url','footer_text','english_only']) identity[key]=current[key];
        apply({...current,...(item.settings||{}),...identity,template_id:item.id,header_layout:item.id});
        changed();showToast(item.name+' düzeni seçildi. Dergi kimliğiniz ve logolarınız korundu.');
      });gallery.append(button);
    }
  }
  function updatePreview() {
    const values=collect();byId('live-preview').replaceChildren(pageSketch(values.header_layout,values,assets.logo));
    byId('journal-heading').textContent=values.journal_name_tr || values.journal_name_en || aiditorAccount?.display_name || 'Derginiz';
    const layout=(templates.length ? templates : localTemplates).find(item=>item.id===values.template_id)?.name || 'Özel';
    byId('journal-summary').textContent=`${layout} düzen · ${values.font_family || 'Palatino Linotype'} · ${values.body_size || 10} punto. Dergi ayarlarınız yeni girişlerde korunur.`;
  }
  function changed(fromAsset = false) {
    if(!ready || accountBlocked || replacementAttempt || ((replacing || loading) && !fromAsset)) return;
    sequence++;dirty=true;updatePreview();
    if(!conflict) status('Ayarlar kaydediliyor…','pending');
    clearTimeout(timer);timer=setTimeout(()=>flush(),700);
  }
  async function api(url,options={}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response=await aiditorFetch(url,{...options,signal:controller.signal});const result=await response.json();
      if(!response.ok || !result.ok){const error=new Error(result.error || 'İşlem tamamlanamadı.');error.status=response.status;error.code=result.code;throw error;}
      return result;
    } catch(error) {
      if(error.name==='AbortError')throw new Error('Kayıt servisi zamanında yanıt vermedi. Yeniden deneyin veya JSON yedeği alın.');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function invalidateAssetRead(key) {
    assetGenerations[key]++;
    if(assetSlotJobs[key])assetJobs.delete(assetSlotJobs[key]);
    delete assetSlotJobs[key];
  }
  function invalidateAssetReads() {
    invalidateAssetRead('logo');invalidateAssetRead('license');
  }
  async function load() {
    if(loading || replacing || replacementAttempt)throw new Error('Devam eden dergi ayarları işlemini tamamlayın; gerekiyorsa içe aktarma kaydını yeniden deneyin.');
    loading=true;byId('journal-form').inert=true;
    clearTimeout(timer);timer=null;
    invalidateAssetReads();
    try {
      // Settle any already dispatched write before replacing the local revision.
      if(inFlight)await inFlight;
      const result=await api('/api/journal');
      assets={logo:null,license:null,...result.assets};revision=result.revision;dirty=false;conflict=false;attempt=null;
      byId('logo-inp').value='';byId('ccby-inp').value='';
      apply(result.settings);status('Dergi ayarları kayıtlı');
    } finally {loading=false;byId('journal-form').inert=accountBlocked || !!replacementAttempt;if(ready && dirty && !conflict && !accountBlocked && !timer)timer=setTimeout(()=>flush(),700);}
  }
  async function flush(duringReplacement = false) {
    clearTimeout(timer);timer=null;
    if(replacementAttempt)return retryReplacement();
    if(!ready || conflict || accountBlocked || loading || (replacing && !duringReplacement)) return false;
    if(assetJobs.size) await Promise.all([...assetJobs]);
    // File reads and awaited writes can yield to a reload or replacement.
    if(!ready || conflict || accountBlocked || loading || (replacing && !duringReplacement)) return false;
    if(inFlight){if(!await inFlight)return false;return dirty || attempt ? flush(duringReplacement) : true;}
    if(!dirty && !attempt) return true;
    inFlight=(async()=>{
      try {
        while(dirty || attempt){
          if(!attempt){
            const current=collect();
            attempt={sequence,settings:current,body:JSON.stringify({settings:current,assets,base_revision:revision})};
          }
          // Retry these exact bytes after a lost response before sending newer edits.
          // The store recognizes the already committed request and returns its revision.
          status('Dergi ayarları diske kaydediliyor…','saving');
          const result=await api('/api/journal',{method:'PUT',headers:{'Content-Type':'application/json'},body:attempt.body});
          revision=result.revision;settings={...attempt.settings,...(result.settings || {})};
          dirty=sequence!==attempt.sequence;attempt=null;
        }
        status('Dergi ayarları kaydedildi · '+new Date().toLocaleTimeString('tr-TR'));return true;
      } catch(error){
        conflict=error.code==='revision_conflict';
        // A rejected validation request cannot have committed. Let corrected fields retry.
        if([400,413,422].includes(error.status))attempt=null;
        status(error.message+(conflict ? ' Yerel ayarlarınızın yedeğini alabilir, ardından kayıtlı ayarları yükleyebilirsiniz.' : ' Değişiklikler henüz kaydedilmedi.'),'error');return false;
      }
    })();
    try{return await inFlight;}finally{inFlight=null;}
  }
  function switchPane(name){
    for(const pane of ['journal','articles']){byId(pane+'-pane').hidden=pane!==name;byId(pane+'-tab').setAttribute('aria-selected',String(pane===name));}
  }
  function downloadJSON(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function exportPreset(){await Promise.all([...assetJobs]);downloadJSON({format:'aiditor-journal-preset',version:1,settings:collect(),assets},'aiditor-dergi-ayarlari.json');showToast('Dergi ayarları ve logolar JSON yedeğine eklendi.');}
  async function importPreset(file){
    if(!file)return;
    try{if(file.size>24*1024*1024)throw new Error('Ayar dosyası en fazla 24 MB olabilir.');const data=JSON.parse(await file.text());
      if(data.format!=='aiditor-journal-preset' || data.version!==1 || !data.settings || typeof data.settings!=='object' || Array.isArray(data.settings))throw new Error('Geçerli bir AI-ditor Plus dergi ayarları yedeği seçin.');
      if(await replacePreset(data.settings,data.assets || {}))showToast('Dergi ayarları ve logolar hesabınıza aktarıldı.');
    }catch(error){showToast('Yedek açılamadı: '+error.message);}finally{byId('import-preset').value='';}
  }
  function renderReplacementRecovery() {
    byId('import-preset-button').disabled=!!replacementAttempt;
    byId('template-gallery').querySelectorAll('button').forEach(button=>{button.disabled=!!replacementAttempt;});
    let banner=byId('journal-import-recovery');
    if(!replacementAttempt){banner?.remove();return;}
    if(banner)return;
    banner=document.createElement('div');banner.id='journal-import-recovery';banner.className='session-warning';banner.setAttribute('role','alert');
    const message=document.createElement('p');message.textContent='İçe aktarılan dergi ayarlarının kayıt sonucu henüz doğrulanamadı. Alanlarınız korunuyor ve düzenleme geçici olarak durduruldu. Aynı kaydı yeniden deneyerek işlemi tamamlayın.';
    const button=document.createElement('button');button.type='button';button.id='journal-import-retry';button.className='btn btn-sm btn-outline-secondary';button.textContent='İçe aktarma kaydını yeniden dene';
    button.addEventListener('click',async()=>{button.disabled=true;try{if(await flush())showToast('İçe aktarılan dergi ayarlarının kaydı doğrulandı.');}finally{button.disabled=false;}});
    banner.append(message,button);byId('main-workspace').prepend(banner);
  }
  async function sendReplacement() {
    const pending=replacementAttempt;
    try {
      const result=await api('/api/journal',{method:'PUT',headers:{'Content-Type':'application/json'},body:pending.body});
      revision=result.revision;assets={logo:null,license:null,...(result.assets || pending.assets)};
      apply(result.settings || pending.settings);dirty=false;conflict=false;attempt=null;replacementAttempt=null;
      byId('logo-inp').value='';byId('ccby-inp').value='';status('Dergi ayarları içe aktarıldı ve kaydedildi');return true;
    } catch(error) {
      // A transport failure or 5xx can follow a successful disk commit. Keep the
      // exact request for idempotent replay; fields remain locked until its ack.
      // A definite client rejection cannot have applied this request.
      if(error.status>=400 && error.status<500)replacementAttempt=null;
      status(error.message+(replacementAttempt ? ' İçe aktarma kaydının sonucunu yeniden deneyerek doğrulayın.' : ' Mevcut alanlar korundu.'),'error');
      throw error;
    }
  }
  async function retryReplacement() {
    if(!replacementAttempt)return true;
    if(replacing || loading || accountBlocked)return false;
    replacing=true;byId('journal-form').inert=true;
    try {return await sendReplacement();}
    catch(error){showToast(error.message);return false;}
    finally {replacing=false;byId('journal-form').inert=accountBlocked || !!replacementAttempt;renderReplacementRecovery();}
  }
  async function replacePreset(incomingSettings,incomingAssets){
    if(replacing || loading || replacementAttempt)throw new Error('Devam eden dergi ayarları işlemini tamamlayın; gerekiyorsa içe aktarma kaydını yeniden deneyin.');
    replacing=true;byId('journal-form').inert=true;
    try {
      // Invalid imports never replace current fields or invalidate their image reads.
      const validated=await api('/validate_journal',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({settings:incomingSettings,assets:{logo:null,license:null,...incomingAssets}})});
      if(!await flush(true))throw new Error('Mevcut dergi ayarları kaydedilemedi; içe aktarma uygulanmadı.');
      invalidateAssetReads();
      replacementAttempt={settings:validated.settings,assets:validated.assets,
        body:JSON.stringify({settings:validated.settings,assets:validated.assets,base_revision:revision})};
      return await sendReplacement();
    } finally {
      replacing=false;byId('journal-form').inert=accountBlocked || !!replacementAttempt;renderReplacementRecovery();
      if(ready && dirty && !replacementAttempt && !conflict && !accountBlocked && !timer)timer=setTimeout(()=>flush(),700);
    }
  }
  function readAsset(key,input){
    invalidateAssetRead(key);
    const generation=assetGenerations[key],file=input.files?.[0];if(!file)return;
    byId((key==='logo'?'logo':'ccby')+'-label').textContent=file.name+' · okunuyor…';
    byId('remove-'+key).hidden=false;
    const job=(async()=>{
      try {
        if(!/\.(png|jpe?g|pdf)$/i.test(file.name))throw new Error('PNG, JPG veya PDF dosyası seçin.');
        if(file.size>8*1024*1024)throw new Error('Görsel en fazla 8 MB olabilir.');
        const data=await fileDataURL(file);
        if(generation!==assetGenerations[key])return;
        assets[key]={name:file.name,data};updateAssets();changed(true);
      } catch(error) {
        if(generation!==assetGenerations[key])return;
        showToast(error.message);input.value='';updateAssets();
      }
    })();
    assetSlotJobs[key]=job;assetJobs.add(job);
    job.finally(()=>{assetJobs.delete(job);if(assetSlotJobs[key]===job)delete assetSlotJobs[key];});
  }
  function authModeChanged(mode){authMode=mode;byId('register-name-wrap').hidden=mode!=='register';byId('auth-display-name').required=mode==='register';byId('login-tab').setAttribute('aria-selected',String(mode==='login'));byId('register-tab').setAttribute('aria-selected',String(mode==='register'));byId('auth-form-title').textContent=mode==='login'?'Çalışma alanınıza girin':'Derginiz için bir hesap açın';byId('auth-description').textContent=mode==='login'?'Kayıtlı dergi ayarlarınız ve makaleleriniz sizi bekliyor.':'E-posta gerekmez. Dergi adınız, kullanıcı adınız ve parolanız yeterli.';byId('auth-submit').textContent=mode==='login'?'Giriş yap →':'Hesap oluştur →';byId('auth-password').autocomplete=mode==='login'?'current-password':'new-password';byId('auth-status').textContent='';}
  async function enter(user, newlyRegistered = false){
    aiditorAccount=Object.freeze({...user});byId('account-name').textContent=user.display_name;
    const result=await api('/api/templates');templates=result.templates || [];await load();ready=true;
    byId('auth-screen').hidden=true;byId('main-workspace').hidden=false;byId('account-controls').hidden=false;
    switchPane(!newlyRegistered && (settings.journal_name_tr || settings.journal_name_en) ? 'articles' : 'journal');
    if(!settings.journal_name_tr && !settings.journal_name_en){byId('js-name-tr').value=user.display_name;changed();}
    resolveAccountReady(user);
  }
  async function bootstrap(){
    byId('auth-submit').disabled=true;byId('session-retry').hidden=true;
    try{const response=await fetch('/api/auth/session');const result=await response.json();if(!response.ok || !result.ok)throw new Error(result.error || 'Oturum bilgisi alınamadı.');if(result.user)await enter(result.user);}
    catch(error){byId('auth-status').textContent='Uygulamaya bağlanılamadı: '+error.message;byId('session-retry').hidden=false;}
    finally{byId('auth-submit').disabled=false;}
  }
  async function prepareToClose(){
    // Authentication readiness is independent from a running import or write.
    // Even when journal work blocks closing, consult the article guard so its
    // pending changes still receive a chance to reach disk.
    let journalSafe=false;
    if(!replacing && !loading && !replacementAttempt){
      if(accountBlocked || !ready)journalSafe=!(dirty || attempt || replacementAttempt || inFlight || assetJobs.size);
      else journalSafe=await flush();
    }
    const articleSafe=window.articleLibrary ? await articleLibrary.prepareToClose() : true;
    return journalSafe && articleSafe && !(replacing || loading || dirty || attempt || replacementAttempt || inFlight || assetJobs.size);
  }
  document.addEventListener('DOMContentLoaded',()=>{
    byId('auth-username').maxLength=40;byId('auth-display-name').maxLength=120;byId('auth-display-name').minLength=2;
    renderTemplates();byId('session-retry').addEventListener('click',bootstrap);
    byId('login-tab').addEventListener('click',()=>authModeChanged('login'));byId('register-tab').addEventListener('click',()=>authModeChanged('register'));
    byId('auth-form').addEventListener('submit',async event=>{event.preventDefault();byId('auth-submit').disabled=true;byId('auth-status').textContent='';try{const response=await fetch('/api/auth/'+authMode,{method:'POST',headers:{'Content-Type':'application/json','X-Aiditor-Request':'1'},body:JSON.stringify({username:byId('auth-username').value,password:byId('auth-password').value,display_name:byId('auth-display-name').value})});const result=await response.json();if(!response.ok || !result.ok)throw new Error(result.error || 'Hesap işlemi tamamlanamadı.');byId('auth-password').value='';await enter(result.user, authMode==='register');}catch(error){byId('auth-status').textContent=error.message;}finally{byId('auth-submit').disabled=false;}});
    byId('logout-button').addEventListener('click',async()=>{try{if(!await prepareToClose())throw new Error('Kayıt tamamlanamadı. Çıkıştan önce JSON yedeği alın veya kayıt hatasını giderin.');await api('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});location.reload();}catch(error){showToast(error.message);}});
    ['journal','articles'].forEach(name=>byId(name+'-tab').addEventListener('click',()=>switchPane(name)));
    byId('journal-form').addEventListener('input',event=>{if(event.target.type!=='file')changed();});byId('journal-form').addEventListener('change',event=>{if(event.target.type!=='file'){if(event.target.id==='js-header-layout'){settings.template_id=event.target.value;renderTemplates();}changed();}});
    byId('journal-form').addEventListener('submit',event=>{event.preventDefault();if(!dirty)changed();flush();});
    byId('journal-reload').addEventListener('click',async()=>{if(dirty&&!confirm('Bu sekmedeki ayarlar sunucuda kayıtlı ayarlarla değiştirilecek. Önce gerekliyse JSON yedeği alın. Devam edilsin mi?'))return;try{await load();showToast('Hesapta kayıtlı ayarlar yüklendi.');}catch(error){status(error.message,'error');}});
    byId('logo-inp').addEventListener('change',event=>readAsset('logo',event.target));byId('ccby-inp').addEventListener('change',event=>readAsset('license',event.target));
    for(const [key,id] of [['logo','logo'],['license','ccby']])byId('remove-'+key).addEventListener('click',()=>{invalidateAssetRead(key);assets[key]=null;byId(id+'-inp').value='';updateAssets();changed();});
    byId('export-preset').addEventListener('click',exportPreset);byId('import-preset-button').addEventListener('click',()=>byId('import-preset').click());byId('import-preset').addEventListener('change',event=>importPreset(event.target.files[0]));
    // Labels inherited from the article editor are connected to their controls.
    document.querySelectorAll('#article-editor label:not([for])').forEach(label=>{const input=label.parentElement.querySelector('input,textarea,select');if(input?.id)label.htmlFor=input.id;});
    bootstrap();
  });
  window.addEventListener('beforeunload',event=>{if(dirty || attempt || replacementAttempt || inFlight || replacing || loading || assetJobs.size){flush();event.preventDefault();event.returnValue='';}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden && ready)flush();});
  return {flush,prepareToClose,exportPreset,get settings(){return collect();},get ready(){return ready && !replacing && !loading && !replacementAttempt;},get dirty(){return dirty || !!attempt || !!replacementAttempt;},get busy(){return replacing || loading || !!replacementAttempt || !!inFlight || assetJobs.size > 0;}};
})();
