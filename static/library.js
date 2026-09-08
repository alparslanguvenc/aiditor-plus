/* Local article library. Disk acknowledgement, not a timer, means "saved". */
window.articleLibrary = (() => {
  let ready = false, locked = false, dirty = false, conflict = false;
  let currentId = null, revision = 0, sequence = 0, timer, inFlight, attempt;
  let lastSnapshot = '', records = [], lastSavedAt = '';
  const editor = document.getElementById('article-editor');
  const status = document.getElementById('autosave-status');
  const retry = document.getElementById('autosave-retry');
  const copyButton = document.getElementById('save-conflict-copy');
  const newButton = document.getElementById('new-article');

  function notify(message, state = 'saved') {
    status.textContent = message; status.dataset.state = state;
    retry.hidden = state !== 'error' || conflict;
    copyButton.hidden = !conflict;
  }
  function savedStatus() {
    notify(lastSavedAt ? `Otomatik kaydedildi · ${new Date(lastSavedAt).toLocaleTimeString('tr-TR')}` :
      'Yeni taslak · İlk değişikliğinizde otomatik kaydedilecek');
  }
  function lock(value) { locked = value; editor.inert = value || !ready || accountBlocked; newButton.disabled = value || !ready || accountBlocked; }
  async function api(url, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await aiditorFetch(url, {...options, signal:controller.signal});
      const result = await response.json();
      if (!response.ok || !result.ok) {
        const error = new Error(result.error || 'Kayıt alanı yanıt vermedi.'); error.status = response.status; throw error;
      }
      return result;
    } catch (error) {
      if (error.name === 'AbortError' || error instanceof TypeError) {
        throw new Error('Kayıt servisine ulaşılamadı. Değişiklikler henüz diske kaydedilmedi.');
      }
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function renderList() {
    const query = document.getElementById('article-search').value.toLocaleLowerCase('tr-TR');
    const list = document.getElementById('article-list'); list.replaceChildren();
    const matches = records.filter(record => `${record.title} ${record.authors}`.toLocaleLowerCase('tr-TR').includes(query));
    for (const record of matches) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'article-record';
      button.dataset.articleId = record.id; button.setAttribute('aria-current', String(record.id === currentId));
      const title = document.createElement('strong'); title.textContent = record.title;
      const details = document.createElement('small');
      details.textContent = [record.authors || 'Yazar bilgisi henüz girilmedi', new Date(record.updated_at).toLocaleString('tr-TR'),
        record.id === currentId ? 'Açık makale' : 'Düzenlemek için seçin'].join(' · ');
      button.append(title, details); button.addEventListener('click', () => open(record.id));
      const row = document.createElement('div'); row.className = 'article-record-row';
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'article-delete';
      remove.textContent = 'Sil'; remove.setAttribute('aria-label', record.title + ' kaydını sil');
      remove.addEventListener('click', () => removeArticle(record)); row.append(button, remove); list.append(row);
    }
    if (!matches.length) {
      const empty = document.createElement('p'); empty.textContent = records.length ? 'Aramanızla eşleşen makale yok.' :
        'Henüz kayıt yok. Makale bilgilerini girmeye veya Word dosyanızı aktarmaya başlayın.';
      list.append(empty);
    }
  }
  async function refresh() {
    const result = await api('/api/articles'); records = result.articles; renderList();
  }
  function changed() {
    if (!ready || locked || accountBlocked) return;
    sequence++; dirty = true;
    if (!conflict) notify('Değişiklikler kaydediliyor…', 'pending');
    // Coalesce rapid keystrokes without postponing indefinitely while typing.
    if (!timer) timer = setTimeout(() => { timer = null; flush(); }, 350);
  }
  async function writeLoop(duringImport) {
    try {
      while (dirty || attempt) {
        if (docxImporting && !duringImport) return false;
        if (!attempt) {
          const capturedSequence = sequence;
          const project = await snapshotProject();
          const snapshot = JSON.stringify(project);
          if (snapshot === lastSnapshot) {
            if (capturedSequence === sequence) dirty = false;
            continue;
          }
          if (new Blob([snapshot]).size > 48 * 1024 * 1024 - 1024) throw new Error('Bu taslak 48 MB kayıt sınırını aşıyor. Şekilleri küçültün veya JSON yedeği alın.');
          if (!currentId) currentId = crypto.randomUUID();
          attempt = {id:currentId, snapshot, sequence:capturedSequence,
            body:JSON.stringify({project, base_revision:revision})};
        }
        notify('Diske kaydediliyor…', 'saving');
        const result = await api(`/api/articles/${attempt.id}`, {method:'PUT',
          headers:{'Content-Type':'application/json','X-Aiditor-Request':'1'}, body:attempt.body});
        revision = result.article.revision; lastSavedAt = result.article.updated_at;
        lastSnapshot = attempt.snapshot;
        dirty = sequence !== attempt.sequence; attempt = null;
        records = [result.article, ...records.filter(record => record.id !== result.article.id)];
        renderList();
      }
      savedStatus(); return true;
    } catch (error) {
      conflict = error.status === 409;
      notify(error.message + (conflict ? '' : ' Pencereyi kapatmayın; yeniden deneyebilir veya JSON yedeği alabilirsiniz.'), 'error');
      return false;
    }
  }
  async function flush(duringImport = false) {
    clearTimeout(timer); timer = null;
    if (!ready || conflict) return false;
    if (inFlight) {
      if (!await inFlight) return false;
      return dirty || attempt ? flush(duringImport) : true;
    }
    if (docxImporting && !duringImport) {
      if (dirty) timer = setTimeout(() => { timer = null; flush(); }, 350);
      return false;
    }
    inFlight = writeLoop(duringImport);
    try { return await inFlight; }
    finally { inFlight = null; }
  }
  function resetIdentity() {
    currentId = null; revision = 0; lastSnapshot = ''; lastSavedAt = ''; attempt = null; conflict = false; dirty = false;
  }
  async function beforeReplacement() {
    // Called only after import validation, before any fields are overwritten.
    if (!ready || locked) { showToast('Kayıt alanının açılmasını bekleyin.'); return false; }
    if (!await flush(true)) { showToast('Mevcut makale kaydedilemedi; alanlar değiştirilmedi.'); return false; }
    resetIdentity(); return true;
  }
  function imported() { changed(); }
  async function open(id, startup = false) {
    if (locked || docxImporting || document.getElementById('btn-gen').disabled) return;
    if (id === currentId && !startup) return;
    lock(true);
    try {
      if (!startup && !await flush()) return;
      const result = await api(`/api/articles/${id}`);
      const project = result.article.project;
      const prepared = prepareProjectFigures(project);
      await applySavedProject(project, prepared, result.article.title);
      currentId = id; revision = result.article.revision; lastSavedAt = result.article.updated_at;
      // DOM-local section/figure IDs are recreated on restore.
      lastSnapshot = JSON.stringify(await snapshotProject());
      dirty = false; attempt = null; conflict = false;
      savedStatus(); renderList();
    } catch (error) { notify('Makale açılamadı: ' + error.message, 'error'); }
    finally { lock(false); }
  }
  async function newArticle() {
    if (locked || docxImporting || document.getElementById('btn-gen').disabled) return;
    lock(true);
    try {
      if (!await flush()) return;
      const blank = {data:{cover:{year:String(new Date().getFullYear()), first_page_fit:journalWorkspace.settings.first_page_fit || 'auto'}, abstract:{}, authors:[{}],
        sections:DEFAULT_SECS.map((section, i) => ({...section,id:String(i)})), figtables:[], extra:{}, references:''}, figures:{}};
      await applySavedProject(blank, {}, 'Yeni makale'); resetIdentity();
      lastSnapshot = JSON.stringify(await snapshotProject());
      setDocxImportStatus('', ''); savedStatus(); renderList();
      document.getElementById('c-tr-title').focus();
    } finally { lock(false); }
  }
  async function removeArticle(record) {
    if (locked || docxImporting || document.getElementById('btn-gen').disabled) return;
    if (!confirm('“' + record.title + '” kaydı bu dergi hesabından silinecek. Gerekliyse önce JSON yedeği alın. Silinsin mi?')) return;
    if (!await flush()) return;
    const wasCurrent = currentId === record.id;
    const saved = records.find(item => item.id === record.id) || record;
    lock(true);
    try {
      await api(`/api/articles/${record.id}`, {method:'DELETE', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({base_revision:saved.revision})});
      records = records.filter(item => item.id !== record.id);
      if (wasCurrent) resetIdentity();
      renderList(); lock(false);
      if (wasCurrent) await newArticle();
      showToast('Makale kaydı silindi.');
    } catch (error) { showToast('Kayıt silinemedi: ' + error.message); }
    finally { lock(false); }
  }
  async function saveCopy() {
    if (locked || docxImporting || !conflict) return;
    resetIdentity(); changed(); await flush();
  }
  async function prepareToClose() {
    if (locked || docxImporting) { showToast('İşlemin tamamlanmasını bekleyin; pencere henüz kapatılamaz.'); return false; }
    // A changed account cannot accept writes from this page. A fully saved page
    // may close, while any unsaved snapshot or uncertain request stays protected.
    if (accountBlocked || !ready) return !(dirty || attempt || inFlight);
    lock(true);
    try { return await flush(); }
    finally { lock(false); }
  }
  async function initialize() {
    lock(true);
    try {
      await refresh(); ready = true; lock(false);
      if (records.length) await open(records[0].id, true);
      else { document.getElementById('c-first-page-fit').value = journalWorkspace.settings.first_page_fit || 'auto'; lastSnapshot = JSON.stringify(await snapshotProject()); savedStatus(); }
    } catch (error) { notify(error.message, 'error'); lock(false); }
  }
  document.getElementById('article-search').addEventListener('input', renderList);
  document.getElementById('library-refresh').addEventListener('click', () => refresh().catch(error => notify(error.message, 'error')));
  newButton.addEventListener('click', newArticle);
  retry.addEventListener('click', () => ready ? flush() : initialize());
  copyButton.addEventListener('click', saveCopy);
  ['input','change','click','paste','drop'].forEach(event => editor.addEventListener(event, changed));
  const observer = new MutationObserver(changed);
  ['authors-list','sections-list','ft-list'].forEach(id => observer.observe(document.getElementById(id), {
    subtree:true, childList:true, characterData:true, attributes:true,
    attributeFilter:['colspan','rowspan','data-bold','data-italic','data-underline','data-align','data-bgcolor','data-textcolor'],
  }));
  window.addEventListener('beforeunload', event => {
    if (dirty || attempt || inFlight || locked || docxImporting) {
      flush(); event.preventDefault(); event.returnValue = '';
    }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) flush(); });
  window.addEventListener('online', () => { if (dirty && !conflict) flush(); });
  document.addEventListener('DOMContentLoaded', () => { window.aiditorAccountReady.then(initialize); });
  return {flush, beforeReplacement, imported, prepareToClose, open, newArticle,
    get ready() { return ready; }, get currentId() { return currentId; }, get dirty() { return dirty; }};
})();
