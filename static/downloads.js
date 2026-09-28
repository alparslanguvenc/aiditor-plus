/* Fetch inside the signed-in page. Native URL downloads can lose WebKit cookies. */
window.downloadArticleZip = async function () {
  const button = document.getElementById('dl-link');
  const status = document.getElementById('zip-download-status');
  if (button.disabled) return;
  button.disabled = true;
  status.textContent = 'ZIP dosyası alınıyor…';
  try {
    const url = button.dataset.downloadUrl;
    if (!url?.startsWith('/download/')) throw new Error('Önce LaTeX çıktısını oluşturun.');
    const response = await aiditorFetch(url, {credentials: 'same-origin'});
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || 'ZIP indirilemedi. Çıktıyı yeniden oluşturun.');
    }
    if (response.headers.get('Content-Type')?.split(';')[0].trim() !== 'application/zip') {
      throw new Error('Sunucu ZIP yerine farklı bir yanıt verdi. Dosya kaydedilmedi.');
    }
    const blob = await response.blob();
    const signature = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
    if (blob.size < 22 || signature.join(',') !== '80,75,3,4') {
      throw new Error('ZIP dosyası eksik veya geçersiz. Çıktıyı yeniden oluşturun.');
    }
    if (window.pywebview) {
      if (typeof window.pywebview.api?.save_article_zip !== 'function') {
        throw new Error('Kaydetme bağlantısı hazır değil. Uygulamayı yeniden açıp deneyin.');
      }
      const encoded = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = () => reject(new Error('ZIP dosyası okunamadı.'));
        reader.readAsDataURL(blob);
      });
      const result = await window.pywebview.api.save_article_zip(encoded);
      if (!result?.ok) throw new Error(result?.error || 'ZIP kaydedilemedi.');
      status.textContent = result.cancelled ? 'Kaydetme iptal edildi. Yeniden deneyebilirsiniz.' : 'ZIP dosyası kaydedildi.';
    } else {
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = 'aiditor_article.zip';
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
      status.textContent = 'ZIP tarayıcının indirme listesine gönderildi.';
    }
  } catch (error) {
    status.textContent = 'Hata: ' + error.message;
  } finally {
    button.disabled = false;
  }
};
