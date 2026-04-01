# AI-ditor Plus

**AI-ditor Plus**, akademik dergi makalelerini kolayca LaTeX formatına dönüştüren bir masaüstü uygulamasıdır. Dergi bilgilerini, yazar detaylarını, bölümleri, şekil ve tabloları form arayüzü üzerinden girebilir; tek tıkla Overleaf'e hazır ZIP dosyası oluşturabilirsiniz.

> Geliştirici: **Alparslan Güvenç**
> [![LinkedIn](https://img.shields.io/badge/LinkedIn-Alparslan%20Güvenç-0077B5?logo=linkedin)](https://linkedin.com/in/alparslan-güvenç)

---

## ⬇️ İndir

[![macOS](https://img.shields.io/badge/macOS-DMG%20İndir-000000?logo=apple&logoColor=white&style=for-the-badge)](https://github.com/alparslanguvenc/aiditor-plus/releases/latest/download/AIditorPlus_Installer.dmg)
[![Windows](https://img.shields.io/badge/Windows-EXE%20İndir-0078D6?logo=windows&logoColor=white&style=for-the-badge)](https://github.com/alparslanguvenc/aiditor-plus/releases/latest/download/AIditorPlus_Setup.exe)

Ya da [tüm sürümleri](https://github.com/alparslanguvenc/aiditor-plus/releases) görüntüleyin.

---

## Özellikler

- Dergi adı, ISSN/e-ISSN, URL ve logo özelleştirme
- Profil kaydetme — aynı dergi bilgilerini tekrar girmeden kullanma
- Çoklu yazar desteği (ünvan, kurum, e-posta, ORCID)
- Bölüm, alt bölüm ve alt-alt bölüm ekleme
- Şekil ve tablo ekleme (sürükle-bırak)
- Yazı tipi seçimi (Palatino, Times New Roman, Century, Calibri, Sans Serif)
- ISSN/e-ISSN koşullu gösterim — yalnızca girilen alanlar çıktıya yansır
- Overleaf'e hazır ZIP çıktısı (`main.tex` + logo + şekiller)
- Adım adım Overleaf yükleme rehberi

---

## Kurulum

### macOS

1. Yukarıdaki **macOS DMG İndir** butonuna tıklayın.
2. İndirilen DMG dosyasını açın.
3. **AI-ditor Plus** simgesini **Applications** klasörüne sürükleyin.
4. Applications'tan uygulamayı açın.

> **⚠️ İlk açılışta güvenlik uyarısı alırsanız:**
> Uygulamaya **sağ tıklayın → "Aç" → "Aç"** seçin.
> Ya da: **Sistem Ayarları → Gizlilik ve Güvenlik → "Yine de Aç"**

### Windows

1. Yukarıdaki **Windows EXE İndir** butonuna tıklayın.
2. İndirilen `AIditorPlus_Setup.exe` dosyasını çalıştırın.
3. Kurulum sihirbazını takip edin.
4. Masaüstündeki kısayoldan uygulamayı açın.

---

## Kullanım

### 1. Dergi Bilgilerini Girin

Uygulamayı açtığınızda tarayıcıda bir arayüz görünür. **Dergi Ayarları** bölümünden:
- Dergi adını (Türkçe / İngilizce) girin
- ISSN ve/veya e-ISSN ekleyin (ikisi de opsiyoneldir)
- Dergi URL'sini girin
- Dergi logosunu yükleyin (PNG önerilir)
- Yazı tipini seçin

Sık kullandığınız dergi bilgilerini **"Profil Kaydet"** ile kaydedebilir, sonraki kullanımlarda tek tıkla yükleyebilirsiniz.

### 2. Makale Bilgilerini Girin

**Makale Bilgileri** bölümünden:
- Makale başlığını (Türkçe / İngilizce) girin
- Anahtar kelimeler ve özeti ekleyin
- Cilt, sayı, sayfa, yıl bilgilerini doldurun

### 3. Yazarları Ekleyin

**Yazar Ekle** butonu ile her yazar için:
- Ünvan (Prof. Dr., Doç. Dr., vb.)
- Ad Soyad
- Kurum / Üniversite
- E-posta ve ORCID numarası

### 4. Bölümleri Oluşturun

**Bölüm Ekle** butonu ile makalenizin bölümlerini oluşturun:
- Ana bölüm (`\section`), alt bölüm (`\subsection`) veya alt-alt bölüm (`\subsubsection`) seçin
- Bölüm metnini girin
- Şekil veya tablo eklemek için ilgili butona tıklayın

### 5. Kaynakları Ekleyin

**Kaynaklar** bölümüne APA formatında referanslarınızı girin.

### 6. ZIP Oluşturun ve Overleaf'e Yükleyin

**ZIP İndir** butonuna tıklayın. İndirilen ZIP dosyasını Overleaf'e yüklemek için:

1. [overleaf.com](https://overleaf.com) → **New Project** → **Upload Project**
2. İndirilen ZIP dosyasını seçin.
3. Proje yüklendikten sonra: **Menu** → **Compiler** → **XeLaTeX** seçin.
4. **Recompile** butonuna tıklayın.

> ⚠️ Derleyici olarak mutlaka **XeLaTeX** seçilmelidir. pdfLaTeX ile derleme başarısız olur.

---

## Gereksinimler

- Python veya başka bir yazılım kurmanıza **gerek yoktur** — her şey uygulama içinde gömülüdür.
- Overleaf üzerinde derleme için ücretsiz bir [Overleaf hesabı](https://overleaf.com) yeterlidir.

---

## Lisans

[MIT License](LICENSE) — Telif hakkı © 2025 Alparslan Güvenç
