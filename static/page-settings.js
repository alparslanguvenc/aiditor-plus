/* Plain text preview only; no user content is interpreted as HTML. */
(() => {
  let activeSlot = null;
  document.querySelectorAll('[data-running-slot]').forEach(el => el.addEventListener('focus', () => { activeSlot = el; }));
  document.querySelectorAll('[data-running-token]').forEach(button => button.addEventListener('click', () => {
    const status = document.getElementById('running-token-status');
    if (!activeSlot || activeSlot.closest('[hidden]')) { status.textContent = 'Önce sol, orta veya sağ metin alanlarından birini seçin.'; return; }
    const text = '{' + button.dataset.runningToken + '}';
    if (activeSlot.value.length - (activeSlot.selectionEnd - activeSlot.selectionStart) + text.length > 180) { status.textContent = 'Bu alan en çok 180 karakter olabilir.'; return; }
    activeSlot.setRangeText(text, activeSlot.selectionStart, activeSlot.selectionEnd, 'end');
    activeSlot.dispatchEvent(new Event('input', {bubbles:true})); activeSlot.focus();
    status.textContent = 'Otomatik bilgi eklendi; gerçek makale bilgisi çıktıda yer alacak.';
  }));
  window.updateRunningPreview = values => {
    for (const group of document.querySelectorAll('[data-running-kind]')) {
      const kind = group.dataset.runningKind;
      for (const fields of group.querySelectorAll('[data-running-variant]')) {
        const variant = fields.dataset.runningVariant;
        fields.hidden = variant === '_first' ? values[kind+'_first_mode'] !== 'custom' : variant === '_even' ? values[kind+'_mode'] !== 'odd_even' : !['same','odd_even'].includes(values[kind+'_mode']);
      }
    }
    const holder = document.getElementById('running-previews'); holder.replaceChildren();
    const samples = {dergi:values.journal_name_tr || values.journal_name_en || 'Dergi adı', dergi_en:values.journal_name_en || 'Journal name', baslik:'Örnek makale başlığı',kisa_baslik:'Örnek kısa başlık',yazarlar:'Örnek ve Smith',yil:'2026',cilt:'4',sayi:'2',doi:'10.xxxx/örnek',issn:values.issn_online || values.issn_print || 'ISSN'};
    for (const [variant, title, number] of [['first','İlk sayfa',1], ['even','Çift sayfa',2], ['odd','Tek sayfa',3]]) {
      const paper=document.createElement('div');paper.className='running-preview';
      const label=document.createElement('strong');label.textContent=title;paper.append(label);
      for (const kind of ['header','footer']) {
        const mode=values[kind+'_mode'], first=values[kind+'_first_mode'];
        const customFirst=variant==='first' && first==='custom';
        let slots=['','',''];
        if (!(variant==='first' && first==='none') && (mode!=='none' || customFirst)) {
          const suffix=customFirst ? '_first' : mode==='odd_even' && variant==='even' ? '_even' : '';
          slots=mode==='standard' && !customFirst ? ['',kind==='header' ? 'Yazar (2026). Makale başlığı. Dergi adı.' : '{sayfa}',''] : ['left','center','right'].map(slot=>values[kind+suffix+'_'+slot] || '');
        }
        const line=document.createElement('div');line.className='running-preview-'+kind;
        if(values[kind+'_rule']==='line' && slots.some(Boolean))line.classList.add('with-rule');
        if(!slots[0] && !slots[2]) line.classList.add('center-only');
        slots.forEach(text=>{const span=document.createElement('span');span.textContent=text.replace(/\{([a-z_]+)\}/g,(all,key)=>key==='sayfa' ? String(number) : samples[key] ?? all);line.append(span);});
        paper.append(line);
        if(kind==='header'){const body=document.createElement('div');body.className='running-preview-body';body.textContent='Makale metni';paper.append(body);}
      }
      holder.append(paper);
    }
  };
})();
