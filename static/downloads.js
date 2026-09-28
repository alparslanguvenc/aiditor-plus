/* Fetch inside the signed-in page. Native URL downloads can lose WebKit cookies. */
window.downloadArticleOutput = async function (kind) {
  const word = kind === 'docx';
  const label = word ? 'Word' : 'ZIP';
  const prefix = word ? '/download_docx/' : '/download/';
  const method = word ? 'save_article_docx' : 'save_article_zip';
  const mime = word ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' : 'application/zip';
  const button = document.getElementById(word ? 'dl-docx' : 'dl-link');
  const status = document.getElementById(word ? 'docx-download-status' : 'zip-download-status');
  if (button.disabled) return;
  button.disabled = true;
  status.textContent = label + ' dosyası alınıyor…';
  try {
    const url = button.dataset.downloadUrl;
    if (!url?.startsWith(prefix)) throw new Error('Önce çıktıyı oluşturun.');
    const response = await aiditorFetch(url, {credentials: 'same-origin'});
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || 'ZIP indirilemedi. Çıktıyı yeniden oluşturun.');
    }
    if (response.headers.get('Content-Type')?.split(';')[0].trim() !== mime) {
      throw new Error('Sunucu ZIP yerine farklı bir yanıt verdi. Dosya kaydedilmedi.');
    }
    const blob = await response.blob();
    const signature = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
    if (blob.size < 22 || signature.join(',') !== '80,75,3,4') {
      throw new Error('ZIP dosyası eksik veya geçersiz. Çıktıyı yeniden oluşturun.');
    }
    if (window.pywebview) {
      if (typeof window.pywebview.api?.[method] !== 'function') {
        throw new Error('Kaydetme bağlantısı hazır değil. Uygulamayı yeniden açıp deneyin.');
      }
      const encoded = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = () => reject(new Error('ZIP dosyası okunamadı.'));
        reader.readAsDataURL(blob);
      });
      const result = await window.pywebview.api[method](encoded);
      if (!result?.ok) throw new Error(result?.error || 'ZIP kaydedilemedi.');
      status.textContent = result.cancelled ? 'Kaydetme iptal edildi. Yeniden deneyebilirsiniz.' : label + ' dosyası kaydedildi.';
    } else {
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = 'aiditor_article.' + kind;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
      status.textContent = label + ' tarayıcının indirme listesine gönderildi.';
    }
  } catch (error) {
    status.textContent = 'Hata: ' + (word ? error.message.replaceAll('ZIP', 'Word') : error.message);
  } finally {
    button.disabled = false;
  }
};

window.downloadArticleZip = () => downloadArticleOutput('zip');
window.downloadArticleDocx = () => downloadArticleOutput('docx');
