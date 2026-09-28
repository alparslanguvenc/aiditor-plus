# 2.0.3 ZIP indirme düzeltmesi — 2026-09-28

## Hata ve neden

Mac uygulamasından indirilen örnek dosya 112 bayttı ve ZIP yerine `login_required` JSON yanıtı içeriyordu. pywebview 6.2.1 Cocoa indirme kodu, WebKit yanıtını aldıktan sonra `NSURLSession.sharedSession()` ile URL'ye ikinci bir istek gönderiyordu. Bu istek WebKit'in oturum çerezini taşımıyordu.

## Düzeltme

- ZIP düğmesi, oturumu koruyan `aiditorFetch` üzerinden veriyi alır; HTTP durumu, içerik türü ve ZIP imzası doğrulanır.
- Masaüstünde doğrulanan veri JS/Python köprüsüne aktarılır; arşivin CRC bütünlüğü ve `main.tex` girdisi kontrol edilir. Kaydetme penceresinin seçtiği konuma geçici dosya üzerinden atomik yazılır.
- Tarayıcıda doğrulanan Blob indirilir. Giriş/hata yanıtları dosyaya yazılmaz.
- Hesap erişim denetimleri kaldırılmadı. Veritabanı şeması ve mevcut kayıtlar değişmedi.

## Doğrulama

- 59 Python testi geçti: ZIP baytlarının korunması, bozuk/eksik dosya reddi, iptal, yazma hatasında eski dosyayı koruma ve yinelenen kayıt engeli dahil.
- `tests/browser_downloads.py`: gerçek ZIP düğmesi, indirilen dosyanın CRC ve LaTeX içeriği; masaüstü köprüsüne iletilen baytların eşitliği; 404, HTML, geçersiz ZIP ve 401 yanıtlarının dosya olarak kaydedilmemesi geçti.
- `tests/browser_workflow.py` ve `tests/browser_races.py` geçti. Makale/dergi kayıtları, hesap ayrımı, kayıp yanıt kurtarma, logo ve Word/Excel akışları korundu.
- `scripts/native_smoke.py`: gerçek Mac WebKit oturumu, LaTeX üretimi, ZIP düğmesi, JS/Python köprüsü, dosyaya yazım ve CRC kontrolü geçti. Bu otomatik testte yalnızca işletim sisteminin dosya seçicisi geçici çıktı yolu ile değiştirilir.
- Paketlenmiş 2.0.3 Mac uygulaması geçici hesapla açıldı. macOS imza ve DMG bütünlük kontrolleri geçti.

Testlerde gerçek kullanıcı kayıtları kullanılmaz; geçici veri dizinleri oluşturulur. Kullanıcı dosyaları, hesap bilgileri ve hatalı indirme örnekleri GitHub'a eklenmez.
