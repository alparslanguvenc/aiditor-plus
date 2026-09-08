/* Portable, explicit backups: article data and figure files stay on the user's computer. */
const coverFields = {
  tr_title:'c-tr-title', en_title:'c-en-title', year:'c-year', volume:'c-volume', issue:'c-issue',
  start_page:'c-start', end_page:'c-end', doi:'c-doi', article_type:'c-article-type',
  received:'c-received', accepted:'c-accepted', published:'c-published',
  author_short:'c-author-short', editor:'c-editor', ethics:'c-ethics', title_note:'c-title-note', first_page_fit:'c-first-page-fit',
};
function fileDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Şekil dosyası okunamadı.'));
    reader.readAsDataURL(file);
  });
}
const figureDataCache = new WeakMap();
async function snapshotProject() {
  const data = collectFormData();
  // Keep unfinished inputs verbatim (including spaces and empty metadata).
  for (const [key, id] of Object.entries(coverFields)) data.cover[key] = document.getElementById(id).value;
  for (const [key, id] of Object.entries({tr_abs:'a-tr-abs',tr_kw:'a-tr-kw',en_abs:'a-en-abs',en_kw:'a-en-kw'})) {
    data.abstract[key] = document.getElementById(id).value;
  }
  document.querySelectorAll('#authors-list .author-row').forEach((row, i) => {
    row.querySelectorAll('[data-f]').forEach(field => {
      if (field.type !== 'checkbox') data.authors[i][field.dataset.f] = field.value;
    });
  });
  document.querySelectorAll('#sections-list .sec-block').forEach((row, i) => {
    ['name','content'].forEach(key => { data.sections[i][key] = row.querySelector(`[data-f="${key}"]`).value; });
  });
  document.querySelectorAll('#ft-list .ft-block').forEach((block, i) => {
    ['number','tr_cap','en_cap','after_para'].forEach(key => {
      const field = block.querySelector(`[data-f="${key}"]`);
      if (field) data.figtables[i][key] = field.value;
    });
    if (data.figtables[i].tbl_model) block.querySelectorAll('.tbl-editor tr').forEach((row, ri) => {
      [...row.cells].forEach((cell, ci) => { data.figtables[i].tbl_model.rows[ri][ci].text = cell.innerText; });
    });
  });
  data.references = document.getElementById('refs').value;
  data.extra.contrib = document.getElementById('ex-contrib').value;
  data.extra.conflict = document.getElementById('ex-conflict').value;
  const ui = {ack_enabled:document.getElementById('ack-on').checked, ack_text:document.getElementById('ex-ack').value};
  data.extra.ack = ui.ack_enabled ? ui.ack_text : '';
  const files = {...figFiles}, figures = {};
  for (const item of data.figtables.filter(item => item.type === 'figure')) {
    const file = files[item.file_key];
    item.file_missing = !file;
    if (file) {
      if (!figureDataCache.has(file)) figureDataCache.set(file, fileDataURL(file).catch(error => {
        figureDataCache.delete(file); throw error;
      }));
      figures[item.file_key] = {name:file.name, data:await figureDataCache.get(file)};
    }
  }
  return {format:'aiditor-project', version:1, data, figures, ui};
}

async function applySavedProject(project, prepared, filename) {
  const data = structuredClone(project.data);
  data.figtables.forEach(item => delete item.import_image_index);
  await applyDocxImport({...data, warnings:[], stats:{}}, '', filename, false);
  for (const [key, id] of Object.entries(coverFields)) document.getElementById(id).value = data.cover[key] || '';
  document.getElementById('authors-list').replaceChildren();
  data.authors.forEach(author => addAuthor(author));
  refreshAuthorNums();
  [...document.querySelectorAll('#ft-list .ft-block')].forEach((block, index) => {
    const saved = data.figtables[index], image = prepared[saved.file_key];
    ['number','tr_cap','en_cap','after_para'].forEach(key => {
      const field = block.querySelector(`[data-f="${key}"]`);
      if (field && typeof saved[key] === 'string') field.value = saved[key];
    });
    if (saved.type === 'figure' && image) {
      const uid = block.id.slice(3); figFiles[uid] = image; showFigPreview(uid, image);
    }
  });
  if (typeof project.ui?.ack_text === 'string' && typeof project.ui?.ack_enabled === 'boolean') {
    document.getElementById('ack-on').checked = project.ui.ack_enabled;
    document.getElementById('ex-ack').value = project.ui.ack_text;
    document.getElementById('ack-body').style.display = project.ui.ack_enabled ? '' : 'none';
  }
  const missing = data.figtables.filter(item => item.type === 'figure' && !prepared[item.file_key]).length;
  setDocxImportStatus('success', 'Kayıtlı proje açıldı; yazar, kapak, metin, tablolar ve şekiller geri yüklendi.' +
    (missing ? ` ${missing} şekil taslakta boş bırakılmış; çıktıdan önce dosyasını seçin.` : ''));
}

function prepareProjectFigures(project) {
  const prepared = Object.create(null);
  if (project.figures != null && (typeof project.figures !== 'object' || Array.isArray(project.figures))) {
    throw new Error('Projedeki şekil listesi geçersiz.');
  }
  for (const [key, image] of Object.entries(project.figures || {})) {
    if (!/^[A-Za-z0-9_-]{1,60}$/.test(key) || !image || typeof image.name !== 'string' ||
        typeof image.data !== 'string' || !/\.(png|jpe?g|pdf)$/i.test(image.name) ||
        !/^data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+$/.test(image.data)) {
      throw new Error('Projedeki şekil verisi geçersiz.');
    }
    const [header, body] = image.data.split(',');
    const bytes = Uint8Array.from(atob(body), char => char.charCodeAt(0));
    prepared[key] = new File([bytes], image.name, {type:header.slice(5).split(';')[0]});
    figureDataCache.set(prepared[key], Promise.resolve(image.data));
  }
  return prepared;
}
async function saveProject() {
  try {
    if (docxImporting) throw new Error('Word aktarımının tamamlanmasını bekleyin.');
    const blob = new Blob([JSON.stringify(await snapshotProject())], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = 'aiditor-makale.json';
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    showToast('Proje, şekillerle birlikte kaydedildi. “Proje Aç” ile düzenlemeye devam edebilirsiniz.');
  } catch (error) { showToast(error.message); }
}
async function loadProject(file) {
  if (!file || docxImporting) return;
  if (document.getElementById('btn-gen').disabled) { showToast('Çıktı üretiminin tamamlanmasını bekleyin.'); return; }
  docxImporting = true;
  const generateButton = document.getElementById('btn-gen');
  const previouslyDisabled = generateButton.disabled;
  generateButton.disabled = true;
  try {
    if (file.size > 48 * 1024 * 1024) throw new Error('Proje dosyası en fazla 48 MB olabilir.');
    const project = JSON.parse(await file.text());
    let data = project?.data;
    if (!['aiditor-project','jgttr-project'].includes(project?.format) || project.version !== 1 || !data?.cover || !data?.abstract ||
        !['sections','authors','figtables'].every(key => Array.isArray(data[key]))) {
      throw new Error('Bu dosya geçerli bir AI-ditor Plus projesi değil.');
    }
    const prepared = prepareProjectFigures(project);
    const validation = new FormData();
    for (const [key, image] of Object.entries(prepared)) validation.append('fig_' + key, image);
    validation.append('data', JSON.stringify(data));
    validation.append('check_figures', '1');
    validation.append('draft', '1');
    const checked = await aiditorFetch('/validate_form', {method:'POST', body:validation});
    if (!(checked.headers.get('Content-Type') || '').includes('application/json')) {
      throw new Error('Proje doğrulama servisi yanıt vermedi. Güncel uygulamayı açın.');
    }
    const result = await checked.json();
    if (!checked.ok || !result.ok) throw new Error(result.error || 'Proje alanları geçersiz.');
    data = result.data;
    if (!data) throw new Error('Çalışan uygulama eski bir sürüm; güncel uygulamayı açın.');
    if (articleFormHasContent() && !confirm('Mevcut alanlar kayıtlı projeyle değiştirilecek. Devam edilsin mi?')) return;
    if (window.articleLibrary && !await articleLibrary.beforeReplacement()) return;
    await applySavedProject({...project, data}, prepared, file.name);
    window.articleLibrary?.imported();
    showToast('Proje açıldı. Düzenlemeye devam edebilirsiniz.');
  } catch (error) { showToast('Proje açılamadı: ' + docxImportErrorMessage(error)); }
  finally {
    docxImporting = false;
    generateButton.disabled = previouslyDisabled;
    document.getElementById('project-file').value = '';
  }
}
