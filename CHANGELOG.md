# Sürüm geçmişi

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
