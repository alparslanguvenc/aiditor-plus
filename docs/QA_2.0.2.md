# 2.0.2 profil gizliliği doğrulaması

- Eski ortak profil klasörünü tarayan kod, listeleme/içe aktarma servisleri ve arayüz kontrolleri kaldırıldı.
- Diskte eski profil ve logo dosyaları bulunduğunda dahi emekli servislerin 404 döndürdüğü regresyon testiyle doğrulandı.
- 54 Python testi ve Chromium hesap/ön ayar/makale akışı geçti. Hesaba özel JSON yedekleme ve içe aktarma korundu.
- Oluşturulan macOS 2.0.2 paketi ayrı bir geçici hesapla açıldı. Eski profil panelinin bulunmadığı ve eski listeleme/okuma adreslerinin 404 döndürdüğü doğrulandı.
- macOS imzası ve DMG bütünlük kontrolü geçti.

Eski kişisel dergi kayıtları veya logoları bu depoya, test verilerine ya da kurulum paketine eklenmez.
