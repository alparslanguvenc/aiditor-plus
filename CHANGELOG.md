# Sürüm geçmişi

## 2.3.0 — 2026-10-02

Kullanıcının sağladığı Word sayfa düzeni, herhangi bir gerçek dergiye ait logo, ISSN, URL, yazar veya makale metni taşınmadan “İki dilli kutulu kapak” adlı altıncı hazır şablona uyarlandı. İlk sayfada künye bandı, iki dilde başlık ve solda makale bilgileri / sağda gri özet panelleri bulunur. Devam sayfalarında tek/çift sayfa üst bilgileri ve altta sayfa numarası desteklenir. Word ve LaTeX çıktıları, hesabın dergi kimliğini ve yüklenen logosunu kullanır; seçim mevcut kimlik ayarlarını korur. Önizleme temsili, kimliksiz örnek sayfadır.

Mevcut beş şablon ve JGTTR Formatter değiştirilmedi.

## 2.2.0 — 2026-09-28

Word çıktılarında ilk sayfa dipnotları, etik beyan, başlık açıklaması ve dergi notları sayfanın altındaki gerçek alt bilgi alanına taşındı. Kısa özetlerde yukarı çıkma sorunu giderildi. Kullanıcının ilk sayfa alt bilgisi korunur; kapak notları sonraki sayfalarda tekrarlanmaz. Gövde ayrı Word bölümünde devam eder ve sayfa numarası sıfırlanmaz. Eski Word dosyalarını düzeltmek için uygulamadan yeniden çıktı alın.

“Sosyal bilimler” adlı beşinci hazır şablon eklendi: logolu gri künye, güçlü ayraç, ortalanmış başlık, yazar altında kurum bilgileri, 2,5 cm yan kenar boşluğu, 1,5 satır aralığı ve ayrı sayfada İngilizce özet. “Extended Summary” başlığı özelleştirilebilir. Uzun İngilizce özetler kayıpsız devam eder; yalnız İngilizce makalelerde yinelenen özet oluşmaz. Word ve LaTeX desteklenir. Örnek sayfa ve varsayılan ayarlar herhangi bir gerçek dergi veya makalenin kimliğini içermez.

Tek/çift üst bilgilerde geniş dergi adları için yerleşim ve `{sayfa_araligi}` etiketi eklendi. Yeni şablondaki tablo/görsel genişlikleri metin alanına uyarlandı. Hesaplar, makaleler, atıf bağlantıları ve diğer dört şablon korunur. JGTTR Formatter değiştirilmez.

## 2.1.0 — 2026-09-28

Dört dergi düzeniyle doğrudan düzenlenebilir Word (.docx) çıktısı eklendi. Metinler, başlıklar, birleşik hücreli tablolar, kaynakça ve üst/alt bilgiler Word nesneleri olarak üretilir. PNG/JPG ve PDF görseller desteklenir; PDF görsellerin ilk sayfası Word'e görüntü olarak eklenir. Oturumlu indirme ve doğrulanmış, atomik yerel dosya kaydı Word için de kullanılır.

Üst ve alt bilgiler için ortak/tek/çift sayfa seçimi, ilk sayfaya özel içerik, sol/orta/sağ alanları, otomatik bilgi etiketleri, sayfa numarası, punto ve çizgi ayarları eklendi. Ayarlar hesapta ve JSON ön ayar yedeklerinde saklanır; LaTeX ve Word aynı tercihleri kullanır.

APA yazar–yıl atıfları tekil eşleşmede kaynakça kaydına bağlanır. Word yer işaretleri ve PDF içi bağlantılar kullanılır; kaynakların kendi DOI/URL bağlantıları korunur. Belirsiz veya tanınmayan kaynaklar için eşleşme özeti gösterilir. Kaynak metni değiştirilmez. Dergi ayarlarında kapatılabilir.

Yeni PDF görsel bileşeniyle macOS paketinin asgari sistem sürümü 13 oldu. Word ile LaTeX arasında yazı tipi, satır/sayfa sonu ve çok uzun kapak düzeni farklılıkları olabilir. Mevcut hesap, makale ve LaTeX/ZIP akışı korunur. JGTTR Formatter değiştirilmez.

## 2.0.3 — 2026-09-28

Mac masaüstü uygulamasında ZIP indirilirken oturum bilgisinin kaybolması ve giriş hatasının `.zip` uzantısıyla kaydedilmesi düzeltildi. İndirme açık oturum üzerinden yapılır; içerik türü ve ZIP imzası kontrol edilir. Masaüstünde arşiv bütünlüğü doğrulanır ve işletim sisteminin kaydetme penceresiyle dosyaya yazılır. İptal veya yazma hatasında önceki dosya korunur. Hesaplar ve kayıtlı dergi/makale verileri değişmez.

## 2.0.2 — 2026-09-08

Önceki kurulumlardan kalan özel dergi profillerini otomatik keşfeden ve listeleyen bölüm kaldırıldı. Eski profil erişim ve aktarım uçları kapatıldı; uygulama başka dergilerin yerel ön ayarlarını sunmaz. Dergi hesaplarına ait ayarlar ile kullanıcının seçtiği JSON yedeklerini içe/dışa aktarma korunur.

## 2.0.1 — 2026-09-08

Uygulama logosu sade bir A monogramı ve turkuaz artı işaretiyle yenilendi. Lacivert ve fildişi renklerini kullanan görsel kimlik; uygulama arayüzü, tarayıcı simgesi, macOS uygulama simgesi ve Windows uygulama/kurulum simgelerinde tutarlı biçimde kullanılıyor.

## 2.0.0 — 2026-09-08

Dergi ayarları artık yerel hesaplara bağlıdır. Her dergi kendi logo, sayfa düzeni, tipografi, künye ve dipnot ön ayarlarıyla yeniden açılır. Dört görsel başlangıç şablonu seçildikten sonra özelleştirilebilir; ön ayarlar görselleriyle birlikte yedeklenebilir.

Makale taslaklarına kalıcı arşiv, otomatik kayıt, kayıt hatası bildirimi ve aynı anda düzenleme çakışması koruması eklendi. Word içe aktarma, zengin Word/Excel tabloları, kaynak sırasını koruyan metin/tablo yapıştırma, bölüm kimliğiyle ilişkilendirme ve otomatik ilk sayfa sığdırma JGTTR Formatter'ın güncel yaklaşımından Plus'a uyarlandı.

İngilizce çıktılar, Unicode yazar bilgileri, uzun kaynak adresleri, dosya adları ve logo paketleme davranışı iyileştirildi. Hesaplar arası veri ayrımı, dosya/içerik doğrulaması ve güvenli yerel oturum kontrolleri eklendi. Başlatılırken meşgul porttaki süreci zorla kapatma kaldırıldı. Masaüstü penceresi kapanmadan önce bekleyen kayıtları tamamlar.

MIT lisansı ve kâr amacı gütmeyen akademik destek amacı arayüzde, dokümantasyonda ve dağıtım açıklamalarında belirtildi. JGTTR Formatter kaynakları ve kurulu uygulaması değiştirilmedi.
